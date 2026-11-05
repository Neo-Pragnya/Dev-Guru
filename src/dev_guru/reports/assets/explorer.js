/* Dev Guru explorer. Offline and view-only: reads the embedded view model, never fetches, never executes.
   Untrusted text (paths, names, docs, source) is only ever assigned through textContent or attributes. */
(() => {
  "use strict";
  const D = JSON.parse(document.getElementById("dg-data").textContent);
  const M = JSON.parse(document.getElementById("dg-manifest").textContent);
  const $ = (s) => document.querySelector(s);
  const NS = "http://www.w3.org/2000/svg";
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "text") n.textContent = String(v);
      else if (k === "class") n.className = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : String(v));
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return n;
  }
  function sv(tag, attrs) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null) continue;
      if (k === "text") n.textContent = String(v);
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, String(v));
    }
    return n;
  }
  const fmt = (n) => Number(n).toLocaleString("en");
  const short = (p) => (p.length > 34 ? "…" + p.slice(-33) : p);

  // ------------------------------------------------------------------ indices
  const files = new Map(D.files.map((f) => [f.id, f]));
  const syms = new Map(D.symbols.map((s) => [s.id, s]));
  const nodeOf = (id) => files.get(id) || syms.get(id);
  const fileOf = (id) => (files.has(id) ? id : syms.get(id)?.file || null);
  const out = new Map(), inn = new Map(), callOut = new Map(), callIn = new Map(), inhOut = new Map(), inhIn = new Map();
  const push = (m, k, v) => { if (!m.has(k)) m.set(k, new Set()); m.get(k).add(v); };
  for (const e of D.edges) {
    if (e.k === "imports") { push(out, e.s, e.t); push(inn, e.t, e.s); }
    else if (e.k === "calls") { push(callOut, e.s, e.t); push(callIn, e.t, e.s); }
    else if (e.k === "inherits") { push(inhOut, e.s, e.t); push(inhIn, e.t, e.s); }
  }
  const get = (m, k) => [...(m.get(k) || [])];
  const PALETTE = ["#ffb347", "#3dd6c6", "#9b87ff", "#ff6f91", "#b7ef6a", "#6cc3ff", "#ffd36e", "#ff9ec7", "#7ee0a1", "#c79bff"];
  const pkgIndex = new Map(D.packages.map((p, i) => [p.id, i]));
  const colorOf = (fid) => PALETTE[(pkgIndex.get(files.get(fid)?.package) ?? 0) % PALETTE.length];
  const cycleFiles = new Set(D.insights.cycles.flat());
  const cyclePairs = new Set();
  for (const cyc of D.insights.cycles) for (const a of cyc) for (const b of get(out, a)) if (cyc.includes(b)) cyclePairs.add(a + "→" + b);

  // ------------------------------------------------------------------ state (shareable through the URL hash)
  const state = { view: "constellation", sel: null, filters: { imports: true, calls: true, inherits: true }, tour: 0, playing: !reduced };
  try {
    const h = new URLSearchParams(location.hash.slice(1));
    if (h.get("view")) state.view = h.get("view");
    if (h.get("sel") && nodeOf(h.get("sel"))) state.sel = h.get("sel");
    if (h.get("theme")) document.documentElement.dataset.theme = h.get("theme") === "day" ? "day" : "night";
    if (h.get("embed") === "1") document.documentElement.classList.add("embed"); // framed in a page: just tabs and stage
  } catch (_) { /* ignore a malformed hash */ }
  function syncHash() {
    const p = new URLSearchParams();
    p.set("view", state.view);
    if (state.sel) p.set("sel", state.sel);
    if (document.documentElement.dataset.theme === "day") p.set("theme", "day");
    if (document.documentElement.classList.contains("embed")) p.set("embed", "1");
    try { history.replaceState(null, "", "#" + p.toString()); } catch (_) { /* file:// in some browsers */ }
  }

  // ------------------------------------------------------------------ SVG stage with pan and zoom
  const svg = $("#svg");
  let world, cam = { x: 0, y: 0, k: 1 };
  function resetStage() {
    svg.replaceChildren();
    const defs = sv("defs");
    const glow = sv("filter", { id: "glow", x: "-50%", y: "-50%", width: "200%", height: "200%" });
    glow.append(sv("feGaussianBlur", { stdDeviation: "6" }));
    defs.append(glow);
    for (const [id, color] of [["arrow", "var(--muted)"], ["arrowHot", "var(--saffron)"]]) {
      const m = sv("marker", { id, viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse" });
      m.append(sv("path", { d: "M0,0 L10,5 L0,10 z", fill: color }));
      defs.append(m);
    }
    svg.append(defs);
    world = sv("g", { class: "world" });
    svg.append(world);
    svg.classList.remove("dim");
    applyCam();
  }
  const applyCam = () => world && world.setAttribute("transform", `translate(${cam.x},${cam.y}) scale(${cam.k})`);
  function fit(pad = 40, box) {
    if (space.active) return spaceFit();
    if (!world) return;
    const b = box || world.getBBox();
    const w = svg.clientWidth || 800, h = svg.clientHeight || 600;
    if (!b.width || !b.height) { cam = { x: w / 2, y: h / 2, k: 1 }; applyCam(); return; }
    const k = Math.min((w - pad * 2) / b.width, (h - pad * 2) / b.height, 2.2);
    cam = { k, x: w / 2 - (b.x + b.width / 2) * k, y: h / 2 - (b.y + b.height / 2) * k };
    animateCam();
  }
  let camAnim = null;
  function animateCam() {
    if (reduced) return applyCam();
    const from = parseCam(), to = { ...cam }, t0 = performance.now(), dur = 520;
    cancelAnimationFrame(camAnim);
    const step = (t) => {
      const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      world.setAttribute("transform", `translate(${from.x + (to.x - from.x) * e},${from.y + (to.y - from.y) * e}) scale(${from.k + (to.k - from.k) * e})`);
      if (p < 1) camAnim = requestAnimationFrame(step);
    };
    camAnim = requestAnimationFrame(step);
  }
  function parseCam() {
    const m = /translate\(([-\d.e]+),([-\d.e]+)\) scale\(([-\d.e]+)\)/.exec(world?.getAttribute("transform") || "");
    return m ? { x: +m[1], y: +m[2], k: +m[3] } : { ...cam };
  }
  function zoomBy(f, cx, cy) {
    if (space.active) return spaceZoom(f);
    const w = svg.clientWidth, h = svg.clientHeight;
    cx = cx ?? w / 2; cy = cy ?? h / 2;
    const k = Math.max(0.08, Math.min(6, cam.k * f));
    cam.x = cx - ((cx - cam.x) * k) / cam.k; cam.y = cy - ((cy - cam.y) * k) / cam.k; cam.k = k;
    applyCam();
  }
  svg.addEventListener("wheel", (e) => { e.preventDefault(); const r = svg.getBoundingClientRect(); zoomBy(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  let drag = null;
  svg.addEventListener("pointerdown", (e) => { if (e.button !== 0) return; drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: false }; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) { drag.moved = true; svg.classList.add("dragging"); }
    if (drag.moved) { cam.x = drag.cx + dx; cam.y = drag.cy + dy; applyCam(); }
  });
  svg.addEventListener("pointerup", () => { svg.classList.remove("dragging"); setTimeout(() => (drag = null), 0); });
  $("#zoomIn").onclick = () => zoomBy(1.25);
  $("#zoomOut").onclick = () => zoomBy(1 / 1.25);
  $("#fitBtn").onclick = () => fit();

  // pulses that travel along highlighted paths
  let pulseTimer = null;
  function pulses(paths) {
    cancelAnimationFrame(pulseTimer);
    world?.querySelectorAll(".pulse").forEach((p) => p.remove());
    if (reduced || !paths.length) return;
    const dots = paths.slice(0, 60).map((p, i) => ({ p, len: p.getTotalLength(), off: (i * 0.17) % 1, c: world.appendChild(sv("circle", { r: 3, class: "pulse" })) }));
    const t0 = performance.now();
    const step = (t) => {
      for (const d of dots) {
        if (!d.c.isConnected) return;
        const f = ((t - t0) / 1400 + d.off) % 1, pt = d.p.getPointAtLength(f * d.len);
        d.c.setAttribute("cx", pt.x); d.c.setAttribute("cy", pt.y); d.c.setAttribute("opacity", Math.sin(f * Math.PI));
      }
      pulseTimer = requestAnimationFrame(step);
    };
    pulseTimer = requestAnimationFrame(step);
  }
  const curve = (a, b, bend = 0.18) => {
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y;
    return `M${a.x},${a.y} Q${mx - dy * bend},${my + dx * bend} ${b.x},${b.y}`;
  };

  // ------------------------------------------------------------------ constellation: a 3D force-directed graph
  // Files are bodies in space. Imports are springs, every file repels the others, each package pulls its own files
  // together, and the whole graph is kept centred. Plain JavaScript on a 2D canvas: no WebGL, no library, no network.
  const cvs = $("#space"), ctx = cvs.getContext("2d");
  const space = { nodes: [], byId: new Map(), links: [], pkgs: [], groups: [], stars: [], yaw: 0.7, pitch: -0.3, dist: 900, cx: 0, cy: 0, cz: 0,
    alpha: 0, active: false, hover: null, raf: 0, idleAt: 0, anim: null, built: false, moved: false, w: 800, h: 600, theme: null, sprites: new Map(), frames: 0 };
  const hashOf = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619); return h >>> 0; };
  const rng = (seed) => () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

  function buildSpace() {
    if (space.built) return;
    space.built = true;
    const GOLD = Math.PI * (3 - Math.sqrt(5)), P = D.packages.length, R0 = 60 * Math.cbrt(D.files.length) + 40;
    D.packages.forEach((p, i) => {
      const y = P === 1 ? 0 : 1 - (i / (P - 1)) * 2, r = Math.sqrt(Math.max(0, 1 - y * y)), a = i * GOLD;
      space.pkgs.push({ id: p.id, ax: Math.cos(a) * r * R0, ay: y * R0, az: Math.sin(a) * r * R0, x: 0, y: 0, z: 0, n: 0, dx: 0, dy: 0, dz: 0 });
      space.groups.push([]);
    });
    for (const f of D.files) {
      const pi = pkgIndex.get(f.package) ?? 0, pk = space.pkgs[pi], rand = rng(hashOf(f.id)), j = 30 + Math.sqrt(D.packages[pi].files.length) * 8;
      const n = { id: f.id, pkg: pi, r: Math.max(4, Math.min(19, 3 + Math.sqrt(f.loc || 1) * 0.72)), color: colorOf(f.id), deg: 0,
        x: pk.ax + (rand() - 0.5) * j, y: pk.ay + (rand() - 0.5) * j, z: pk.az + (rand() - 0.5) * j, vx: 0, vy: 0, vz: 0, fx: null, fy: null, fz: null, sx: 0, sy: 0, ss: 0, depth: 0 };
      space.nodes.push(n); space.byId.set(f.id, n); space.groups[pi].push(n);
    }
    for (const e of D.edges) {
      const a = e.k === "imports" && space.byId.get(e.s), b = a && space.byId.get(e.t);
      if (!a || !b || a === b) continue;
      a.deg++; b.deg++;
      space.links.push({ a, b, cycle: cyclePairs.has(e.s + "→" + e.t), cross: a.pkg !== b.pkg });
    }
    const sr = rng(7);
    for (let i = 0; i < 320; i++) { const u = sr() * 2 - 1, t = sr() * Math.PI * 2, q = Math.sqrt(1 - u * u), R = R0 * (3 + sr() * 3); space.stars.push({ x: Math.cos(t) * q * R, y: u * R, z: Math.sin(t) * q * R, b: 0.3 + sr() * 0.7 }); }
    space.alpha = 1;
    // settle most of the way before the first frame; with reduced motion, settle completely
    const t0 = performance.now(), budget = reduced ? 1500 : 90;
    while (space.alpha > (reduced ? 0.002 : 0.12) && performance.now() - t0 < budget) tick();
  }

  function tick() {
    const N = space.nodes, A = space.alpha, S = 30 * A;
    for (const p of space.pkgs) { p.x = p.y = p.z = 0; p.n = 0; p.dx = p.dy = p.dz = 0; }
    for (const n of N) { const p = space.pkgs[n.pkg]; p.x += n.x; p.y += n.y; p.z += n.z; p.n++; }
    for (const p of space.pkgs) if (p.n) { p.x /= p.n; p.y /= p.n; p.z /= p.n; }
    // repulsion: exact within a package, and between packages through their centres of mass
    for (const g of space.groups) {
      const step = Math.max(1, Math.ceil(g.length / 600));
      for (let i = 0; i < g.length; i++) {
        const u = g[i];
        for (let j = i + 1; j < g.length; j += step) {
          const v = g[j]; let dx = v.x - u.x, dy = v.y - u.y, dz = v.z - u.z, d2 = dx * dx + dy * dy + dz * dz;
          if (d2 > 90000) continue;
          if (d2 < 1) { dx = 0.5; dy = 0.3; dz = 0.2; d2 = 1; }
          const w = (S * step) / d2;
          u.vx -= dx * w; u.vy -= dy * w; u.vz -= dz * w; v.vx += dx * w; v.vy += dy * w; v.vz += dz * w;
        }
      }
    }
    const P = space.pkgs;
    for (let i = 0; i < P.length; i++) for (let j = i + 1; j < P.length; j++) {
      const a = P[i], b = P[j]; if (!a.n || !b.n) continue;
      let dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z, d2 = dx * dx + dy * dy + dz * dz;
      if (d2 < 1) { dx = 1; d2 = 1; }
      const w = (S * 0.5) / d2;
      a.dx -= dx * w * b.n; a.dy -= dy * w * b.n; a.dz -= dz * w * b.n; b.dx += dx * w * a.n; b.dy += dy * w * a.n; b.dz += dz * w * a.n;
    }
    // imports are springs; a busy file moves less than a quiet one
    for (const l of space.links) {
      const { a, b } = l;
      let dx = b.x + b.vx - a.x - a.vx, dy = b.y + b.vy - a.y - a.vy, dz = b.z + b.vz - a.z - a.vz;
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1, rest = (l.cross ? 55 : 18) + a.r + b.r;
      const k = ((d - rest) / d) * A * (l.cross ? 0.35 : 0.8) / Math.min(a.deg, b.deg), bias = a.deg / (a.deg + b.deg);
      dx *= k; dy *= k; dz *= k;
      b.vx -= dx * bias; b.vy -= dy * bias; b.vz -= dz * bias; a.vx += dx * (1 - bias); a.vy += dy * (1 - bias); a.vz += dz * (1 - bias);
    }
    let mx = 0, my = 0, mz = 0;
    for (const n of N) {
      const p = space.pkgs[n.pkg];
      // each package pulls its files in, and a gentle gravity keeps loose packages from drifting off
      n.vx += ((p.x - n.x) * 0.06 - n.x * 0.012) * A + p.dx; n.vy += ((p.y - n.y) * 0.06 - n.y * 0.012) * A + p.dy; n.vz += ((p.z - n.z) * 0.06 - n.z * 0.012) * A + p.dz;
      n.vx *= 0.6; n.vy *= 0.6; n.vz *= 0.6;
      if (n.fx !== null) { n.x = n.fx; n.y = n.fy; n.z = n.fz; n.vx = n.vy = n.vz = 0; } else { n.x += n.vx; n.y += n.vy; n.z += n.vz; }
      mx += n.x; my += n.y; mz += n.z;
    }
    if (N.length) { mx /= N.length; my /= N.length; mz /= N.length; for (const n of N) { n.x -= mx; n.y -= my; n.z -= mz; if (n.fx !== null) { n.fx -= mx; n.fy -= my; n.fz -= mz; } } }
    space.alpha += (0 - space.alpha) * 0.0228;
    if (space.alpha < 0.002) space.alpha = 0;
  }

  // ---- camera: orbit (yaw, pitch) around a centre at a distance, perspective projection
  function rot(x, y, z) {
    const c = Math.cos(space.yaw), s = Math.sin(space.yaw), cp = Math.cos(space.pitch), sp = Math.sin(space.pitch);
    const x1 = x * c - z * s, z1 = x * s + z * c;
    return [x1, y * cp - z1 * sp, y * sp + z1 * cp];
  }
  function unrot(x1, y2, z2) {
    const c = Math.cos(space.yaw), s = Math.sin(space.yaw), cp = Math.cos(space.pitch), sp = Math.sin(space.pitch);
    const y = cp * y2 + sp * z2, z1 = -sp * y2 + cp * z2;
    return [c * x1 + s * z1, y, -s * x1 + c * z1];
  }
  const focal = () => Math.min(space.w, space.h) * 1.1;
  function proj(o) {
    const [x, y, z] = rot(o.x - space.cx, o.y - space.cy, o.z - space.cz), depth = space.dist + z, s = depth > 12 ? focal() / depth : 0;
    o.sx = space.w / 2 + x * s; o.sy = space.h / 2 + y * s; o.ss = s; o.depth = depth;
  }
  function sizeSpace() {
    const r = cvs.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
    space.w = r.width || 800; space.h = r.height || 600;
    cvs.width = Math.round(space.w * dpr); cvs.height = Math.round(space.h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function spread(nodes, cx, cy, cz) {
    const d = nodes.map((n) => Math.hypot(n.x - cx, n.y - cy, n.z - cz)).sort((a, b) => a - b);
    return Math.max(40, d[Math.floor((d.length - 1) * 0.95)] || 40);
  }
  function flyTo(cx, cy, cz, dist) {
    const to = { cx, cy, cz, dist: Math.max(60, Math.min(30000, dist)) };
    if (reduced) { Object.assign(space, to); return wake(); }
    space.anim = { from: { cx: space.cx, cy: space.cy, cz: space.cz, dist: space.dist }, to, t0: performance.now() };
    wake();
  }
  const fitDist = (R) => (focal() * R) / (0.44 * Math.min(space.w, space.h)) + R * 0.35;
  function spaceFit() { if (space.nodes.length) flyTo(0, 0, 0, fitDist(spread(space.nodes, 0, 0, 0))); }
  function spaceFocus(id) {
    const n = space.byId.get(id); if (!n) return spaceFit();
    flyTo(n.x, n.y, n.z, Math.min(space.anim ? space.anim.to.dist : space.dist, fitDist(spread(space.nodes, 0, 0, 0)) * 0.55));
  }
  function spaceFocusPackage(pid) {
    const i = pkgIndex.get(pid), g = space.groups[i]; if (!g || !g.length) return;
    const c = g.reduce((a, n) => [a[0] + n.x / g.length, a[1] + n.y / g.length, a[2] + n.z / g.length], [0, 0, 0]);
    flyTo(c[0], c[1], c[2], fitDist(spread(g, ...c)) * 1.1);
  }
  const spaceZoom = (f) => { space.dist = Math.max(60, Math.min(30000, space.dist / f)); space.anim = null; space.moved = true; wake(); };

  // ---- drawing: stars, links with depth fog, shaded bodies sorted far to near, labels, pulses
  function themeColors() {
    const cs = getComputedStyle(document.documentElement), v = (k) => cs.getPropertyValue(k).trim();
    return { ink: v("--ink"), muted: v("--muted"), faint: v("--faint"), bg: v("--bg-2"), saffron: v("--saffron"), rose: v("--rose"), day: document.documentElement.dataset.theme === "day" };
  }
  function sprite(color) {
    if (space.sprites.has(color)) return space.sprites.get(color);
    const c = document.createElement("canvas"); c.width = c.height = 64;
    const g = c.getContext("2d"), grd = g.createRadialGradient(24, 22, 2, 32, 32, 30);
    grd.addColorStop(0, "#ffffff"); grd.addColorStop(0.18, color); grd.addColorStop(0.85, color); grd.addColorStop(1, "rgba(0,0,0,0.55)");
    g.fillStyle = grd; g.beginPath(); g.arc(32, 32, 30, 0, Math.PI * 2); g.fill();
    const glow = document.createElement("canvas"); glow.width = glow.height = 64;
    const h = glow.getContext("2d"), gg = h.createRadialGradient(32, 32, 0, 32, 32, 32);
    gg.addColorStop(0, color); gg.addColorStop(1, "rgba(0,0,0,0)");
    h.fillStyle = gg; h.fillRect(0, 0, 64, 64);
    const s = { body: c, glow }; space.sprites.set(color, s); return s;
  }
  function focusSet() {
    const f = space.hover || (state.sel && fileOf(state.sel));
    return f && space.byId.has(f) ? { id: f, near: new Set([f, ...get(out, f), ...get(inn, f)]) } : null;
  }
  function drawSpace(t) {
    const C = ctx, T = space.theme || (space.theme = themeColors()), W = space.w, H = space.h;
    C.clearRect(0, 0, W, H);
    for (const s of space.stars) proj(s);
    C.fillStyle = T.faint;
    for (const s of space.stars) if (s.ss) { C.globalAlpha = s.b * 0.7; C.fillRect(s.sx, s.sy, s.b > 0.85 ? 1.8 : 1.1, s.b > 0.85 ? 1.8 : 1.1); }
    const N = space.nodes; let dMin = Infinity, dMax = -Infinity;
    for (const n of N) { proj(n); if (n.ss) { dMin = Math.min(dMin, n.depth); dMax = Math.max(dMax, n.depth); } }
    const fog = (d) => 1 - 0.72 * Math.max(0, Math.min(1, (d - dMin) / (dMax - dMin + 1)));
    const F = focusSet(), hotLinks = [];
    C.lineWidth = 1;
    if (state.filters.imports) for (const l of space.links) {
      const { a, b } = l; if (!a.ss || !b.ss) continue;
      const hot = F && (a.id === F.id || b.id === F.id);
      if (hot) { hotLinks.push(l); continue; }
      C.globalAlpha = (F ? 0.05 : l.cycle ? 0.75 : 0.32) * fog((a.depth + b.depth) / 2);
      C.strokeStyle = l.cycle ? T.rose : T.day ? "#6a52e0" : "#9b87ff";
      C.beginPath(); C.moveTo(a.sx, a.sy); C.lineTo(b.sx, b.sy); C.stroke();
    }
    C.lineWidth = 2; C.strokeStyle = T.saffron; C.globalAlpha = 0.95;
    for (const { a, b } of hotLinks) { C.beginPath(); C.moveTo(a.sx, a.sy); C.lineTo(b.sx, b.sy); C.stroke(); }
    const order = N.filter((n) => n.ss).sort((a, b) => b.depth - a.depth), sel = state.sel && fileOf(state.sel);
    for (const n of order) {
      const r = Math.max(1.2, n.r * n.ss), near = !F || F.near.has(n.id), sp = sprite(n.color);
      C.globalAlpha = near ? fog(n.depth) : 0.12;
      if (F && near || n.id === sel) { C.globalAlpha = 0.55; C.drawImage(sp.glow, n.sx - r * 3, n.sy - r * 3, r * 6, r * 6); C.globalAlpha = 1; }
      C.drawImage(sp.body, n.sx - r, n.sy - r, r * 2, r * 2);
      if (n.id === sel) { C.globalAlpha = 1; C.strokeStyle = T.saffron; C.lineWidth = 2.5; C.beginPath(); C.arc(n.sx, n.sy, r + 4, 0, Math.PI * 2); C.stroke(); }
    }
    // pulses travel from importer to imported along the lit links
    if (hotLinks.length) {
      C.fillStyle = T.saffron;
      hotLinks.slice(0, 80).forEach(({ a, b }, i) => {
        const f = ((t / 1400) + i * 0.17) % 1;
        C.globalAlpha = Math.sin(f * Math.PI); C.beginPath(); C.arc(a.sx + (b.sx - a.sx) * f, a.sy + (b.sy - a.sy) * f, 2.6, 0, Math.PI * 2); C.fill();
      });
    }
    // labels: package names at their centres, file names for lit, selected and large nearby bodies
    // a label is drawn only where it does not cover one already drawn
    const placed = [], free = (x, y, w) => { const b = [x - 2, y - 12, x + w + 2, y + 3]; if (placed.some((q) => b[0] < q[2] && b[2] > q[0] && b[1] < q[3] && b[3] > q[1])) return false; placed.push(b); return true; };
    C.textAlign = "left"; C.font = "11px Inter, system-ui, sans-serif"; C.lineWidth = 3; C.strokeStyle = T.bg;
    const named = F ? new Set([F.id, ...[...F.near].sort((x, y) => files.get(y).loc - files.get(x).loc).slice(0, 12)]) : null;
    for (const n of [...order].reverse()) {
      const f = files.get(n.id), lit = named && named.has(n.id), r = n.r * n.ss;
      if (!(lit || n.id === sel || (!F && (r > 8 || ((f.entry || f.fan_in >= 4) && n.ss > 0.9))))) continue;
      const x = n.sx + r + 4, y = n.sy + 4;
      if (n.id !== sel && n.id !== F?.id && !free(x, y, C.measureText(f.name).width)) continue;
      C.globalAlpha = lit || n.id === sel ? 1 : 0.75 * fog(n.depth); C.fillStyle = T.ink;
      C.strokeText(f.name, x, y); C.fillText(f.name, x, y);
    }
    C.textAlign = "center"; C.font = "700 11px Inter, system-ui, sans-serif"; C.globalAlpha = F ? 0.35 : 0.8;
    const big = [...space.groups.keys()].sort((x, y) => space.groups[y].length - space.groups[x].length).slice(0, 10);
    for (const i of big) {
      const g = space.groups[i]; if (!g.length) continue;
      const c = g.reduce((o, n) => ({ x: o.x + n.x / g.length, y: o.y + n.y / g.length, z: o.z + n.z / g.length }), { x: 0, y: 0, z: 0 });
      proj(c); if (!c.ss) continue;
      const id = space.pkgs[i].id, top = Math.min(...g.map((n) => n.sy - n.r * n.ss)) - 10;
      const text = (id === "." ? "(root)" : id.split("/").slice(-2).join("/")).toUpperCase(), w = C.measureText(text).width, y = Math.max(14, top);
      if (!free(c.sx - w / 2, y, w)) continue;
      C.fillStyle = T.faint; C.fillText(text, c.sx, y);
    }
    C.globalAlpha = 1;
  }

  let lastT = 0;
  function loop(t) {
    space.raf = 0;
    if (!space.active) return;
    const dt = Math.min(64, t - (lastT || t)); lastT = t;
    if (space.alpha > 0) {
      tick();
      // while the graph settles, the camera keeps it framed, until someone takes the controls
      if (!space.moved && !state.sel && !space.anim && (++space.frames % 4 === 0 || space.alpha === 0)) space.dist += (fitDist(spread(space.nodes, 0, 0, 0)) - space.dist) * (space.alpha === 0 ? 1 : 0.25);
    }
    if (space.anim) {
      const a = space.anim, p = Math.min(1, (t - a.t0) / 650), e = 1 - Math.pow(1 - p, 3);
      for (const k of ["cx", "cy", "cz", "dist"]) space[k] = a.from[k] + (a.to[k] - a.from[k]) * e;
      if (p >= 1) space.anim = null;
    }
    if (!reduced && !sdrag && performance.now() - space.idleAt > 2500) space.yaw += 0.00011 * dt;
    drawSpace(t);
    if (!document.hidden && (!reduced || space.alpha > 0 || space.anim)) space.raf = requestAnimationFrame(loop);
  }
  function wake() { if (space.active && !space.raf) { lastT = 0; space.raf = requestAnimationFrame(loop); } }
  document.addEventListener("visibilitychange", wake);

  function pick(x, y) {
    let best = null;
    for (const n of space.nodes) {
      if (!n.ss) continue;
      const r = Math.max(6, n.r * n.ss) + 3, dx = n.sx - x, dy = n.sy - y;
      if (dx * dx + dy * dy <= r * r && (!best || n.depth < best.depth)) best = n;
    }
    return best;
  }
  function setHover(id) {
    if (space.hover === id) return;
    space.hover = id;
    const f = id || (state.sel && fileOf(state.sel));
    cvs.style.cursor = id ? "pointer" : "";
    $("#hint").textContent = f && files.has(f) ? `${files.get(f).path} · imports ${get(out, f).length} · imported by ${get(inn, f).length}` : "Drag to orbit · drag a file to pull it · scroll to zoom · double-click to fly to a file";
    wake();
  }
  const local = (e) => { const r = cvs.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  let sdrag = null;
  cvs.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const [x, y] = local(e), hit = pick(x, y);
    sdrag = { x: e.clientX, y: e.clientY, yaw: space.yaw, pitch: space.pitch, node: hit, moved: false };
    space.idleAt = performance.now(); cvs.setPointerCapture(e.pointerId);
  });
  cvs.addEventListener("pointermove", (e) => {
    const [x, y] = local(e);
    if (!sdrag) { setHover(pick(x, y)?.id || null); return; }
    const dx = e.clientX - sdrag.x, dy = e.clientY - sdrag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4 && !sdrag.moved) { sdrag.moved = true; cvs.classList.add("dragging"); }
    if (!sdrag.moved) return;
    space.idleAt = performance.now(); space.moved = true; space.anim = null;
    if (sdrag.node) {
      // move the body in the screen plane at its own depth, and let the graph follow
      const n = sdrag.node, s = n.ss || 1, [ox, oy, oz] = unrot((x - space.w / 2) / s, (y - space.h / 2) / s, n.depth - space.dist);
      n.fx = ox + space.cx; n.fy = oy + space.cy; n.fz = oz + space.cz;
      space.alpha = Math.max(space.alpha, 0.3);
    } else {
      space.yaw = sdrag.yaw + dx * 0.006;
      space.pitch = Math.max(-1.45, Math.min(1.45, sdrag.pitch + dy * 0.006));
    }
    wake();
  });
  const release = () => {
    if (!sdrag) return;
    const d = sdrag; sdrag = null; cvs.classList.remove("dragging");
    if (d.node) { d.node.fx = d.node.fy = d.node.fz = null; if (!d.moved) select(d.node.id); }
    space.idleAt = performance.now(); wake();
  };
  cvs.addEventListener("pointerup", release);
  cvs.addEventListener("pointercancel", release);
  cvs.addEventListener("pointerleave", () => { if (!sdrag) setHover(null); });
  cvs.addEventListener("wheel", (e) => { e.preventDefault(); space.idleAt = performance.now(); spaceZoom(e.deltaY < 0 ? 1.12 : 1 / 1.12); }, { passive: false });
  cvs.addEventListener("dblclick", (e) => { const [x, y] = local(e), n = pick(x, y); space.moved = true; if (n) spaceFocus(n.id); else spaceFit(); });

  function drawConstellation() {
    resetStage();
    buildSpace();
    space.active = true; space.theme = null;
    sizeSpace();
    space.hover = null; setHover(null);
    legend([["imports", "rgba(155,135,255,.7)", "import"], ["cycle", "var(--rose)", "import cycle"], ["dot", "", "size = lines · colour = package · drag to orbit"]]);
    wake();
  }
  // a test and automation hook: what is lit when a file is hovered
  function spaceProbe(id) {
    setHover(id || null);
    const F = focusSet(), hot = F ? space.links.filter((l) => l.a.id === F.id || l.b.id === F.id).length : 0;
    return { nodes: space.nodes.length, lit: F ? F.near.size : 0, links: hot, settled: space.alpha === 0, drawn: space.nodes.filter((n) => n.ss).length, running: !!space.raf || reduced, yaw: space.yaw, dist: Math.round(space.dist), fit: Math.round(fitDist(spread(space.nodes, 0, 0, 0))), w: space.w, h: space.h };
  }

  // ------------------------------------------------------------------ flow: layered dependency map
  function drawFlow() {
    resetStage();
    if (state.flowLevel === undefined) state.flowLevel = D.files.length > 120 ? "packages" : "files";
    if (state.flowLevel === "packages") return drawPackageFlow();
    const nodes = D.files.filter((f) => get(out, f.id).length || get(inn, f.id).length).map((f) => f.id);
    if (!nodes.length) return emptyStage("No imports between workspace files", "Every file stands alone, so there's no flow to draw.");
    // break cycles with a DFS, then longest-path layering from the importers' side
    const color = new Map(), back = new Set(), order = [];
    const visit = (u) => {
      color.set(u, 1);
      for (const v of get(out, u).sort()) { if (color.get(v) === 1) back.add(u + "→" + v); else if (!color.get(v)) visit(v); }
      color.set(u, 2); order.push(u);
    };
    nodes.sort().forEach((n) => !color.get(n) && visit(n));
    const layer = new Map();
    for (const u of order) { // sinks first: layer = 1 + max(layer of what u imports)
      let L = 0;
      for (const v of get(out, u)) if (!back.has(u + "→" + v)) L = Math.max(L, (layer.get(v) ?? 0) + 1);
      layer.set(u, L);
    }
    const maxL = Math.max(...layer.values());
    const cols = [];
    for (const [id, L] of layer) (cols[maxL - L] ||= []).push(id);
    for (const c of cols) c.sort((a, b) => files.get(a).package.localeCompare(files.get(b).package) || a.localeCompare(b));
    const y = new Map();
    const place = () => cols.forEach((c) => c.forEach((id, i) => y.set(id, i)));
    place();
    for (let sweep = 0; sweep < 4; sweep++) { // barycentre ordering reduces crossings
      cols.forEach((c, ci) => {
        if (!ci) return;
        const bary = (id) => { const ns = [...get(out, id), ...get(inn, id)].filter((n) => y.has(n)); return ns.length ? ns.reduce((s, n) => s + y.get(n), 0) / ns.length : y.get(id); };
        c.sort((a, b) => bary(a) - bary(b) || a.localeCompare(b));
      });
      place();
    }
    const W = 210, H = 34, GX = 110, GY = 14;
    const pos = new Map();
    cols.forEach((c, ci) => c.forEach((id, i) => pos.set(id, { x: ci * (W + GX), y: i * (H + GY) })));
    const ge = sv("g"), gn = sv("g");
    world.append(ge, gn);
    cols.forEach((c, ci) => world.insertBefore(sv("text", { class: "lane-label", x: ci * (W + GX), y: -16, text: ci === 0 ? "entry side" : ci === cols.length - 1 ? "foundations" : `layer ${ci + 1}` }), ge));
    const edgeEls = [];
    for (const [s, ts] of out) for (const t of ts) {
      const a = pos.get(s), b = pos.get(t);
      if (!a || !b) continue;
      const cyc = back.has(s + "→" + t) || cyclePairs.has(s + "→" + t);
      const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, dx = Math.max(40, Math.abs(x2 - x1) / 2);
      const d = x2 > x1 ? `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}` : `M${a.x},${y1} C${a.x - 80},${y1 - 60} ${b.x + W + 80},${y2 - 60} ${b.x + W},${y2}`;
      const p = sv("path", { class: "edge imports" + (cyc ? " cycle" : ""), d, "marker-end": "url(#arrow)" });
      p.dataset.s = s; p.dataset.t = t;
      ge.append(p); edgeEls.push(p);
    }
    const boxes = new Map();
    for (const [id, p] of pos) {
      const f = files.get(id);
      const g = sv("g", { class: "node box", transform: `translate(${p.x},${p.y})` });
      g.append(sv("rect", { width: W, height: H, rx: 10, fill: "var(--panel-solid)", stroke: colorOf(id), "stroke-width": cycleFiles.has(id) ? 2.5 : 1.2 }));
      g.append(sv("circle", { cx: 14, cy: H / 2, r: 5, fill: colorOf(id) }));
      g.append(sv("text", { x: 26, y: H / 2 + 4, text: short(f.path) }));
      g.dataset.id = id;
      g.addEventListener("mouseenter", () => hot(id));
      g.addEventListener("mouseleave", () => hot(null));
      g.addEventListener("click", () => { if (!drag?.moved) select(id); });
      gn.append(g); boxes.set(id, g);
    }
    function hot(id) {
      const focus = id || (state.sel && fileOf(state.sel));
      svg.classList.toggle("dim", !!focus);
      boxes.forEach((g) => g.classList.remove("hot")); edgeEls.forEach((p) => p.classList.remove("hot"));
      if (!focus || !pos.has(focus)) { pulses([]); return; }
      // everything downstream (what it depends on) and upstream (what depends on it)
      const walk = (start, m) => { const seen = new Set([start]), q = [start]; while (q.length) for (const n of get(m, q.shift())) if (!seen.has(n)) { seen.add(n); q.push(n); } return seen; };
      const reach = new Set([...walk(focus, out), ...walk(focus, inn)]);
      reach.forEach((n) => boxes.get(n)?.classList.add("hot"));
      const hotEdges = edgeEls.filter((p) => reach.has(p.dataset.s) && reach.has(p.dataset.t));
      hotEdges.forEach((p) => p.classList.add("hot"));
      pulses(hotEdges);
      $("#hint").textContent = `${files.get(focus).path}: ${walk(focus, out).size - 1} downstream · ${walk(focus, inn).size - 1} upstream`;
    }
    hot(null);
    const isolated = D.files.length - nodes.length;
    legend([["imports", "rgba(155,135,255,.7)", "imports (left → right)"], ["cycle", "var(--rose)", `cycle (${D.insights.cycles.length})`], ["", "", isolated ? `${isolated} file(s) with no imports not shown` : ""]]);
  }

  function drawPackageFlow() {
    const pkgOf = (fid) => files.get(fid).package;
    const weight = new Map();
    for (const [s, ts] of out) for (const t of ts) { const a = pkgOf(s), b = pkgOf(t); if (a !== b) weight.set(a + "\u0000" + b, (weight.get(a + "\u0000" + b) || 0) + 1); }
    const pout = new Map(), pin = new Map();
    for (const k of weight.keys()) { const [a, b] = k.split("\u0000"); push(pout, a, b); push(pin, b, a); }
    const ids = D.packages.map((p) => p.id).filter((id) => pout.has(id) || pin.has(id));
    if (!ids.length) return emptyStage("No imports between packages", "Each package stands alone.");
    const color = new Map(), back = new Set(), order = [];
    const visit = (u) => { color.set(u, 1); for (const v of get(pout, u).sort()) { if (color.get(v) === 1) back.add(u + "\u0000" + v); else if (!color.get(v)) visit(v); } color.set(u, 2); order.push(u); };
    ids.sort().forEach((n) => !color.get(n) && visit(n));
    const layer = new Map();
    for (const u of order) { let L = 0; for (const v of get(pout, u)) if (!back.has(u + "\u0000" + v)) L = Math.max(L, (layer.get(v) ?? 0) + 1); layer.set(u, L); }
    const maxL = Math.max(...layer.values()), cols = [];
    for (const [id, L] of layer) (cols[maxL - L] ||= []).push(id);
    cols.forEach((c) => c.sort());
    const W = 230, H = 46, GX = 120, GY = 16, pos = new Map();
    cols.forEach((c, ci) => c.forEach((id, i) => pos.set(id, { x: ci * (W + GX), y: i * (H + GY) - (c.length * (H + GY)) / 2 })));
    const ge = sv("g"), gn = sv("g"); world.append(ge, gn);
    const maxW = Math.max(...weight.values()), edgeEls = [];
    for (const [k, w] of weight) {
      const [s, t] = k.split("\u0000"), a = pos.get(s), b = pos.get(t);
      if (!a || !b) continue;
      const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, dx = Math.max(50, Math.abs(x2 - x1) / 2);
      const d = x2 > x1 ? `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}` : `M${a.x},${y1} C${a.x - 90},${y1 - 70} ${b.x + W + 90},${y2 - 70} ${b.x + W},${y2}`;
      const p = sv("path", { class: "edge imports" + (back.has(k) ? " cycle" : ""), d, "stroke-width": 1 + (5 * w) / maxW });
      p.dataset.s = s; p.dataset.t = t; ge.append(p); edgeEls.push(p);
    }
    const boxes = new Map();
    for (const [id, p] of pos) {
      const pk = D.packages.find((x) => x.id === id), col = PALETTE[pkgIndex.get(id) % PALETTE.length];
      const g = sv("g", { class: "node box", transform: `translate(${p.x},${p.y})` });
      g.append(sv("rect", { width: W, height: H, rx: 12, fill: "var(--panel-solid)", stroke: col, "stroke-width": 1.5 }));
      g.append(sv("text", { x: 14, y: 19, text: id === "." ? "(root)" : (id.length > 30 ? "…" + id.slice(-29) : id) }));
      g.append(sv("text", { x: 14, y: 35, class: "sub", text: `${pk.files.length} files · → ${get(pout, id).length} · ← ${get(pin, id).length}` }));
      g.addEventListener("mouseenter", () => hot(id)); g.addEventListener("mouseleave", () => hot(null));
      g.addEventListener("click", () => { if (!drag?.moved) { state.flowLevel = "files"; select(pk.files[0]); } });
      gn.append(g); boxes.set(id, g);
    }
    function hot(id) {
      svg.classList.toggle("dim", !!id);
      boxes.forEach((g) => g.classList.remove("hot")); edgeEls.forEach((p) => p.classList.remove("hot"));
      if (!id) { pulses([]); $("#hint").textContent = `${ids.length} packages · ${weight.size} package dependencies · click a package to see its files`; return; }
      boxes.get(id)?.classList.add("hot");
      const hotE = edgeEls.filter((p) => p.dataset.s === id || p.dataset.t === id);
      hotE.forEach((p) => { p.classList.add("hot"); boxes.get(p.dataset.s)?.classList.add("hot"); boxes.get(p.dataset.t)?.classList.add("hot"); });
      pulses(hotE);
      $("#hint").textContent = `${id}: depends on ${get(pout, id).length} packages, used by ${get(pin, id).length}`;
    }
    hot(null);
    legend([["imports", "rgba(155,135,255,.7)", "package imports (thicker = more)"], ["cycle", "var(--rose)", "cycle"]]);
  }

  // ------------------------------------------------------------------ impact: blast-radius rings
  function dependents(id) {
    const symbolLevel = syms.has(id);
    const methodsOf = (n) => D.symbols.filter((s) => s.kind === "method" && s.file === syms.get(n)?.file && s.name.startsWith(syms.get(n).name + ".")).map((s) => s.id);
    const next = (n) => symbolLevel ? [...get(callIn, n), ...get(inhIn, n), ...(syms.get(n)?.kind === "class" ? methodsOf(n).flatMap((m) => get(callIn, m)) : [])].filter((x) => x !== n) : [...get(inn, n), ...new Set([...(files.get(n)?.symbols || [])].flatMap((s) => get(callIn, s)).map(fileOf).filter((f) => f && f !== n))];
    const dist = new Map([[id, 0]]), parent = new Map(), q = [id];
    while (q.length) { const u = q.shift(); for (const v of next(u)) if (!dist.has(v)) { dist.set(v, dist.get(u) + 1); parent.set(v, u); q.push(v); } }
    return { dist, parent, symbolLevel };
  }
  function drawImpact() {
    resetStage();
    const focus = state.sel || D.insights.most_depended[0] || D.files[0].id;
    const { dist, parent, symbolLevel } = dependents(focus);
    const rings = [];
    for (const [id, d] of dist) if (d) (rings[Math.min(d, 4)] ||= []).push(id);
    const R = 120, pos = new Map([[focus, { x: 0, y: 0 }]]);
    rings.forEach((ids, d) => {
      if (!ids) return;
      world.append(sv("circle", { class: "ring", r: d * R }));
      world.append(sv("text", { class: "ring-label", x: 6, y: -d * R - 6, text: `${d === 4 ? "4+" : d} hop${d === 1 ? "" : "s"} · ${ids.length}` }));
      ids.sort((a, b) => (fileOf(a) || "").localeCompare(fileOf(b) || "") || a.localeCompare(b));
      ids.forEach((id, i) => { const a = (i / ids.length) * Math.PI * 2 - Math.PI / 2 + d * 0.4; pos.set(id, { x: Math.cos(a) * d * R, y: Math.sin(a) * d * R }); });
    });
    const ge = sv("g"), gn = sv("g");
    world.append(ge, gn);
    const paths = [];
    for (const [id, p] of parent) { const a = pos.get(id), b = pos.get(p); if (a && b) { const e = sv("path", { class: "edge hot " + (symbolLevel ? "calls" : "imports"), d: curve(a, b, 0.1), "marker-end": "url(#arrowHot)" }); ge.append(e); paths.push(e); } }
    for (const [id, p] of pos) {
      const n = nodeOf(id), isFocus = id === focus;
      const g = sv("g", { class: "node" + (isFocus ? " selected" : ""), transform: `translate(${p.x},${p.y})` });
      const color = colorOf(fileOf(id));
      g.append(sv("circle", { class: "halo", r: isFocus ? 26 : 13, fill: color, filter: "url(#glow)" }));
      g.append(sv("circle", { class: "core", r: isFocus ? 16 : 7, fill: color }));
      g.append(sv("text", { x: isFocus ? 22 : 11, y: 4, text: n.name }));
      g.addEventListener("click", () => { if (!drag?.moved) select(id); });
      gn.append(g);
    }
    if (!reduced) for (let i = 0; i < 3; i++) { const c = sv("circle", { class: "ripple", r: 10 }); world.append(c); setTimeout(() => c.classList.add("go"), 30 + i * 420); }
    pulses(paths);
    const total = dist.size - 1, pool = symbolLevel ? D.symbols.length : D.files.length;
    $("#hint").textContent = total ? `Changing ${nodeOf(focus).name} can reach ${total} ${symbolLevel ? "symbol" : "file"}${total === 1 ? "" : "s"} (${Math.round((100 * total) / Math.max(1, pool - 1))}% of the ${symbolLevel ? "symbols" : "workspace"})` : `Nothing in the workspace depends on ${nodeOf(focus).name}`;
    legend([["imports", "var(--saffron)", symbolLevel ? "called by" : "imported or called by"], ["", "", "ring = hops from the change"]]);
  }

  // ------------------------------------------------------------------ calls: symbol ego network around a file
  function drawCalls() {
    resetStage();
    const fid = (state.sel && fileOf(state.sel)) || D.insights.most_depended[0] || D.files[0].id;
    const own = [...(files.get(fid)?.symbols || [])].sort((a, b) => (syms.get(a).line - syms.get(b).line) || a.localeCompare(b));
    if (!own.length) return emptyStage("No classes or functions here", `${files.get(fid).path} has no top-level symbols to connect.`);
    const ownSet = new Set(own), callers = new Set(), callees = new Set(), edges = [];
    for (const s of own) {
      for (const t of [...get(callOut, s), ...get(inhOut, s)]) { edges.push([s, t, get(inhOut, s).includes(t) ? "inherits" : "calls"]); if (!ownSet.has(t)) callees.add(t); }
      for (const c of [...get(callIn, s), ...get(inhIn, s)]) { if (!ownSet.has(c)) { callers.add(c); edges.push([c, s, get(inhIn, s).includes(c) ? "inherits" : "calls"]); } }
    }
    const COL = 330, ROW = 34, pos = new Map();
    const column = (ids, x) => [...ids].sort().forEach((id, i, arr) => pos.set(id, { x, y: (i - (arr.length - 1) / 2) * ROW }));
    column(callers, -COL); column(own, 0); column(callees, COL);
    world.append(sv("text", { class: "lane-label", x: -COL, y: -(Math.max(callers.size, own.length, callees.size) / 2) * ROW - 24, "text-anchor": "middle", text: `callers · ${callers.size}` }));
    world.append(sv("text", { class: "lane-label", x: 0, y: -(Math.max(callers.size, own.length, callees.size) / 2) * ROW - 24, "text-anchor": "middle", text: files.get(fid).name }));
    world.append(sv("text", { class: "lane-label", x: COL, y: -(Math.max(callers.size, own.length, callees.size) / 2) * ROW - 24, "text-anchor": "middle", text: `calls out · ${callees.size}` }));
    const ge = sv("g"), gn = sv("g");
    world.append(ge, gn);
    const edgeEls = [];
    for (const [s, t, k] of edges) {
      if (!state.filters[k]) continue;
      const a = pos.get(s), b = pos.get(t);
      if (!a || !b) continue;
      const d = a.x === b.x ? `M${a.x + 70},${a.y} C${a.x + 140},${a.y} ${b.x + 140},${b.y} ${b.x + 70},${b.y}` : curve(a, b, 0.06);
      const p = sv("path", { class: "edge " + k, d, "marker-end": "url(#arrow)" });
      p.dataset.s = s; p.dataset.t = t; ge.append(p); edgeEls.push(p);
    }
    const nodeEls = new Map();
    for (const [id, p] of pos) {
      const s = syms.get(id), mine = ownSet.has(id);
      const g = sv("g", { class: "node box" + (state.sel === id ? " selected" : ""), transform: `translate(${p.x - 70},${p.y - 13})` });
      g.append(sv("rect", { width: 140, height: 26, rx: 8, fill: mine ? "var(--raise)" : "var(--panel-solid)", stroke: colorOf(s.file), "stroke-width": mine ? 1.8 : 1 }));
      g.append(sv("text", { x: 10, y: 17, text: (s.kind === "class" ? "◆ " : "ƒ ") + (s.name.length > 18 ? s.name.slice(0, 17) + "…" : s.name) }));
      g.addEventListener("mouseenter", () => hot(id)); g.addEventListener("mouseleave", () => hot(null));
      g.addEventListener("click", () => { if (!drag?.moved) select(id); });
      gn.append(g); nodeEls.set(id, g);
    }
    function hot(id) {
      svg.classList.toggle("dim", !!id);
      nodeEls.forEach((g) => g.classList.remove("hot")); edgeEls.forEach((p) => p.classList.remove("hot"));
      if (!id) { pulses([]); return; }
      nodeEls.get(id)?.classList.add("hot");
      const hotE = edgeEls.filter((p) => p.dataset.s === id || p.dataset.t === id);
      hotE.forEach((p) => { p.classList.add("hot"); nodeEls.get(p.dataset.s)?.classList.add("hot"); nodeEls.get(p.dataset.t)?.classList.add("hot"); });
      pulses(hotE);
    }
    $("#hint").textContent = `${own.length} symbols in ${files.get(fid).path} · ${callers.size} callers · ${callees.size} callees (inferred)`;
    legend([["calls", "rgba(61,214,198,.8)", "calls (inferred)"], ["inherits", "var(--rose)", "inherits"]]);
  }

  // ------------------------------------------------------------------ hotspots: squarified treemap
  function drawHotspots() {
    const box = $("#treemap");
    box.replaceChildren();
    const W = box.clientWidth || 800, H = box.clientHeight || 500;
    const items = D.files.filter((f) => f.loc > 0).map((f) => ({ f, v: f.loc })).sort((a, b) => b.v - a.v);
    if (!items.length) { box.append(el("div", { class: "empty" }, el("span", { class: "big", text: "🜂" }), "No lines to measure.")); return; }
    const maxIn = Math.max(1, ...D.files.map((f) => f.fan_in));
    const heat = (n) => { const t = n / maxIn; return t > 0.66 ? "var(--ember)" : t > 0.33 ? "var(--saffron)" : t > 0 ? "#ffd36e" : "var(--teal)"; };
    const total = items.reduce((s, i) => s + i.v, 0);
    let rect = { x: 0, y: 0, w: W, h: H }, row = [], rest = items.map((i) => ({ ...i, a: (i.v / total) * W * H }));
    const worst = (r, side) => { const s = r.reduce((t, i) => t + i.a, 0), mx = Math.max(...r.map((i) => i.a)), mn = Math.min(...r.map((i) => i.a)); return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn)); };
    const flush = () => {
      const s = row.reduce((t, i) => t + i.a, 0), horiz = rect.w >= rect.h, side = horiz ? rect.h : rect.w, thick = s / side;
      let off = 0;
      for (const i of row) {
        const len = i.a / thick;
        const cell = horiz ? { x: rect.x, y: rect.y + off, w: thick, h: len } : { x: rect.x + off, y: rect.y, w: len, h: thick };
        off += len;
        const d = el("button", { class: "tm-cell" + (fileOf(state.sel || "") === i.f.id ? " selected" : ""), title: `${i.f.path} · ${i.f.loc} lines · imported by ${i.f.fan_in}`, style: `left:${cell.x}px;top:${cell.y}px;width:${Math.max(0, cell.w - 2)}px;height:${Math.max(0, cell.h - 2)}px;background:${heat(i.f.fan_in)}`, onclick: () => select(i.f.id) });
        if (cell.w > 60 && cell.h > 26) d.append(el("b", { text: i.f.name }), el("small", { text: `${fmt(i.f.loc)} lines · ←${i.f.fan_in}` }));
        box.append(d);
      }
      if (horiz) { rect = { x: rect.x + thick, y: rect.y, w: rect.w - thick, h: rect.h }; } else { rect = { x: rect.x, y: rect.y + thick, w: rect.w, h: rect.h - thick }; }
      row = [];
    };
    while (rest.length) {
      const side = Math.min(rect.w, rect.h), next = rest[0];
      if (!row.length || worst([...row, next], side) <= worst(row, side)) { row.push(next); rest.shift(); } else flush();
    }
    if (row.length) flush();
    $("#hint").textContent = "";
    legend([["", "var(--teal)", "imported by none"], ["", "#ffd36e", "a few"], ["", "var(--saffron)", "many"], ["", "var(--ember)", "most"], ["", "", "area = lines"]]);
  }

  // ------------------------------------------------------------------ guided tour
  function tourSteps() {
    const P = D.project, steps = [{ title: "Overview", text: `${P.name}: ${fmt(P.files)} files in ${fmt(P.packages)} packages, ${fmt(P.symbols)} classes and functions, ${fmt(P.loc)} lines.`, view: "constellation" }];
    [...D.packages].sort((a, b) => b.files.length - a.files.length).slice(0, 3).forEach((p) => steps.push({ title: "Package", text: `${p.id === "." ? "The root" : p.id} holds ${p.files.length} file${p.files.length === 1 ? "" : "s"}.`, view: "constellation", pkg: p.id }));
    D.insights.entry_points.slice(0, 2).forEach((id) => steps.push({ title: "Entry point", text: `${files.get(id).path} looks like a way in: start reading here.`, view: "constellation", sel: id }));
    const top = D.insights.most_depended[0];
    if (top) steps.push({ title: "Most depended on", text: `${files.get(top).path} is imported by ${files.get(top).fan_in} files. A change here ripples furthest.`, view: "impact", sel: top });
    const big = D.insights.largest[0];
    if (big) steps.push({ title: "Largest file", text: `${files.get(big).path} has ${fmt(files.get(big).loc)} lines and ${files.get(big).symbols.length} symbols.`, view: "hotspots", sel: big });
    if (D.insights.cycles.length) steps.push({ title: "Import cycles", text: `${D.insights.cycles.length} cycle${D.insights.cycles.length === 1 ? "" : "s"}, e.g. ${D.insights.cycles[0].map((id) => files.get(id).name).join(" ↔ ")}. Cycles make modules hard to change alone.`, view: "flow", sel: D.insights.cycles[0][0] });
    if (D.external.length) steps.push({ title: "Outside world", text: `Depends on ${D.external.length} external modules, most used: ${[...D.external].sort((a, b) => b.importers.length - a.importers.length).slice(0, 5).map((e) => e.name).join(", ")}.`, view: "constellation" });
    steps.push({ title: "What this map can't see", text: D.limitations[1] || D.limitations[0], view: "constellation" });
    return steps;
  }
  let tourTimer = null, typeTimer = null;
  function runTour(i) {
    const steps = tourSteps();
    state.tour = (i + steps.length) % steps.length;
    const s = steps[state.tour];
    $("#narration").hidden = false;
    $("#tourStep").textContent = `${state.tour + 1} / ${steps.length} · ${s.title}`;
    $("#tourDots").replaceChildren(...steps.map((_, k) => el("i", { class: k <= state.tour ? "on" : "" })));
    state.sel = s.sel || null;
    renderView(s.view, true);
    if (s.pkg) spaceFocusPackage(s.pkg);
    const t = $("#tourText"); clearInterval(typeTimer);
    if (reduced) t.textContent = s.text; else { let k = 0; t.textContent = ""; typeTimer = setInterval(() => { t.textContent = s.text.slice(0, ++k); if (k >= s.text.length) clearInterval(typeTimer); }, 16); }
    clearTimeout(tourTimer);
    if (state.playing) tourTimer = setTimeout(() => runTour(state.tour + 1), 6500);
  }
  $("#tourPrev").onclick = () => runTour(state.tour - 1);
  $("#tourNext").onclick = () => runTour(state.tour + 1);
  $("#tourPlay").onclick = () => { state.playing = !state.playing; $("#tourPlay").textContent = state.playing ? "❚❚ Pause" : "▶ Play"; runTour(state.tour); };

  // ------------------------------------------------------------------ view switching
  const VIEWS = {
    constellation: { icon: "✦", label: "Constellation", desc: "Every file as a body in 3D space: imports pull, files repel, packages cluster. Drag to orbit, hover to light up a file's imports.", draw: drawConstellation },
    flow: { icon: "⇶", label: "Flow", desc: "Dependencies left to right, from entry side to foundations. Cycles glow rose.", draw: drawFlow },
    impact: { icon: "◎", label: "Impact", desc: "Blast radius: what could break if the selected file or symbol changes.", draw: drawImpact },
    calls: { icon: "ƒ", label: "Calls", desc: "Who calls into the selected file, and what it calls (inferred from imports).", draw: drawCalls },
    hotspots: { icon: "▦", label: "Hotspots", desc: "Big files that many others depend on are where changes cost the most.", draw: drawHotspots },
    tour: { icon: "☄", label: "Tour", desc: "A guided walk through this codebase.", draw: () => runTour(state.tour) },
  };
  const SERVE = JSON.parse(document.getElementById("dg-serve").textContent);
  const SHELL = JSON.parse(document.getElementById("dg-serve-shell").textContent);
  const frame = document.getElementById("serveFrame");
  const SERVE_VIEWS = {
    overview: ["#/", "◇", "Overview", "What's connected, and a line for each view of this repository."],
    codemap: ["#/map", "⌗", "Code map", "How the folders, files and functions connect, across folders."],
    e2e: ["#/flows", "⇢", "End-to-end flows", "From a request to the data, one step at a time."],
    notebooks: ["#/notebooks", "✎", "Notebooks", "What each notebook does, and how they feed each other."],
    data: ["#/data", "⛁", "Data", "An ERD of tables and fields, and the code that uses them."],
    apis: ["#/apis", "⇄", "API pathways", "Every route, who calls it, and calls that lead nowhere."],
    architecture: ["#/architecture", "▣", "Architecture", "A CALM model inferred from the repository."],
    quality: ["#/quality", "◈", "Quality", "Complexity, size and tests."],
    coverage: ["#/coverage", "▤", "Coverage", "What the tests cover, per file."],
    cves: ["#/cves", "⚠", "CVEs", "Known vulnerabilities in dependencies, and what fixes them."],
    findings: ["#/findings", "⚑", "Findings", "What scanners and test runs reported, and what to fix first."],
    certainty: ["#/certainty", "≈", "What's certain", "How far to trust each view, and what the analysis couldn't tell."],
    tokens: ["#/context", "✂", "Saving tokens", "A small map of this repository for an AI assistant."],
    code: ["#/code", "⌘", "Code", "Browse the code graph by folder, file or symbol."],
    runs: ["#/runs", "▶", "Runs", "What ran to make this report."],
    capabilities: ["#/sources", "❖", "Capabilities", "What your sources offer."],
    workflows: ["#/workflows", "⛓", "Workflows", "Put capabilities in order, and see what would run."],
    documents: ["#/docs", "❏", "Documentation", "Decks and diagrams from your Markdown."],
    learning: ["#/learning", "✓", "Learning review", "What was learned, before it becomes reusable."],
  };
  if (SERVE) {
    window.DEV_GURU_REPORT = SERVE;
    const hasNotebooks = (SERVE.intel.sections?.notebooks?.notebooks || []).length > 0;
    for (const [id, [route, icon, label, desc]] of Object.entries(SERVE_VIEWS)) {
      if (id === "notebooks" && !hasNotebooks) continue;
      VIEWS[id] = { icon, label, desc, serve: route, draw: () => {} };
    }
  }
  let frameReady = false;
  const frameTheme = () => { try { frame.contentDocument.documentElement.dataset.theme = document.documentElement.dataset.theme === "day" ? "light" : "dark"; } catch { /* not loaded yet */ } };
  function openServe(route) {
    if (frameReady) { frameTheme(); frame.contentWindow.location.hash = route; return; }
    if (frame.srcdoc) { frame.dataset.next = route; return; }
    frame.dataset.next = route;
    frame.addEventListener("load", () => {
      frameReady = true;
      frameTheme();
      frame.contentWindow.location.hash = frame.dataset.next;
      // a link inside a page moves to another view, so the tabs follow it
      frame.contentWindow.addEventListener("hashchange", () => {
        const section = `#/${frame.contentWindow.location.hash.replace(/^#\/?/, "").split(/[/?]/)[0]}`;
        const found = Object.entries(VIEWS).find(([, v]) => v.serve === section);
        if (found && state.view !== found[0]) { state.view = found[0]; markTabs(found[0]); $("#viewTitle").textContent = found[1].label; syncHash(); }
      });
    }, { once: true });
    frame.srcdoc = SHELL;
  }
  if (D.repository && !SERVE) VIEWS.repository = { icon: "▤", label: "Repository", desc: "Every section of the repository analysis: components, routes, tables, flows, quality, coverage and vulnerabilities.", draw: drawRepository };
  function drawRepository() {
    const R = D.repository, box = $("#repoView");
    const table = (id, heads, rows) => el("table", { id }, el("thead", {}, el("tr", {}, ...heads.map((h) => el("th", { text: h })))),
      el("tbody", {}, ...rows.map((r) => el("tr", {}, ...r.map((c) => el("td", { text: c === null || c === undefined ? "" : String(c) }))))));
    const part = (title, heads, rows, id, empty) => [el("h2", { text: title }), rows.length ? table(id, heads, rows) : el("p", { class: "muted", text: empty })];
    const card = (value, label) => el("div", {}, el("b", { text: value === null || value === undefined ? "Unknown" : String(value) }), label);
    const t = R.totals || {}, cov = R.coverage || {}, deps = R.dependencies || {};
    const covered = typeof cov.line_rate === "number" ? `${Math.round(cov.line_rate * 100)}%` : "Unknown";
    const held = R.reduced ? "Left out of a public report." : "None found in this analysis.";
    const vulns = deps.vulnerabilities === null || deps.vulnerabilities === undefined
      ? [el("h2", { text: "Vulnerabilities" }), el("p", { id: "repo-cves-unknown", text: R.reduced ? "Left out of a public report." : "Not checked, which doesn't mean there are none. A report makes no network requests. Run dev serve and ask for a check." })]
      : part("Vulnerabilities", ["Package", "Version", "Severity", "Advisory", "Fixed in"], deps.vulnerabilities, "repo-cves", "None known, as of this analysis.");
    box.replaceChildren(
      el("div", { class: "repo-cards", id: "repo-cards" }, card(R.files, "Files"), card(R.loc, "Lines"), card(R.routes_total, "Routes"), card(R.tables_total, "Tables"), card(R.flows_total, "Flows"), card(t.avg_complexity, "Average complexity"), card(covered, "Line coverage")),
      ...part("Components", ["Name", "Kind", "Language", "Files"], R.components, "repo-components", held),
      ...part("How they connect (inferred)", ["From", "To", "How", "Evidence"], R.links, "repo-links", held),
      ...part("Routes", ["Method", "Path", "Handler", "Called from"], R.routes, "repo-routes", held),
      ...(R.unmatched.length ? part("Calls to routes that don't exist here", ["Method", "Path", "From"], R.unmatched, "repo-unmatched", "") : []),
      ...part("Tables", ["Table", "Fields"], R.tables, "repo-tables", held),
      ...part("Relationships", ["From", "To"], R.relationships, "repo-relationships", held),
      ...part("End-to-end flows", ["Flow"], R.flows.map((f) => [f]), "repo-flows", held),
      ...part("Most complex functions", ["Function", "Complexity", "Where"], R.hotspots, "repo-hotspots", held),
      ...vulns);
  }
  const tabs = $("#tabs");
  for (const [id, v] of Object.entries(VIEWS)) tabs.append(el("button", { class: `tab${id === "overview" ? " group-start" : ""}`, role: "tab", "data-view": id, "aria-selected": "false", onclick: () => { if (id !== "tour") { clearTimeout(tourTimer); $("#narration").hidden = true; } renderView(id); } }, el("span", { class: "ic", "aria-hidden": "true", text: v.icon }), v.label));
  function renderView(id, fromTour) {
    if (!VIEWS[id]) id = "constellation";
    if (!fromTour) state.view = id;
    const served = VIEWS[id].serve;
    document.querySelector(".workspace").hidden = !!served;
    frame.hidden = !served;
    if (served) {
      space.active = false; cancelAnimationFrame(space.raf); space.raf = 0;
      markTabs(id); document.title = `${VIEWS[id].label} · ${D.project?.name || "Dev Guru"}`;
      openServe(served); syncHash();
      return;
    }
    if (id === "tour") { state.view = "tour"; markTabs("tour"); return VIEWS.tour.draw(); }
    markTabs(fromTour ? "tour" : id);
    $("#viewTitle").textContent = VIEWS[id].label;
    $("#viewDesc").textContent = VIEWS[id].desc;
    const tm = id === "hotspots", s3 = id === "constellation";
    if (!s3) { space.active = false; cancelAnimationFrame(space.raf); space.raf = 0; }
    const repo = id === "repository"; $("#repoView").hidden = !repo;
    $("#treemap").hidden = !tm; cvs.hidden = !s3; svg.style.display = tm || s3 || repo ? "none" : "block"; $("#zoomTools").hidden = tm;
    toolsFor(id);
    $("#hint").textContent = "";
    VIEWS[id].draw();
    if (s3) { if (state.sel) spaceFocus(fileOf(state.sel)); else if (!space.moved) spaceFit(); }
    else if (!tm) fit();
    inspect(state.sel);
    syncHash();
  }
  function markTabs(id) { tabs.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.view === id))); }
  function toolsFor(id) {
    const box = $("#stageTools"); box.replaceChildren();
    const keys = id === "constellation" || id === "flow" ? ["imports"] : id === "calls" ? ["calls", "inherits"] : [];
    for (const k of keys) box.append(el("button", { class: "chip", "aria-pressed": String(state.filters[k]), text: k, onclick: () => { state.filters[k] = !state.filters[k]; renderView(state.view === "tour" ? "constellation" : state.view); } }));
    if (id === "flow") for (const lvl of ["packages", "files"]) box.append(el("button", { class: "chip", "aria-pressed": String((state.flowLevel || (D.files.length > 120 ? "packages" : "files")) === lvl), text: lvl, onclick: () => { state.flowLevel = lvl; renderView("flow"); } }));
    if (id === "impact" || id === "calls") box.append(el("span", { class: "muted", text: state.sel ? "" : "Select a file or symbol to focus" }));
  }
  function legend(items) {
    const L = $("#legend"); L.replaceChildren();
    for (const [, color, label] of items) if (label) L.append(el("span", {}, color ? el("i", { style: `background:${color}` }) : "", label));
    L.hidden = !L.childElementCount;
  }
  function emptyStage(title, text) {
    world.append(sv("text", { x: 0, y: 0, "text-anchor": "middle", class: "pkg-label", text: title }));
    world.append(sv("text", { x: 0, y: 22, "text-anchor": "middle", class: "ring-label", text }));
    legend([]);
  }

  // ------------------------------------------------------------------ selection and inspector
  function select(id) {
    state.sel = id && nodeOf(id) ? id : null;
    if (state.view !== "tour") renderView(state.view); else inspect(state.sel);
    document.querySelectorAll(".tree-item").forEach((t) => t.setAttribute("aria-current", String(t.dataset.id === (state.sel && fileOf(state.sel)))));
    if (window.innerWidth <= 1180 && state.sel) $("#inspector").classList.add("open");
    syncHash();
  }
  const link = (id, where) => { const n = nodeOf(id); return n ? el("button", { class: "link", onclick: () => select(id) }, el("span", { class: "dot", style: `color:${colorOf(fileOf(id))}` }), el("span", { class: "kind " + (n.kind || "file"), text: n.kind || "file" }), el("span", { text: n.name }), where ? el("span", { class: "where", text: where }) : "") : null; };
  const section = (title, kids) => (kids.filter(Boolean).length ? [el("h3", { class: "eyebrow", text: title }), el("div", { class: "links" }, kids)] : []);
  function inspect(id) {
    const body = $("#inspectBody"); body.replaceChildren();
    const close = el("button", { class: "btn icon", "aria-label": "Close inspector", text: "✕", onclick: () => $("#inspector").classList.remove("open"), style: "margin-left:auto" });
    if (!id) {
      const P = D.project;
      body.append(
        el("div", { class: "ins-head" }, el("h2", { text: P.name }), close),
        el("p", { class: "muted", text: "Pick anything in the graph, the tree or search to see its source, contract and connections." }),
        el("div", { class: "facts" }, ...[["files", P.files], ["symbols", P.symbols], ["lines", P.loc], ["imports", P.imports], ["calls", P.calls], ["external", P.external]].map(([k, v]) => el("div", { class: "fact" }, el("b", { text: fmt(v) }), el("span", { text: k })))),
        ...section("Most depended on", D.insights.most_depended.slice(0, 6).map((f) => link(f, `← ${files.get(f).fan_in}`))),
        ...section("Entry points", D.insights.entry_points.slice(0, 6).map((f) => link(f))),
        el("h3", { class: "eyebrow", text: "How to read this" }),
        el("ul", { class: "muted" }, el("li", { text: "Each sphere is a file; size is lines of code, colour is the package." }), el("li", { text: "Lines join a file to what it imports. In the constellation, drag to orbit and scroll to zoom." }), el("li", { text: "Calls and inheritance are inferred statically by Ananke and may miss dynamic dispatch." })),
      );
      return;
    }
    const f = files.get(id);
    if (f) {
      body.append(
        el("div", { class: "ins-head" }, el("span", { class: "kind file", text: "file" }), el("div", {}, el("h2", { text: f.name }), el("div", { class: "ins-path mono", text: f.path })), close),
        f.doc ? el("div", { class: "ins-doc", text: f.doc }) : "",
        el("div", { class: "facts" }, el("div", { class: "fact" }, el("b", { text: fmt(f.loc) }), el("span", { text: "lines" })), el("div", { class: "fact" }, el("b", { text: f.fan_in }), el("span", { text: "imported by" })), el("div", { class: "fact" }, el("b", { text: f.fan_out }), el("span", { text: "imports" }))),
        el("div", { class: "actions" },
          el("button", { class: "btn primary", text: "◎ Impact", onclick: () => renderView("impact") }),
          el("button", { class: "btn", text: "ƒ Calls", onclick: () => renderView("calls") }),
          el("button", { class: "btn", text: "⇶ Flow", onclick: () => renderView("flow") }),
          el("button", { class: "btn", text: "⧉ Copy path", onclick: () => copy(f.path, "Path copied") })),
        f.parse_error ? el("p", { class: "ins-doc", text: "Ananke couldn't parse this file, so its symbols aren't shown." }) : "",
        cycleFiles.has(f.id) ? el("p", { class: "ins-doc", text: "Part of an import cycle (see Flow)." }) : "",
        ...section(`Symbols · ${f.symbols.length}`, f.symbols.map((s) => link(s, `L${syms.get(s).line}`))),
        ...section(`Imported by · ${f.fan_in}`, get(inn, f.id).sort().map((x) => link(x))),
        ...section(`Imports · ${f.fan_out}`, get(out, f.id).sort().map((x) => link(x))),
        f.external.length ? el("h3", { class: "eyebrow", text: "External modules" }) : "",
        f.external.length ? el("div", { class: "tagline" }, ...f.external.map((m) => el("span", { class: "tag mono", text: m }))) : "",
      );
      return;
    }
    const s = syms.get(id);
    const file = files.get(s.file);
    const src = el("pre", { class: "src", "aria-label": "Source" });
    (s.source || "").split("\n").forEach((line, i) => src.append(el("span", { "data-ln": s.line + i, text: line || " " })));
    body.append(
      el("div", { class: "ins-head" }, el("span", { class: "kind " + s.kind, text: s.kind }), el("div", {}, el("h2", { text: s.name }), el("div", { class: "ins-path mono", text: `${file ? file.path : ""}:${s.line}` })), close),
      s.signature ? el("div", { class: "sig mono", text: s.signature }) : "",
      s.doc ? el("div", { class: "ins-doc", text: s.doc }) : "",
      el("div", { class: "facts" }, el("div", { class: "fact" }, el("b", { text: s.calls_in }), el("span", { text: "called by" })), el("div", { class: "fact" }, el("b", { text: s.calls_out }), el("span", { text: "calls" })), el("div", { class: "fact" }, el("b", { text: Math.max(1, s.end_line - s.line + 1) }), el("span", { text: "lines" }))),
      el("div", { class: "actions" },
        el("button", { class: "btn primary", text: "◎ Who's affected", onclick: () => renderView("impact") }),
        el("button", { class: "btn", text: "ƒ Calls", onclick: () => renderView("calls") }),
        file ? el("button", { class: "btn", text: "↑ File", onclick: () => select(file.id) }) : "",
        el("button", { class: "btn", text: "⤓ Ask for deeper analysis", onclick: () => requestAnalysis(s.id) })),
      s.source ? el("h3", { class: "eyebrow", text: "Source" }) : "",
      s.source ? src : "",
      ...section("Called by", get(callIn, s.id).sort().map((x) => link(x, files.get(fileOf(x))?.name))),
      ...section("Calls", get(callOut, s.id).sort().map((x) => link(x, files.get(fileOf(x))?.name))),
      ...section("Inherits from", get(inhOut, s.id).map((x) => link(x))),
      ...section("Subclassed by", get(inhIn, s.id).map((x) => link(x))),
    );
  }

  // ------------------------------------------------------------------ sidebar: insights, tree, search
  function buildSidebar() {
    $("#projectName").textContent = D.project.name;
    const P = D.project;
    $("#stats").replaceChildren(...[["files", P.files], ["packages", P.packages], ["symbols", P.symbols], ["lines", P.loc], ["imports", P.imports], ["calls", P.calls], ["external", P.external]].map(([k, v]) => el("div", { class: "stat" }, el("b", { text: fmt(v) }), el("span", { text: k }))),
      D.insights.cycles.length ? el("div", { class: "stat warn" }, el("b", { text: D.insights.cycles.length }), el("span", { text: "import cycles" })) : "");
    const ins = $("#insights"); ins.replaceChildren(el("h2", { class: "eyebrow", text: "Start here" }));
    const card = (label, text, onclick) => ins.append(el("button", { class: "insight", onclick }, el("b", { text: label }), el("span", { text })));
    card("Guided tour", "Walk through this codebase step by step", () => renderView("tour"));
    if (D.insights.most_depended[0]) card("Most depended on", files.get(D.insights.most_depended[0]).path, () => { state.view = "impact"; select(D.insights.most_depended[0]); });
    if (D.insights.cycles.length) card("Import cycles", `${D.insights.cycles.length} found`, () => { state.view = "flow"; select(D.insights.cycles[0][0]); });
    if (D.insights.largest[0]) card("Largest file", files.get(D.insights.largest[0]).path, () => { state.view = "hotspots"; select(D.insights.largest[0]); });
    const tree = $("#tree"); tree.replaceChildren();
    for (const p of D.packages) {
      const kids = el("div", { class: "tree-children", role: "group", hidden: D.packages.length > 6 ? true : false });
      const head = el("button", { class: "tree-item tree-pkg", role: "treeitem", "aria-expanded": String(D.packages.length <= 6), onclick: () => { kids.hidden = !kids.hidden; head.setAttribute("aria-expanded", String(!kids.hidden)); } },
        el("span", { class: "dot", style: `color:${PALETTE[pkgIndex.get(p.id) % PALETTE.length]}` }), el("span", { text: p.id === "." ? "(root)" : p.id }), el("span", { class: "count", text: p.files.length }));
      for (const fid of p.files) kids.append(el("button", { class: "tree-item", role: "treeitem", "data-id": fid, onclick: () => select(fid) }, el("span", { text: files.get(fid).name }), el("span", { class: "count", text: fmt(files.get(fid).loc) })));
      tree.append(head, kids);
    }
  }
  const searchIndex = [...D.files.map((f) => ({ id: f.id, name: f.name, hay: f.path.toLowerCase(), kind: "file", where: f.package })), ...D.symbols.map((s) => ({ id: s.id, name: s.name, hay: s.name.toLowerCase(), kind: s.kind, where: files.get(s.file)?.name || "" }))];
  function find(q, limit = 30) {
    q = q.trim().toLowerCase();
    if (!q) return [];
    const scored = [];
    for (const it of searchIndex) { const i = it.hay.indexOf(q); if (i < 0) continue; scored.push([(it.name.toLowerCase().startsWith(q) ? 0 : 1) * 1000 + i * 10 + it.name.length, it]); }
    return scored.sort((a, b) => a[0] - b[0] || a[1].id.localeCompare(b[1].id)).slice(0, limit).map((x) => x[1]);
  }
  const search = $("#search"), results = $("#results");
  let active = 0;
  function showResults() {
    const hits = find(search.value);
    results.hidden = !search.value;
    results.replaceChildren(...(hits.length ? hits.map((h, i) => el("button", { class: "result", role: "option", "aria-selected": String(i === active), onclick: () => { select(h.id); search.value = ""; showResults(); search.blur(); } }, el("span", { class: "kind " + h.kind, text: h.kind }), el("span", { text: h.name }), el("span", { class: "where", text: h.where }))) : [el("div", { class: "empty", text: "Nothing matches" })]));
  }
  search.addEventListener("input", () => { active = 0; showResults(); });
  search.addEventListener("keydown", (e) => {
    const opts = results.querySelectorAll(".result");
    if (e.key === "ArrowDown") { active = Math.min(opts.length - 1, active + 1); showResults(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { active = Math.max(0, active - 1); showResults(); e.preventDefault(); }
    else if (e.key === "Enter" && opts[active]) opts[active].click();
    else if (e.key === "Escape") { search.value = ""; showResults(); search.blur(); }
  });
  $("#searchBtn").onclick = () => search.focus();

  // ------------------------------------------------------------------ command palette
  const palette = $("#palette"), pInput = $("#paletteInput"), pList = $("#paletteList");
  const commands = () => [
    ...Object.entries(VIEWS).map(([id, v]) => ({ label: `${v.icon}  Go to ${v.label}`, run: () => renderView(id) })),
    { label: "◐  Toggle theme", run: toggleTheme },
    { label: "⤢  Fit to screen", run: () => fit() },
    { label: "⧉  Copy a link to this view", run: () => copy(location.href, "Link copied") },
    { label: "⤓  Download this view's state (JSON)", run: downloadState },
    { label: "⤓  Ask for deeper analysis of the selection", run: () => requestAnalysis(state.sel) },
    { label: "ⓘ  About this report and its limitations", run: about },
  ];
  let pActive = 0;
  function renderPalette() {
    const q = pInput.value.toLowerCase();
    const cmds = commands().filter((c) => c.label.toLowerCase().includes(q));
    const hits = find(pInput.value, 12).map((h) => ({ label: `${h.kind === "file" ? "▤" : "ƒ"}  ${h.name}  ·  ${h.where}`, run: () => select(h.id) }));
    const all = [...cmds, ...hits];
    pActive = Math.min(pActive, Math.max(0, all.length - 1));
    pList.replaceChildren(...all.map((c, i) => el("button", { class: "pl-item", role: "option", "aria-selected": String(i === pActive), onclick: () => { closePalette(); c.run(); } }, c.label)));
  }
  const openPalette = () => { palette.hidden = false; pInput.value = ""; pActive = 0; renderPalette(); pInput.focus(); };
  const closePalette = () => { palette.hidden = true; };
  pInput.addEventListener("input", () => { pActive = 0; renderPalette(); });
  pInput.addEventListener("keydown", (e) => {
    const n = pList.children.length;
    if (e.key === "ArrowDown") { pActive = (pActive + 1) % Math.max(1, n); renderPalette(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { pActive = (pActive - 1 + n) % Math.max(1, n); renderPalette(); e.preventDefault(); }
    else if (e.key === "Enter") pList.children[pActive]?.click();
    else if (e.key === "Escape") closePalette();
  });
  palette.addEventListener("click", (e) => { if (e.target === palette) closePalette(); });
  $("#paletteBtn").onclick = openPalette;

  // ------------------------------------------------------------------ about, theme, exports, toast
  function about() {
    const b = $("#aboutBody");
    const pre = el("pre", { class: "manifest mono", text: JSON.stringify(M, null, 2) });
    b.replaceChildren(
      el("h2", { id: "aboutTitle", text: "About this report" }),
      el("p", { text: "Generated by Dev Guru from the code graph Ananke Plexus built for this workspace. It works offline and is view-only: it never runs commands or contacts a server." }),
      el("h3", { class: "eyebrow", text: "Limitations" }),
      el("ul", {}, ...D.limitations.map((l) => el("li", { text: l }))),
      el("h3", { class: "eyebrow", text: "Keyboard" }),
      el("ul", {}, el("li", { text: "/  search · Ctrl/⌘ K  commands · 1–6  views · F  fit · T  theme · Esc  close" })),
      el("h3", { class: "eyebrow", text: "Manifest" }), pre,
      el("p", {}, el("button", { class: "btn", text: "Close", onclick: () => ($("#about").hidden = true) })),
    );
    $("#about").hidden = false;
  }
  $("#about").addEventListener("click", (e) => { if (e.target.id === "about") $("#about").hidden = true; });
  $("#infoBtn").onclick = about;
  function toggleTheme() { const r = document.documentElement; r.dataset.theme = r.dataset.theme === "day" ? "night" : "day"; frameTheme(); space.theme = null; wake(); syncHash(); }
  $("#themeBtn").onclick = toggleTheme;
  function download(name, obj) {
    const a = el("a", { download: name, href: URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" })) });
    document.body.append(a); a.click(); a.remove();
    toast(`Saved ${name}`);
  }
  const downloadState = () => download("dev-guru-view.json", { schema: "dev-guru/view-state@1", report: M.input_digest, view: state.view, selection: state.sel, filters: state.filters });
  function requestAnalysis(id) {
    download("dev-guru-analysis-request.json", {
      schema: "dev-guru/analysis-request@1",
      note: "Run this with Dev Guru or Ananke; the report itself never executes anything.",
      workspace: M.workspace, report_digest: M.input_digest, target: id || null,
      requested: id ? ["impact", "callers", "tests-covering"] : ["full-explore"],
      suggested_command: `dev explore ${id ? "--focus " + JSON.stringify(id) : ""}`.trim(),
    });
  }
  async function copy(text, done) {
    try { await navigator.clipboard.writeText(text); toast(done); }
    catch (_) { window.prompt("Copy:", text); }
  }
  let toastTimer;
  function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 1800); }

  // ------------------------------------------------------------------ footer and keyboard
  const rev = M.workspace && M.workspace.commit ? `${M.workspace.commit.slice(0, 8)}${M.workspace.dirty ? " (uncommitted changes)" : ""}` : "not a git checkout";
  $("#foot").replaceChildren(
    el("span", {}, el("b", { text: "Dev Guru " }), String(M.dev_guru)), el("span", {}, el("b", { text: "Ananke " }), String(M.ananke)),
    el("span", {}, el("b", { text: "revision " }), rev), el("span", {}, el("b", { text: "input " }), String(M.input_digest).slice(0, 19) + "…"),
    el("span", {}, el("b", { text: "generated " }), String(M.generated_at)), el("span", { text: "offline · view-only" }),
  );
  document.addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA/.test(document.activeElement?.tagName || "");
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); palette.hidden ? openPalette() : closePalette(); return; }
    if (e.key === "Escape") { closePalette(); $("#about").hidden = true; $("#inspector").classList.remove("open"); return; }
    if (typing) return;
    if (e.key === "/") { e.preventDefault(); search.focus(); }
    else if (e.key >= "1" && e.key <= "6") renderView(Object.keys(VIEWS)[+e.key - 1]);
    else if (e.key.toLowerCase() === "f") fit();
    else if (e.key.toLowerCase() === "t") toggleTheme();
    else if (state.view === "tour" && e.key === "ArrowRight") runTour(state.tour + 1);
    else if (state.view === "tour" && e.key === "ArrowLeft") runTour(state.tour - 1);
  });
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (state.view === "hotspots") drawHotspots(); else if (space.active) { sizeSpace(); wake(); } else fit(); }, 150); });

  buildSidebar();
  renderView(state.view);
  if (state.sel) select(state.sel);
  window.__devGuru = { state, D, M, renderView, select, find, space: spaceProbe };
})();
