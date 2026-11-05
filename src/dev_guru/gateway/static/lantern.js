// What every page shares with the explorer's views: a rail on the left, a live stage in the middle and an inspector on the
// right, with the same pulses, hover and walk-through. It draws only what a page hands it, and all text stays text.
"use strict";

(() => {
  const { el } = window.DevGuru;
  const SVG = "http://www.w3.org/2000/svg";
  const svg = (tag, attrs, ...children) => {
    const node = document.createElementNS(SVG, tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (key === "text") node.textContent = value;
      else if (value !== undefined && value !== null) node.setAttribute(key, value);
    }
    node.append(...children);
    return node;
  };
  const short = (text, max) => (String(text).length > max ? `${String(text).slice(0, max - 1)}…` : String(text));
  const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const railNode = () => document.querySelector("#rail");
  const dockNode = () => document.querySelector("#dock");
  const TONES = { saffron: "var(--saffron)", ember: "var(--ember)", teal: "var(--teal)", violet: "var(--violet)", rose: "var(--rose)", lime: "var(--lime)", faint: "var(--faint)" };
  const SEVERITY_TONE = { critical: "rose", high: "ember", moderate: "saffron", medium: "saffron", low: "teal", note: "teal", unknown: "faint" };
  const CYCLE = ["saffron", "teal", "violet", "rose", "lime", "ember"];
  const toneOf = (index) => CYCLE[index % CYCLE.length];
  let stopWalk = null;

  function waiting(text) {
    return el("div", { class: "empty" }, el("span", { class: "big flame-big", "aria-hidden": "true" }), el("p", { text }));
  }

  // A new page starts clean, and never leaves a side empty.
  function reset() {
    if (stopWalk) stopWalk();
    stopWalk = null;
    const rail = railNode();
    const dock = dockNode();
    if (rail) rail.replaceChildren(el("p", { class: "eyebrow", text: "In this view" }), el("p", { class: "muted rail-note", text: "Nothing to list yet." }));
    if (dock) dock.replaceChildren(waiting("Select something to see it here."));
  }

  function tools(...nodes) {
    document.querySelector("#stageTools")?.append(...nodes.filter(Boolean));
  }

  const dock = (...nodes) => dockNode()?.replaceChildren(...nodes.filter(Boolean));

  // The inspector's own look: a heading, where it is, a note, a few numbers, then sections.
  function detail({ title, where, note, facts, tags, actions }, ...rest) {
    return el("div", { class: "detail" },
      el("h2", { text: title }),
      where ? el("p", { class: "ins-path mono", text: where }) : null,
      tags && tags.length ? el("div", { class: "tagline" }, ...tags.filter(Boolean).map((t) => (t instanceof Node ? t : el("span", { class: "tag", text: t })))) : null,
      note ? el("p", { class: "ins-doc", text: note }) : null,
      facts && facts.length ? el("div", { class: "facts" }, ...facts.map(([value, label]) => el("div", { class: "fact" }, el("b", { text: value === null || value === undefined ? "?" : String(value) }), el("span", { text: label })))) : null,
      actions && actions.length ? el("div", { class: "actions" }, ...actions.filter(Boolean)) : null,
      ...rest);
  }
  const linkList = (title, rows) => (rows.length
    ? [el("h3", { class: "eyebrow", text: `${title} (${rows.length})` }), el("ul", { class: "links" }, ...rows.map((row) => el("li", {}, row)))]
    : []);

  // ---------------------------------------------------------------- rail
  function rail({ groups, onSelect, search, placeholder, insights, searchId, note }) {
    const root = railNode();
    if (!root) return { select() {}, ids: [] };
    const rows = new Map();
    const box = el("div", { class: "rail-groups" });
    const makeRow = (item, index) => {
      const dot = el("span", { class: "dot" });
      dot.style.color = TONES[item.tone || toneOf(index)] || TONES.saffron;
      const inner = [dot, el("span", { class: "tree-label" }, el("span", { class: "tree-name", text: item.label }), item.sub ? el("small", { text: item.sub }) : null),
        item.count !== undefined && item.count !== null ? el("span", { class: "count", text: String(item.count) }) : null];
      const row = item.href
        ? el("a", { class: "tree-item", href: item.href }, ...inner)
        : el("button", { type: "button", class: "tree-item", on: { click: () => { if (stopWalk) stopWalk(); onSelect?.(item.id); mark(item.id); } } }, ...inner);
      row.dataset.row = item.id;
      rows.set(item.id, { row, text: `${item.label} ${item.sub || ""}`.toLowerCase() });
      return row;
    };
    const mark = (id) => {
      for (const [key, { row }] of rows) {
        if (key === id) {
          row.setAttribute("aria-current", "true");
          const top = row.offsetTop - root.offsetTop;
          if (top < root.scrollTop || top > root.scrollTop + root.clientHeight - 40) root.scrollTop = Math.max(0, top - 60);
        } else row.removeAttribute("aria-current");
      }
    };
    box.append(...groups.flatMap((group, g) => {
      if (!group.items.length) return [];
      const items = group.items.map((item, i) => makeRow(item, g + i));
      return [group.title ? el("h2", { class: "eyebrow", text: group.title }) : null, el("div", { class: "tree" }, ...items)].filter(Boolean);
    }));
    if (!rows.size) box.append(el("p", { class: "muted rail-note", text: note || "Nothing to list." }));
    const finder = search ? el("input", { id: searchId, type: "search", placeholder: placeholder || "Find", "aria-label": placeholder || "Find", autocomplete: "off",
      on: { input: (e) => {
        const words = e.target.value.toLowerCase();
        for (const { row, text } of rows.values()) row.hidden = !text.includes(words);
        for (const tree of box.querySelectorAll(".tree")) {
          const seen = [...tree.children].some((child) => !child.hidden);
          tree.hidden = !seen;
          if (tree.previousElementSibling?.classList.contains("eyebrow")) tree.previousElementSibling.hidden = !seen;
        }
      } } }) : null;
    const notes = (insights || []).filter(Boolean).map((item) => (item.href
      ? el("a", { class: "insight", href: item.href }, el("b", { text: item.title }), el("span", { text: item.text }))
      : el("button", { type: "button", class: "insight", on: { click: item.onClick } }, el("b", { text: item.title }), el("span", { text: item.text }))));
    root.replaceChildren(...[
      finder ? el("label", { class: "search" }, el("span", { "aria-hidden": "true", text: "⌕" }), finder) : null,
      notes.length ? el("section", { class: "insights", "aria-label": "Start here" }, el("h2", { class: "eyebrow", text: "Start here" }), ...notes) : null,
      box].filter(Boolean));
    return { select: mark, ids: [...rows.keys()] };
  }

  // ---------------------------------------------------------------- stage
  function stage({ id, legend, hint, compact } = {}) {
    const body = el("div", { class: "stage-body" });
    const root = el("div", { class: `lstage${compact ? " compact" : ""}`, id }, body);
    const key = legend && legend.length ? el("div", { class: "legend", "aria-hidden": "true" }, ...legend.map(([text, tone, dashed]) => {
      const mark = el("i", { class: dashed ? "dashed" : "" });
      mark.style.color = TONES[tone] || TONES.saffron;
      return el("span", {}, mark, text);
    })) : null;
    if (key) root.append(key);
    const note = el("div", { class: "hint", text: hint || "" });
    root.append(note);
    return { el: root, body, hint: (text) => { note.textContent = text; },
      fill: (...nodes) => { body.replaceChildren(...nodes); return root; } };
  }

  function nothing(main, title, text) {
    const shown = stage({ compact: true });
    shown.fill(waiting(text));
    main.append(shown.el);
    rail({ groups: [], note: title });
    dock(waiting(text));
  }

  // ---------------------------------------------------------------- motion
  // Light travelling along the lines. It stops by itself when the drawing leaves the page, and never starts for reduced motion.
  function pulses(layer, paths) {
    if (layer.dgStop) layer.dgStop();
    layer.replaceChildren();
    if (still() || !paths.length) return;
    let frame = 0;
    const dots = paths.slice(0, 40).map((path, i) => {
      let length = 0;
      try { length = path.getTotalLength(); } catch { /* not laid out */ }
      const dot = svg("circle", { r: 3.2, class: "pulse" });
      layer.append(dot);
      return { path, length, offset: (i * 0.17) % 1, dot };
    });
    const started = performance.now();
    const step = (now) => {
      if (!layer.isConnected) return;
      for (const d of dots) {
        const at = ((now - started) / 1500 + d.offset) % 1;
        try {
          const point = d.path.getPointAtLength(at * (d.length || d.path.getTotalLength()));
          d.dot.setAttribute("cx", point.x);
          d.dot.setAttribute("cy", point.y);
          d.dot.setAttribute("opacity", Math.sin(at * Math.PI).toFixed(2));
        } catch { /* hidden for now */ }
      }
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    layer.dgStop = () => cancelAnimationFrame(frame);
  }

  // Hover lights a thing's neighbours and sends light along their lines, as in the explorer. A pinned set holds until cleared.
  function fx(canvas) {
    const nodes = [...canvas.querySelectorAll("[data-id]")];
    const lines = [...canvas.querySelectorAll("path[data-source]")];
    nodes.forEach((node, i) => node.style.setProperty("--i", String(Math.min(i, 30))));
    const layer = svg("g", { class: "pulses", "aria-hidden": "true" });
    canvas.append(layer);
    let pinned = null;
    const paint = (ids, hotLines, current) => {
      for (const node of nodes) {
        node.classList.toggle("dim", ids !== null && !ids.has(node.dataset.id));
        node.classList.toggle("hot", ids !== null && ids.has(node.dataset.id));
        node.classList.toggle("selected", current !== undefined && current !== null && node.dataset.id === current);
      }
      for (const line of lines) {
        const hot = ids !== null && hotLines.includes(line);
        line.classList.toggle("dim", ids !== null && !hot);
        line.classList.toggle("hot", hot);
      }
      pulses(layer, ids === null || !hotLines.length ? lines.slice(0, 24) : hotLines);
    };
    const touching = (id) => {
      const hotLines = lines.filter((l) => l.dataset.source === id || l.dataset.target === id);
      return { ids: new Set([id, ...hotLines.flatMap((l) => [l.dataset.source, l.dataset.target])]), hotLines };
    };
    const rest = () => {
      if (!pinned) { paint(null, []); return; }
      paint(pinned.ids, pinned.hotLines, pinned.current);
    };
    for (const node of nodes) {
      const id = node.dataset.id;
      const enter = () => { const t = touching(id); paint(t.ids, t.hotLines, pinned?.current); };
      node.addEventListener("mouseenter", enter);
      node.addEventListener("focus", enter);
      node.addEventListener("mouseleave", rest);
      node.addEventListener("blur", rest);
    }
    rest();
    return {
      // lights exactly these things, and the lines between them
      pin(ids, current) {
        if (ids === null) pinned = null;
        else pinned = { ids, current, hotLines: lines.filter((l) => ids.has(l.dataset.source) && ids.has(l.dataset.target)) };
        rest();
      },
      // lights one thing and all it touches
      focus(id) {
        pinned = { ...touching(id), current: id };
        rest();
      },
    };
  }

  // ---------------------------------------------------------------- pictures
  const pressable = (node, label, act) => {
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", "button");
    node.setAttribute("aria-label", label);
    node.addEventListener("click", act);
    node.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); act(); } });
    return node;
  };

  // A core with rings of things round it, each joined by a line.
  function radial({ center, sub, items, onSelect, label, more }) {
    const WIDTH = 960;
    const capacity = [12, 16, 22];
    const rings = [];
    let rest = [...items];
    for (let r = 0; r < capacity.length && rest.length; r++) {
      rings.push(rest.slice(0, capacity[r]));
      rest = rest.slice(capacity[r]);
    }
    const HEIGHT = rings.length > 2 ? 620 : (rings.length > 1 ? 520 : 400);
    const cx = WIDTH / 2;
    const cy = HEIGHT / 2 + 8;
    const canvas = svg("svg", { class: "radial", viewBox: `0 0 ${WIDTH} ${HEIGHT}`, role: "group", "aria-label": label });
    const back = svg("g");
    const fore = svg("g");
    rings.forEach((ring, r) => {
      const rx = rings.length === 1 ? 340 : 200 + r * 130;
      const ry = (HEIGHT / 2 - 66) * ((r + 1) / rings.length);
      back.append(svg("ellipse", { cx, cy, rx, ry, class: "ring" }));
      ring.forEach((item, i) => {
        const turn = (i / ring.length) * Math.PI * 2 - Math.PI / 2 + r * 0.26;
        const x = cx + rx * Math.cos(turn);
        const y = cy + ry * Math.sin(turn);
        const bend = (x - cx) * 0.12;
        const line = svg("path", { d: `M${cx} ${cy} Q${(cx + x) / 2 - (y - cy) * 0.14} ${(cy + y) / 2 + bend} ${x} ${y}`, class: `edge tone-${item.tone || "saffron"}` });
        line.dataset.source = "core";
        line.dataset.target = item.id;
        back.append(line);
        const node = svg("g", { class: `rnode tone-${item.tone || "saffron"}`, transform: `translate(${x} ${y})` },
          svg("circle", { class: "halo", r: 20 }), svg("circle", { class: "core", r: item.big ? 13 : 9 }),
          svg("text", { y: 26, "text-anchor": "middle", class: "node-label", text: short(item.label, rings.length > 2 ? 16 : 22) }),
          item.sub ? svg("text", { y: 40, "text-anchor": "middle", class: "node-sub", text: short(item.sub, 24) }) : "");
        node.dataset.id = item.id;
        pressable(node, `${item.label}${item.sub ? `, ${item.sub}` : ""}`, () => { if (stopWalk) stopWalk(); onSelect?.(item.id); });
        fore.append(node);
      });
    });
    const core = svg("g", { class: "rcore", transform: `translate(${cx} ${cy})` },
      svg("circle", { class: "halo", r: 42 }), svg("circle", { class: "core", r: 24 }),
      svg("text", { y: 46, "text-anchor": "middle", class: "node-label", text: short(center, 28) }),
      sub ? svg("text", { y: 62, "text-anchor": "middle", class: "node-sub", text: short(sub, 40) }) : "");
    core.dataset.id = "core";
    canvas.append(back, fore, core);
    if (more) canvas.append(svg("text", { x: WIDTH - 16, y: HEIGHT - 12, "text-anchor": "end", class: "node-sub", text: more }));
    const lit = fx(canvas);
    return { canvas, select: (id) => lit.focus(id) };
  }

  // Sizes by value, split along the longer side, so each cell stays near square.
  function split(items, x, y, w, h, out) {
    if (!items.length) return;
    if (items.length === 1) { out.push({ item: items[0], x, y, w, h }); return; }
    const total = items.reduce((sum, i) => sum + i.value, 0);
    let half = 0;
    let at = 0;
    while (at < items.length - 1 && half + items[at].value / 2 < total / 2) half += items[at++].value;
    if (at === 0) { half = items[0].value; at = 1; }
    const part = half / total;
    if (w * 1.2 >= h) {
      split(items.slice(0, at), x, y, w * part, h, out);
      split(items.slice(at), x + w * part, y, w * (1 - part), h, out);
    } else {
      split(items.slice(0, at), x, y, w, h * part, out);
      split(items.slice(at), x, y + h * part, w, h * (1 - part), out);
    }
  }

  function treemap({ items, onSelect, label }) {
    const root = el("div", { class: "treemap", role: "group", "aria-label": label });
    const cells = new Map();
    const lay = () => {
      const width = root.clientWidth;
      const height = root.clientHeight;
      if (!width || !height) return;
      const out = [];
      split([...items].sort((a, b) => b.value - a.value), 0, 0, width, height, out);
      for (const place of out) {
        const cell = cells.get(place.item.id);
        cell.style.left = `${place.x}px`;
        cell.style.top = `${place.y}px`;
        cell.style.width = `${Math.max(0, place.w - 2)}px`;
        cell.style.height = `${Math.max(0, place.h - 2)}px`;
        cell.classList.toggle("tiny", place.w < 70 || place.h < 34);
      }
    };
    items.forEach((item, i) => {
      const cell = el("button", { type: "button", class: "tm-cell", "aria-label": `${item.label}, ${item.sub || ""}`, on: { click: () => { if (stopWalk) stopWalk(); onSelect?.(item.id); } } },
        el("b", { text: item.label }), el("small", { text: item.sub || "" }));
      cell.style.setProperty("--heat", item.color);
      cell.style.setProperty("--i", String(Math.min(i, 30)));
      cells.set(item.id, cell);
      root.append(cell);
    });
    requestAnimationFrame(lay);
    if (window.ResizeObserver) new ResizeObserver(lay).observe(root);
    return { canvas: root, select: (id) => { for (const [key, cell] of cells) { cell.classList.toggle("selected", key === id); cell.classList.toggle("dim", key !== id); } } };
  }

  // Stations along a line, with a comet running to where things stand.
  function pipeline({ steps, onSelect, label }) {
    const WIDTH = 960;
    const HEIGHT = 240;
    const gap = steps.length > 1 ? (WIDTH - 200) / (steps.length - 1) : 0;
    const at = (i) => ({ x: steps.length > 1 ? 100 + i * gap : WIDTH / 2, y: i % 2 ? 106 : 134 });
    const canvas = svg("svg", { class: "radial pipeline", viewBox: `0 0 ${WIDTH} ${HEIGHT}`, role: "group", "aria-label": label });
    const back = svg("g");
    const fore = svg("g");
    steps.forEach((step, i) => {
      const p = at(i);
      if (i < steps.length - 1) {
        const q = at(i + 1);
        const mid = (p.x + q.x) / 2;
        const line = svg("path", { d: `M${p.x} ${p.y} C${mid} ${p.y} ${mid} ${q.y} ${q.x} ${q.y}`, class: `edge tone-${steps[i + 1].tone || "saffron"}` });
        line.dataset.source = step.id;
        line.dataset.target = steps[i + 1].id;
        back.append(line);
      }
      const node = svg("g", { class: `rnode tone-${step.tone || "saffron"}${step.waiting ? " waiting" : ""}`, transform: `translate(${p.x} ${p.y})` },
        svg("circle", { class: "halo", r: 26 }), svg("circle", { class: "core", r: 14 }),
        svg("text", { y: 38, "text-anchor": "middle", class: "node-label", text: short(step.label, 22) }),
        step.sub ? svg("text", { y: 54, "text-anchor": "middle", class: "node-sub", text: short(step.sub, 26) }) : "");
      node.dataset.id = step.id;
      pressable(node, `${step.label}${step.sub ? `, ${step.sub}` : ""}`, () => { if (stopWalk) stopWalk(); onSelect?.(step.id); });
      fore.append(node);
    });
    canvas.append(back, fore);
    const lit = fx(canvas);
    return { canvas, select: (id) => lit.focus(id) };
  }

  // ---------------------------------------------------------------- walk through
  // The Tour's bar, for any page: it moves through the rail's items, says what each is, and hands back to you on any click.
  function walk({ into, steps, go }) {
    if (stopWalk) stopWalk();
    document.querySelector("#walk")?.remove();
    document.querySelector("#walk-start")?.remove();
    if (!steps.length) return null;
    const text = el("p", {});
    const step = el("span", { class: "step" });
    const dots = el("div", { class: "dots", "aria-hidden": "true" }, ...steps.map(() => el("i")));
    let index = -1;
    let timer = null;
    const play = el("button", { type: "button", class: "btn", id: "walk-play", text: "❚❚ Pause" });
    const show = (to) => {
      index = (to + steps.length) % steps.length;
      step.textContent = `Step ${index + 1} of ${steps.length}`;
      text.textContent = steps[index].text;
      [...dots.children].forEach((d, i) => d.classList.toggle("on", i <= index));
      go(steps[index].id);
    };
    const halt = () => { clearTimeout(timer); timer = null; play.textContent = "▶ Play"; };
    const run = () => {
      play.textContent = "❚❚ Pause";
      clearTimeout(timer);
      if (still()) { play.textContent = "▶ Play"; return; }
      timer = setTimeout(() => {
        if (!bar.isConnected) return;
        show(index + 1);
        run();
      }, 3400);
    };
    const bar = el("div", { class: "narration", id: "walk", "aria-live": "polite", hidden: true },
      el("div", { class: "narration-text" }, step, text),
      el("div", { class: "narration-ctl" },
        el("button", { type: "button", class: "btn icon", "aria-label": "Previous", text: "‹", on: { click: () => { halt(); show(index - 1); } } }),
        play,
        el("button", { type: "button", class: "btn icon", "aria-label": "Next", text: "›", on: { click: () => { halt(); show(index + 1); } } }),
        el("button", { type: "button", class: "btn icon", "aria-label": "Close the walk-through", text: "×", on: { click: () => { halt(); bar.hidden = true; } } })),
      dots);
    play.addEventListener("click", () => { if (timer) halt(); else { show(index + 1); run(); } });
    into.after(bar);
    const start = el("button", { type: "button", class: "chip", id: "walk-start", text: "▶ Walk through", on: { click: () => {
      bar.hidden = false;
      show(index < 0 ? 0 : index);
      run();
    } } });
    tools(start);
    const stop = () => halt();
    stopWalk = stop;
    return { stop, bar };
  }

  window.DevGuru.lantern = { reset, tools, dock, detail, linkList, rail, stage, nothing, pulses, fx, radial, treemap, pipeline, walk, waiting, short, toneOf, svg, SEVERITY_TONE };
  reset();
})();
