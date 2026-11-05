// Code map and end-to-end flows. Everything from the server reaches the page as text or as attributes set through helpers.
"use strict";

(() => {
  const { el, api, scoped, page, showError, views, withAnalysis } = window.DevGuru;
  const SVG = "http://www.w3.org/2000/svg";
  const WIDTH = 190;
  const HEIGHT = 46;
  const GAP_X = 90;
  const GAP_Y = 18;

  const svg = (tag, attrs, ...children) => {
    const node = document.createElementNS(SVG, tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (key === "text") node.textContent = value;
      else if (value !== undefined && value !== null) node.setAttribute(key, value);
    }
    node.append(...children);
    return node;
  };
  const short = (text, max) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

  // Longest-path layers, ignoring edges that close a cycle, then a few sweeps to reduce crossings.
  function layout(nodes, edges) {
    const ids = new Set(nodes.map((n) => n.id));
    const out = new Map(nodes.map((n) => [n.id, []]));
    const into = new Map(nodes.map((n) => [n.id, []]));
    const state = new Map();
    const forward = [];
    const visit = (start) => {
      const stack = [[start, 0]];
      state.set(start, 1);
      while (stack.length) {
        const top = stack[stack.length - 1];
        const next = (top[0] === start && !out.has(start)) ? [] : edges.filter((e) => e.source === top[0]);
        if (top[1] >= next.length) { state.set(top[0], 2); stack.pop(); continue; }
        const edge = next[top[1]++];
        if (!ids.has(edge.target)) continue;
        if (state.get(edge.target) === 1) continue; // closes a cycle: drawn, but not used for layers
        forward.push(edge);
        if (!state.has(edge.target)) { state.set(edge.target, 1); stack.push([edge.target, 0]); }
      }
    };
    for (const n of nodes) if (!state.has(n.id)) visit(n.id);
    for (const e of forward) { out.get(e.source).push(e.target); into.get(e.target).push(e.source); }
    const layer = new Map();
    const pending = new Map(nodes.map((n) => [n.id, into.get(n.id).length]));
    let ready = nodes.filter((n) => pending.get(n.id) === 0).map((n) => n.id);
    for (const id of ready) layer.set(id, 0);
    while (ready.length) {
      const next = [];
      for (const id of ready) {
        for (const target of out.get(id)) {
          layer.set(target, Math.max(layer.get(target) || 0, layer.get(id) + 1));
          pending.set(target, pending.get(target) - 1);
          if (pending.get(target) === 0) next.push(target);
        }
      }
      ready = next;
    }
    const columns = [];
    for (const n of nodes) {
      const at = layer.get(n.id) || 0;
      (columns[at] = columns[at] || []).push(n.id);
    }
    const order = new Map();
    const place = () => columns.forEach((col) => col.forEach((id, i) => order.set(id, i)));
    place();
    const mean = (list) => (list.length ? list.reduce((sum, id) => sum + order.get(id), 0) / list.length : Infinity);
    for (let sweep = 0; sweep < 4; sweep++) {
      const pick = sweep % 2 ? out : into;
      for (const col of columns) {
        if (!col) continue;
        const score = new Map(col.map((id) => [id, mean(pick.get(id))]));
        col.sort((a, b) => (score.get(a) === score.get(b) ? 0 : score.get(a) - score.get(b)));
        col.forEach((id, i) => order.set(id, i));
      }
    }
    const position = new Map();
    const tallest = Math.max(...columns.map((c) => (c ? c.length : 0)), 1);
    columns.forEach((col, x) => {
      if (!col) return;
      const offset = ((tallest - col.length) * (HEIGHT + GAP_Y)) / 2;
      col.forEach((id, y) => position.set(id, { x: 20 + x * (WIDTH + GAP_X), y: 20 + offset + y * (HEIGHT + GAP_Y) }));
    });
    return { position, width: 40 + columns.length * (WIDTH + GAP_X), height: 40 + tallest * (HEIGHT + GAP_Y) };
  }

  // Draws nodes and edges; returns the element and a way to highlight a set of nodes.
  function drawGraph({ nodes, edges, onSelect, label }) {
    const { position, width, height } = layout(nodes, edges);
    const canvas = svg("svg", { class: "graph", viewBox: `0 0 ${width} ${height}`, width, height, role: "group", "aria-label": label });
    const lines = svg("g");
    const boxes = svg("g");
    const shapes = new Map();
    const paths = [];
    for (const edge of edges) {
      const from = position.get(edge.source);
      const to = position.get(edge.target);
      if (!from || !to) continue;
      // left to right normally; a link back leaves from the left, and one within a column arcs out to the right
      const sameColumn = from.x === to.x;
      const onward = to.x > from.x;
      const x1 = onward || sameColumn ? from.x + WIDTH : from.x;
      const y1 = from.y + HEIGHT / 2;
      const x2 = onward ? to.x : to.x + WIDTH;
      const y2 = to.y + HEIGHT / 2;
      const reach = Math.max(40, Math.abs(x2 - x1) / 2);
      const bendOut = onward || sameColumn ? reach : -reach;
      const bendIn = sameColumn ? -reach : bendOut;
      const title = `${edge.kindLabel}: ${edge.source} to ${edge.target}`;
      const line = svg("path", {
        d: `M${x1} ${y1} C${x1 + bendOut} ${y1} ${x2 - bendIn} ${y2} ${x2} ${y2}`,
        class: `edge edge-${edge.kind}${edge.inferred ? " inferred" : ""}`,
        "marker-end": "url(#arrow)",
      }, svg("title", { text: title }));
      line.dataset.source = edge.source;
      line.dataset.target = edge.target;
      paths.push(line);
      lines.append(line);
    }
    for (const node of nodes) {
      const at = position.get(node.id);
      const box = svg("g", { class: `node node-${node.kind}${node.neighbour ? " neighbour" : ""}`, transform: `translate(${at.x} ${at.y})`, tabindex: "0", role: "button", "aria-label": `${node.kind} ${node.label}` },
        svg("rect", { width: WIDTH, height: HEIGHT, rx: 9 }),
        svg("text", { x: 10, y: 19, class: "node-label", text: short(node.label, 25) }),
        svg("text", { x: 10, y: 35, class: "node-sub", text: short(node.sub || node.kind, 29) }));
      box.dataset.id = node.id;
      box.addEventListener("click", () => onSelect(node));
      box.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(node); }
      });
      shapes.set(node.id, box);
      boxes.append(box);
    }
    canvas.append(svg("defs", {}, svg("marker", { id: "arrow", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
      svg("path", { d: "M0 0L8 4L0 8z", class: "arrow-head" }))), lines, boxes);
    const highlight = (ids) => {
      for (const [id, box] of shapes) box.classList.toggle("dim", ids !== null && !ids.has(id));
      for (const line of paths) line.classList.toggle("dim", ids !== null && !(ids.has(line.dataset.source) && ids.has(line.dataset.target)));
      for (const [id, box] of shapes) box.classList.toggle("selected", ids !== null && ids.size === 1 && ids.has(id));
      if (ids !== null && ids.size === 1) keepInView(shapes.get([...ids][0]));
    };
    return { canvas, highlight };
  }

  // Moves the drawing's own frame, never the page, so the current step stays on screen.
  function keepInView(box) {
    const frame = box && box.ownerSVGElement ? box.ownerSVGElement.parentElement : null;
    if (!frame) return;
    const shown = frame.getBoundingClientRect();
    const at = box.getBoundingClientRect();
    frame.scrollLeft += at.left + at.width / 2 - (shown.left + shown.width / 2);
    frame.scrollTop += at.top + at.height / 2 - (shown.top + shown.height / 2);
  }

  function panZoom(canvas) {
    const [, , fullWidth, fullHeight] = canvas.getAttribute("viewBox").split(" ").map(Number);
    let scale = 1;
    // zooming resizes the drawing and its frame scrolls, so text stays readable and nothing is cut off
    const apply = () => {
      canvas.setAttribute("width", fullWidth * scale);
      canvas.setAttribute("height", fullHeight * scale);
    };
    const button = (text, label, fn) => el("button", { type: "button", class: "ghost", text, "aria-label": label, on: { click: fn } });
    // start as close to the whole map as still leaves the labels readable
    requestAnimationFrame(() => {
      const room = canvas.parentElement ? canvas.parentElement.clientWidth : fullWidth;
      scale = Math.max(0.75, Math.min(1, room / fullWidth));
      apply();
    });
    return el("div", { class: "row zoom" },
      button("−", "Zoom out", () => { scale = Math.max(0.4, scale / 1.25); apply(); }),
      button("+", "Zoom in", () => { scale = Math.min(4, scale * 1.25); apply(); }),
      button("Fit", "Fit the whole map", () => {
        const room = canvas.parentElement ? canvas.parentElement.clientWidth : fullWidth;
        scale = Math.max(0.4, Math.min(1, room / fullWidth));
        apply();
      }));
  }

  const whereFile = (node) => (node.path && !node.id.startsWith("dir:") ? node.path : null);

  async function showSource(panel, location) {
    const match = /^(.*?)(?:#cell=\d+)?:(\d+)$/.exec(location || "");
    const path = match ? match[1] : location;
    if (!path || !/\.[a-z]+$/i.test(path)) return;
    const start = match ? Math.max(1, Number(match[2]) - 2) : 1;
    try {
      const source = await api(scoped("/api/v1/source", { path, start, end: start + 24 }));
      panel.append(el("h3", { text: "Source" }), el("p", { class: "muted mono", text: `${path}, lines ${source.start} to ${source.end} of ${source.total_lines}` }),
        el("pre", { class: "source" }, el("code", { text: source.lines.join("\n") })));
    } catch (error) {
      panel.append(el("p", { class: "muted", text: `Source isn't available: ${error.message}` }));
    }
  }

  window.DevGuru.drawGraph = drawGraph;
  window.DevGuru.panZoom = panZoom;

  views.map = async (main, query) => {
    page("Code map", "How this repository connects. Open a folder to see its files, and a file to see its functions.");
    const root = document.querySelector("#main");
    const path = query.get("path") || "";
    const isFile = /\.[A-Za-z0-9]+$/.test(path);
    const depth = Number(query.get("depth")) || 3;
    // A folder's links usually lead out of it, so its view asks for everything and keeps its neighbours.
    const collapse = isFile ? "none" : (path ? "file" : "directory");
    const within = (p) => !path || p === path || p.startsWith(`${path}/`);
    try {
      const view = await api(scoped("/api/v1/code", { collapse, depth, budget: isFile ? 150 : 2000, ...(isFile ? { path } : {}) }));
      const a = view.edge_accounting;
      const crumbs = el("div", { class: "row" }, el("a", { href: "#/map", text: "All folders" }));
      if (path) crumbs.append(el("span", { class: "mono", text: path }));
      root.append(crumbs);
      if (view.truncated) root.append(el("p", { class: "muted", text: "Over budget: the most connected items are shown. Open a folder to narrow it down." }));

      let nodes = view.nodes.map((n) => ({
        // a folder alone can be ambiguous, as many projects have an app and a src: its parent says which
        id: n.node_id, kind: n.kind, path: n.path, raw: n,
        label: n.members !== undefined && n.path ? n.path.split("/").slice(-2).join("/") : (n.name || n.path || "."),
        sub: n.members !== undefined ? `${n.members} ${n.members === 1 ? "item" : "items"}` : (n.source_location || n.kind),
      }));
      let edges = view.edges.map((e) => {
        const kinds = e.kinds ? Object.entries(e.kinds) : [[e.kind, 1]];
        const top = kinds.slice().sort((x, y) => y[1] - x[1])[0][0];
        return {
          source: e.source, target: e.target, kind: ["imports", "calls", "reads", "writes", "inherits", "owns"].includes(top) ? top : "other",
          kindLabel: kinds.map(([k, n]) => (e.kinds ? `${k} ${n}` : k)).join(", "), kinds: kinds.map(([k]) => k), count: e.count || 1,
          inferred: e.origins ? e.origins.inferred > 0 : e.origin === "inferred", raw: e,
        };
      });
      // Imports stop at a process boundary. What crosses it comes from the analysis: HTTP calls, and reads and writes of tables.
      let report = null;
      if (collapse !== "none") {
        try { report = await api(scoped("/api/v1/intel")); } catch { /* not analysed yet: the import links still stand */ }
      }
      let crossing = 0;
      if (report) {
        const group = (symbol) => {
          const file = String(symbol).split(":")[1] || "";
          if (collapse === "file") return `file:${file}`;
          const folders = file.split("/").slice(0, -1).slice(0, depth);
          return `dir:${folders.join("/") || "."}`;
        };
        const known = new Set(nodes.map((n) => n.id));
        const summed = new Map();
        const add = (source, target, kind) => {
          if (source === target || !known.has(source) || !known.has(target)) return;
          const key = `${source}|${target}|${kind}`;
          summed.set(key, { source, target, kind, count: (summed.get(key)?.count || 0) + 1 });
        };
        for (const client of report.sections.api?.clients || []) {
          const route = (report.sections.api.routes || []).find((r) => r.id === client.route);
          if (route?.handler) add(group(client.caller), group(route.handler), "http");
        }
        const usage = report.sections.data?.usage || [];
        for (const table of new Set(usage.map((u) => u.table))) {
          nodes.push({ id: `table:${table}`, kind: "table", label: table, path: "", raw: {}, sub: "table" });
          known.add(`table:${table}`);
        }
        for (const use of usage) add(group(use.symbol), `table:${use.table}`, use.access === "write" ? "writes" : "reads");
        for (const e of summed.values()) {
          crossing += e.count;
          edges.push({ source: e.source, target: e.target, kind: e.kind, kindLabel: `${e.kind} ${e.count}`, kinds: [e.kind], count: e.count, inferred: true, raw: e });
        }
      }
      if (path && !isFile) {
        const inside = new Set(nodes.filter((n) => within(n.path || "")&& n.kind !== "table").map((n) => n.id));
        edges = edges.filter((e) => inside.has(e.source) || inside.has(e.target));
        const shownIds = new Set([...inside, ...edges.flatMap((e) => [e.source, e.target])]);
        nodes = nodes.filter((n) => shownIds.has(n.id)).map((n) => (inside.has(n.id) ? n : { ...n, neighbour: true, sub: `outside: ${n.sub}` }));
      }
      root.append(el("p", { class: "muted", id: "map-summary",
        text: `${nodes.length} items and ${edges.length} links shown${crossing ? `, including ${crossing} HTTP calls and table uses` : ""}. ${a.external_imports} imports of third-party packages aren't drawn.${report || collapse === "none" ? "" : " Analyse the repository to see HTTP calls and tables here."}` }));
      if (!path) {
        root.append(el("label", { class: "field" }, "Folder depth", el("select", { id: "map-depth", on: { change: (e) => { location.hash = `#/map?depth=${e.target.value}`; } } },
          ...[1, 2, 3, 4].map((d) => el("option", { value: String(d), text: String(d), selected: d === depth })))));
      }

      const linked = new Set(edges.flatMap((e) => [e.source, e.target]));
      const alone = nodes.filter((n) => !linked.has(n.id));
      const connected = nodes.filter((n) => linked.has(n.id));

      const inspector = el("aside", { class: "inspector", id: "inspector", "aria-live": "polite" },
        el("p", { class: "muted", text: "Select something to see what it connects to." }));
      const allKinds = [...new Set(edges.flatMap((e) => e.kinds))].sort();
      const hidden = new Set();

      const stage = el("div", { class: "stage", id: "map-stage" });
      let graph = null;
      let selected = null;
      const open = (node) => {
        if (node.kind === "directory" || node.kind === "file") {
          location.hash = `#/map?${new URLSearchParams({ path: node.path === "." ? "" : node.path })}`;
          return;
        }
        select(node);
      };
      // What depends on this, directly or through something else, and how two things connect. Only what this view shows.
      const impactAndPath = (node, label) => {
        const users = new Map();
        for (const e of edges) (users.get(e.target) || users.set(e.target, []).get(e.target)).push(e.source);
        const affected = new Set();
        const queue = [node.id];
        while (queue.length) {
          for (const user of users.get(queue.shift()) || []) {
            if (user !== node.id && !affected.has(user)) { affected.add(user); queue.push(user); }
          }
        }
        const route = (from, to) => {
          const before = new Map([[from, null]]);
          const waiting = [from];
          while (waiting.length) {
            const at = waiting.shift();
            if (at === to) break;
            for (const e of edges) {
              if (e.source === at && !before.has(e.target)) { before.set(e.target, at); waiting.push(e.target); }
            }
          }
          if (!before.has(to)) return null;
          const steps = [];
          for (let at = to; at !== null; at = before.get(at)) steps.unshift(at);
          return steps;
        };
        const result = el("div", { id: "map-path" });
        const others = connected.filter((n) => n.id !== node.id);
        const picker = el("select", { id: "map-path-to", "aria-label": "Find a path to", on: { change: () => {
          const target = picker.value;
          if (!target) { result.replaceChildren(); return; }
          const steps = route(node.id, target) || route(target, node.id);
          if (!steps) { result.replaceChildren(el("p", { class: "muted", text: "No path between these in this view." })); graph.highlight(new Set([node.id, target])); return; }
          result.replaceChildren(el("ol", {}, ...steps.map((id) => el("li", { text: label(id) }))));
          graph.highlight(new Set(steps));
        } } }, el("option", { value: "", text: "Find a path to..." }), ...others.map((n) => el("option", { value: n.id, text: n.label })));
        return [
          el("h3", { text: "Impact" }),
          el("p", { id: "map-impact-count", text: affected.size ? `Changing this could affect ${affected.size} other ${affected.size === 1 ? "item" : "items"} in this view, directly or through others.` : "Nothing in this view depends on it." }),
          ...(affected.size ? [el("button", { type: "button", class: "ghost", id: "map-impact", text: "Show them", on: { click: () => graph.highlight(new Set([node.id, ...affected])) } })] : []),
          el("h3", { text: "Path" }), picker, result,
        ];
      };
      const select = (node) => {
        const incoming = edges.filter((e) => e.target === node.id);
        const outgoing = edges.filter((e) => e.source === node.id);
        graph.highlight(new Set([node.id, ...incoming.map((e) => e.source), ...outgoing.map((e) => e.target)]));
        const label = (id) => nodes.find((n) => n.id === id)?.label || id;
        const list = (title, rows) => (rows.length
          ? [el("h3", { text: title }), el("ul", {}, ...rows.map((r) => el("li", { text: r })))] : []);
        inspector.replaceChildren(el("h2", { text: node.label }), el("p", { class: "muted mono", text: node.raw.source_location || node.path || "" }),
          ...list(`Used by (${incoming.length})`, incoming.map((e) => `${label(e.source)}: ${e.kindLabel}`)),
          ...list(`Uses (${outgoing.length})`, outgoing.map((e) => `${label(e.target)}: ${e.kindLabel}`)));
        if (!incoming.length && !outgoing.length) inspector.append(el("p", { class: "muted", text: "Nothing in this view connects to it." }));
        else inspector.append(...impactAndPath(node, label));
        if (node.kind === "directory" || node.kind === "file") {
          inspector.append(el("button", { type: "button", id: "map-open-selected", text: `Open ${node.label}`, on: { click: () => open(node) } }));
        }
        const where = node.raw.source_location || whereFile(node);
        if (where && node.kind !== "directory") showSource(inspector, where);
      };
      const render = () => {
        const shown = edges.filter((e) => e.kinds.some((k) => !hidden.has(k)));
        stage.replaceChildren();
        if (!connected.length) {
          stage.append(el("p", { class: "muted", text: "Nothing here connects. See the unconnected list below." }));
          return;
        }
        graph = drawGraph({ nodes: connected, edges: shown, onSelect: (node) => { if (selected === node.id && (node.kind === "directory" || node.kind === "file")) open(node); else { selected = node.id; select(node); } }, label: `Map of ${path || "this repository"}` });
        const wrap = el("div", { class: "canvas-wrap" }, graph.canvas);
        stage.append(panZoom(graph.canvas), wrap);
      };
      const chips = el("div", { class: "row", id: "edge-filters", role: "group", "aria-label": "Show links by kind" },
        ...allKinds.map((kind) => {
          const chip = el("button", { type: "button", class: `chip edge-chip-${kind}`, text: kind, "aria-pressed": "true" });
          chip.addEventListener("click", () => {
            if (hidden.has(kind)) hidden.delete(kind); else hidden.add(kind);
            chip.setAttribute("aria-pressed", String(!hidden.has(kind)));
            render();
          });
          return chip;
        }));
      root.append(chips);
      if (connected.length) {
        const openAll = el("div", { class: "row" }, el("label", { class: "field" }, "Open",
          el("select", { id: "map-open", on: { change: (e) => { const n = nodes.find((x) => x.id === e.target.value); if (n) open(n); } } },
            el("option", { value: "", text: "a folder or file…" }),
            ...nodes.filter((n) => n.kind === "directory" || n.kind === "file").map((n) => el("option", { value: n.id, text: n.path || n.label })))));
        if (nodes.some((n) => n.kind === "directory" || n.kind === "file")) root.append(openAll);
      }
      root.append(el("div", { class: "map-layout" }, stage, inspector));
      render();

      if (alone.length) {
        root.append(el("h2", { text: `Not connected (${alone.length})` }),
          el("p", { class: "muted", text: "Nothing in this view links to these: they may be standalone scripts, or linked only through something this analysis doesn't read." }),
          el("ul", { class: "alone", id: "not-connected" }, ...alone.map((n) => el("li", {},
            el("button", { type: "button", class: "ghost", text: n.label, on: { click: () => open(n) } })))));
      }
      // the same facts as the picture, for a keyboard or a screen reader
      root.append(el("details", { id: "map-text" }, el("summary", { text: "The links as a list" }),
        el("div", { class: "wrap" }, el("table", {}, el("thead", {}, el("tr", {}, ...["From", "To", "How"].map((h) => el("th", { scope: "col", text: h })))),
          el("tbody", {}, ...edges.slice(0, 300).map((e) => el("tr", {}, el("td", { class: "mono", text: e.source }), el("td", { class: "mono", text: e.target }),
            el("td", { text: e.inferred ? `${e.kindLabel} (inferred)` : e.kindLabel }))))))));
    } catch (error) {
      if (error.code !== "GRAPH_MISSING") { showError(root, error); return; }
      showError(root, error, el("a", { href: "#/code", text: "Build the code graph" }));
    }
  };

  views.flows = async (_main, query) => {
    page("End-to-end flows", "What happens from a request to the data, drawn only from links found in the code.");
    const root = document.querySelector("#main");
    await withAnalysis(root, (report) => {
      const section = report.sections.flows;
      const api_ = report.sections.api;
      if (section.status !== "found") {
        root.append(el("p", { class: "muted", id: "flows-empty", text: "No flows were found. This repository may have no HTTP routes this analysis can read." }));
        for (const limit of section.limits || []) root.append(el("p", { class: "muted", text: limit }));
        return;
      }
      const broken = (api_.unmatched_clients || []).filter((c) => !c.base_unknown && !c.external);
      if (broken.length) {
        root.append(el("div", { class: "card warn-card", id: "unmatched-calls" }, el("h2", { text: `Calls to routes that don't exist here (${broken.length})` }),
          el("ul", {}, ...broken.map((c) => el("li", {}, el("code", { text: `${c.method} ${c.path}` }), ` from ${c.evidence}`)))));
      }
      const flows = section.flows || [];
      const wanted = query.get("flow");
      const filter = el("input", { type: "search", id: "flow-search", placeholder: "Find a flow", "aria-label": "Find a flow" });
      const picker = el("select", { id: "flow-picker", "aria-label": "Flow" });
      const stage = el("div", { id: "flow-stage" });
      const fill = () => {
        const words = filter.value.toLowerCase();
        picker.replaceChildren(...flows.filter((f) => f.name.toLowerCase().includes(words)).map((f) => el("option", { value: f.id, text: f.name })));
      };
      const showFlow = (flow) => {
        stage.replaceChildren();
        if (!flow) return;
        const nodes = flow.steps.map((s) => ({ id: s.node, kind: s.kind === "table" ? "table" : s.kind, label: s.label, sub: s.access || s.kind, raw: s }));
        const known = new Set(nodes.map((n) => n.id));
        const edges = flow.edges.filter((e) => known.has(e.source) && known.has(e.target)).map((e) => ({
          source: e.source, target: e.target, kind: e.kind, kindLabel: e.kind, inferred: e.origin === "inferred",
        }));
        const detail = el("aside", { class: "inspector", id: "flow-detail", "aria-live": "polite" });
        let index = 0;
        let graph = null;
        const steps = el("ol", { class: "steps", id: "flow-steps" });
        const go = (to) => {
          index = Math.max(0, Math.min(flow.steps.length - 1, to));
          const step = flow.steps[index];
          graph.highlight(new Set([step.node]));
          for (const [i, row] of [...steps.children].entries()) {
            if (i === index) row.setAttribute("aria-current", "step"); else row.removeAttribute("aria-current");
          }
          detail.replaceChildren(el("h2", { text: step.label }), el("p", { class: "muted", text: `Step ${index + 1} of ${flow.steps.length}: ${step.kind}${step.access ? `, ${step.access}` : ""}` }),
            el("p", { class: "mono", text: step.evidence || "" }));
          if (step.evidence) showSource(detail, step.evidence);
        };
        graph = drawGraph({ nodes, edges, label: `Flow ${flow.name}`, onSelect: (node) => go(flow.steps.findIndex((s) => s.node === node.id)) });
        flow.steps.forEach((step, i) => steps.append(el("li", {},
          el("button", { type: "button", class: "ghost", text: `${step.label}${step.access ? ` (${step.access})` : ""}`, on: { click: () => go(i) } }))));
        const reaches = flow.steps.some((s) => s.kind === "table");
        const called = flow.steps.some((s) => s.kind === "client");
        stage.append(el("p", { class: "muted", id: "flow-note", text: [
          called ? "Called from this repository." : "No caller found in this repository.",
          reaches ? "Reaches a data store." : "No data store found on this path.",
          flow.truncated ? "Cut short at the size limit." : "",
        ].filter(Boolean).join(" ") }),
        panZoom(graph.canvas), el("div", { class: "row" },
          el("button", { type: "button", class: "ghost", id: "flow-prev", text: "Previous step", on: { click: () => go(index - 1) } }),
          el("button", { type: "button", class: "ghost", id: "flow-next", text: "Next step", on: { click: () => go(index + 1) } })),
        el("div", { class: "canvas-wrap" }, graph.canvas), el("div", { class: "map-layout" }, steps, detail));
        go(0);
      };
      const pick = () => showFlow(flows.find((f) => f.id === picker.value));
      filter.addEventListener("input", () => { fill(); pick(); });
      picker.addEventListener("change", pick);
      fill();
      if (wanted && flows.some((f) => f.id === wanted)) picker.value = wanted;
      root.append(el("div", { class: "row" }, filter, picker), stage);
      for (const limit of section.limits || []) root.append(el("p", { class: "muted", text: limit }));
      pick();
    });
  };
})();
