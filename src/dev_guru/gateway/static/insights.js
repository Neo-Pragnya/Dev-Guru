// Data, API pathways, architecture, quality, coverage and CVEs. Unknown is never shown as zero or as clean.
"use strict";

(() => {
  const { el, page, views, withAnalysis, startAnalysis, showError, when, lantern: L } = window.DevGuru;
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
  const main = () => document.querySelector("#main");
  const short = (text, max) => (String(text).length > max ? `${String(text).slice(0, max - 1)}…` : String(text));
  const table = (id, heads, rows) => el("div", { class: "wrap" }, el("table", { id },
    el("thead", {}, el("tr", {}, ...heads.map((h) => el("th", { scope: "col", text: h })))),
    el("tbody", {}, ...rows.map((cells) => el("tr", {}, ...cells.map((c) => (c instanceof Node ? el("td", {}, c) : el("td", { text: c === null || c === undefined ? "" : String(c) }))))))));
  const limits = (section) => (section.limits || []).length
    ? el("details", { class: "limits" }, el("summary", { text: `What this doesn't cover (${section.limits.length})` }), el("ul", {}, ...section.limits.map((l) => el("li", { text: l }))))
    : null;
  const stat = (value, label) => el("div", { class: "card" }, el("span", { class: "stat", text: value === null || value === undefined ? "unknown" : String(value) }), label);
  const download = (name, text, type) => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([text], { type }));
    link.download = name;
    link.click();
    URL.revokeObjectURL(link.href);
  };
  const status = (section, none) => {
    if (section.status === "found" || section.status === "scanned") return true;
    const said = section.status === "failed" ? "This analysis failed, so nothing is known here." : none;
    L.nothing(main(), said, said);
    main().append(el("p", { class: "muted", id: "section-status", text: said }));
    const more = limits(section);
    if (more) main().append(more);
    return false;
  };
  const stamp = (report) => el("p", { class: "muted mono", id: "analysed-at", text: `Analysed ${report.analysed_at ? when(report.analysed_at) : ""}, ${report.source_snapshot || ""}` });
  const page_ = (title, lede, render) => async () => {
    page(title, lede);
    await withAnalysis(main(), (report) => { render(report); main().append(stamp(report)); });
  };

  // ------------------------------------------------------------------ data
  const CARD_WIDTH = 230;
  const ROW = 19;
  const HEAD = 30;

  const ARC_ROOM = 46;
  function erd(tables, relationships, onSelect) {
    // tables that share keys sit together, joined tables first
    const degree = new Map(tables.map((t) => [t.name, 0]));
    for (const r of relationships) {
      if (degree.has(r.from_table)) degree.set(r.from_table, degree.get(r.from_table) + 1);
      if (degree.has(r.to_table)) degree.set(r.to_table, degree.get(r.to_table) + 1);
    }
    const near = new Map(tables.map((t) => [t.name, []]));
    for (const r of relationships) {
      if (near.has(r.from_table) && near.has(r.to_table)) { near.get(r.from_table).push(r.to_table); near.get(r.to_table).push(r.from_table); }
    }
    const order = [];
    const seen = new Set();
    for (const start of [...tables].sort((a, b) => degree.get(b.name) - degree.get(a.name))) {
      if (seen.has(start.name)) continue;
      const queue = [start.name];
      seen.add(start.name);
      while (queue.length) {
        const name = queue.shift();
        order.push(name);
        for (const next of near.get(name)) if (!seen.has(next)) { seen.add(next); queue.push(next); }
      }
    }
    const byName = new Map(tables.map((t) => [t.name, t]));
    const columnsAcross = Math.max(1, Math.ceil(Math.sqrt(order.length)));
    const place = new Map();
    const heights = Array(columnsAcross).fill(ARC_ROOM);
    order.forEach((name, i) => {
      const x = i % columnsAcross;
      const visible = Math.min(byName.get(name).columns.length, 10);
      const height = HEAD + visible * ROW + (byName.get(name).columns.length > 10 ? ROW : 0) + 8;
      place.set(name, { x: 20 + x * (CARD_WIDTH + 90), y: heights[x], height });
      heights[x] += height + 44;
    });
    const fullWidth = 40 + columnsAcross * (CARD_WIDTH + 90);
    const fullHeight = Math.max(...heights) + 20;
    const canvas = svg("svg", { class: "erd graph", viewBox: `0 0 ${fullWidth} ${fullHeight}`, width: fullWidth, height: fullHeight, role: "group", "aria-label": `Diagram of ${order.length} tables` });
    const lines = svg("g");
    for (const r of relationships) {
      const from = place.get(r.from_table);
      const to = place.get(r.to_table);
      if (!from || !to || r.from_table === r.to_table) continue;
      // cards with a column between them join by an arc over the top, rather than a line through what's between
      if (Math.abs(from.x - to.x) > CARD_WIDTH + 90) {
        const a = from.x + CARD_WIDTH / 2;
        const b = to.x + CARD_WIDTH / 2;
        const lift = Math.min(from.y, to.y) - ARC_ROOM + 2;
        lines.append(svg("path", { d: `M${a} ${from.y} C${a} ${lift} ${b} ${lift} ${b} ${to.y}`, class: `rel${r.origin === "inferred" ? " inferred" : ""}`, "marker-end": "url(#one)", "marker-start": r.cardinality === "one-to-one" ? "url(#one)" : "url(#many)", "data-source": r.from_table, "data-target": r.to_table },
          svg("title", { text: `${r.from_table}.${r.from_column} to ${r.to_table}.${r.to_column}, ${r.cardinality}` })));
        continue;
      }
      // cards in one column join by an arc out to the right, rather than a line looping through them both
      const sameColumn = from.x === to.x;
      const leftToRight = from.x < to.x;
      const x1 = leftToRight || sameColumn ? from.x + CARD_WIDTH : from.x;
      const x2 = leftToRight ? to.x : to.x + CARD_WIDTH;
      const y1 = from.y + from.height / 2;
      const y2 = to.y + to.height / 2;
      const reach = sameColumn ? 60 : Math.max(30, Math.abs(x2 - x1) / 2);
      const bendOut = leftToRight || sameColumn ? reach : -reach;
      const bendIn = sameColumn ? -reach : bendOut;
      const line = svg("path", { d: `M${x1} ${y1} C${x1 + bendOut} ${y1} ${x2 - bendIn} ${y2} ${x2} ${y2}`, class: `rel${r.origin === "inferred" ? " inferred" : ""}`, "marker-end": "url(#one)", "marker-start": r.cardinality === "one-to-one" ? "url(#one)" : "url(#many)", "data-source": r.from_table, "data-target": r.to_table },
        svg("title", { text: `${r.from_table}.${r.from_column} to ${r.to_table}.${r.to_column}, ${r.cardinality}` }));
      lines.append(line);
    }
    const cards = svg("g");
    for (const name of order) {
      const t = byName.get(name);
      const at = place.get(name);
      const inferred = String(t.source || "").startsWith("inferred");
      const card = svg("g", { class: `table-card${inferred ? " inferred" : ""}`, "data-id": name, transform: `translate(${at.x} ${at.y})`, tabindex: "0", role: "button", "aria-label": `Table ${name}, ${t.columns.length} columns` },
        svg("rect", { width: CARD_WIDTH, height: at.height, rx: 8 }),
        svg("rect", { class: "table-head", width: CARD_WIDTH, height: HEAD - 4, rx: 8 }),
        svg("text", { x: 10, y: 18, class: "table-name", text: short(name, 26) }));
      t.columns.slice(0, 10).forEach((c, i) => {
        const mark = c.primary_key ? "PK " : (c.foreign_key ? "FK " : "");
        card.append(svg("text", { x: 10, y: HEAD + 13 + i * ROW, class: `col${mark ? " key" : ""}`, text: short(`${mark}${c.name}`, 20) }),
          svg("text", { x: CARD_WIDTH - 10, y: HEAD + 13 + i * ROW, class: "col-type", "text-anchor": "end", text: short(c.type || "", 11) }));
      });
      if (t.columns.length > 10) card.append(svg("text", { x: 10, y: HEAD + 13 + 10 * ROW, class: "col-type", text: `and ${t.columns.length - 10} more` }));
      card.addEventListener("click", () => onSelect(t));
      card.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(t); } });
      cards.append(card);
    }
    canvas.append(svg("defs", {},
      svg("marker", { id: "one", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 9, markerHeight: 9, orient: "auto-start-reverse" }, svg("path", { d: "M8 1V9", class: "mark" })),
      svg("marker", { id: "many", viewBox: "0 0 10 10", refX: 1, refY: 5, markerWidth: 9, markerHeight: 9, orient: "auto-start-reverse" }, svg("path", { d: "M1 5L9 1M1 5L9 9M1 5H9", class: "mark" }))),
    lines, cards);
    canvas.dgLit = L.fx(canvas);
    return canvas;
  }

  views.data = page_("Data", "The tables this repository defines or uses, how they relate, and which code touches them.", (report) => {
    const data = report.sections.data;
    if (!status(data, "No tables were found: no ORM models, SQL files or SQL in the code that this analysis can read.")) return;
    const root = main();
    const tables = data.tables;
    const inferredCount = tables.filter((t) => String(t.source || "").startsWith("inferred")).length;
    root.append(el("div", { class: "cards" }, stat(tables.length, "Tables"), stat(data.relationships.length, "Relationships"), stat(data.usage.length, "Places code uses them"), stat(inferredCount, "Known only from use")));
    L.tools(
      el("button", { type: "button", class: "chip", id: "copy-erd", text: "Copy Mermaid ERD", on: { click: async (e) => { await navigator.clipboard.writeText(data.erd_mermaid); e.target.textContent = "Copied"; } } }),
      el("button", { type: "button", class: "chip", id: "download-erd", text: "Download Mermaid ERD", on: { click: () => download("erd.mmd", data.erd_mermaid, "text/plain") } }));
    const detail = el("aside", { class: "inspector", id: "table-detail" }, el("p", { class: "muted", text: "Select a table to see its fields and the code that uses it." }));
    L.dock(detail);
    let canvas = null;
    let list = null;
    const select = (t) => {
      const uses = data.usage.filter((u) => u.table === t.name);
      const related = data.relationships.filter((r) => r.from_table === t.name || r.to_table === t.name);
      canvas?.dgLit.focus(t.name);
      list?.select(t.name);
      detail.replaceChildren(el("h2", { text: t.name }), el("p", { class: "ins-path mono", text: `${t.source}: ${t.evidence || "no definition found"}` }),
        el("div", { class: "facts" }, el("div", { class: "fact" }, el("b", { text: String(t.columns.length) }), el("span", { text: "Fields" })), el("div", { class: "fact" }, el("b", { text: String(uses.length) }), el("span", { text: "Uses" })), el("div", { class: "fact" }, el("b", { text: String(related.length) }), el("span", { text: "Keys" }))),
        table("table-columns", ["Field", "Type", "Key", "Null"], t.columns.map((c) => [c.name, c.type, c.primary_key ? "primary" : (c.foreign_key ? `to ${c.foreign_key}` : ""), c.nullable === false ? "no" : (c.nullable ? "yes" : "")])),
        el("h3", { class: "eyebrow", text: `Code that uses it (${uses.length})` }),
        uses.length ? el("ul", { id: "table-usage" }, ...uses.map((u) => el("li", {}, el("strong", { text: u.access }), ` ${String(u.symbol).split(":").slice(1).join(":")} `, el("span", { class: "muted mono", text: u.evidence })))) : el("p", { class: "muted", text: "No code found using it." }),
        el("h3", { class: "eyebrow", text: `Relationships (${related.length})` }),
        el("ul", {}, ...related.map((r) => el("li", { text: `${r.from_table}.${r.from_column} to ${r.to_table}.${r.to_column}, ${r.cardinality}` }))));
    };
    const frame = L.stage({ id: "erd-stage", legend: [["a key in the schema", "saffron"], ["inferred", "saffron", true]], hint: "Hover or select a table to follow its keys." });
    const groupOf = (t) => t.schema || String(t.evidence || "").split("/")[0] || "other";
    const draw = (shown) => {
      const names = new Set(shown.map((t) => t.name));
      canvas = erd(shown, data.relationships.filter((r) => names.has(r.from_table) && names.has(r.to_table)), select);
      frame.body.replaceChildren(el("div", { class: "canvas-wrap" }, canvas), window.DevGuru.panZoom(canvas));
    };
    if (tables.length > 40) {
      const groups = [...new Set(tables.map(groupOf))].sort();
      const picker = el("select", { id: "erd-group", on: { change: (e) => draw(tables.filter((t) => groupOf(t) === e.target.value)) } },
        ...groups.map((g) => el("option", { value: g, text: `${g} (${tables.filter((t) => groupOf(t) === g).length})` })));
      root.append(el("label", { class: "field" }, `${tables.length} tables are too many to draw at once. Show`, picker));
      draw(tables.filter((t) => groupOf(t) === groups[0]));
    } else {
      draw(tables);
    }
    root.append(frame.el);
    const keysOf = (t) => data.relationships.filter((r) => r.from_table === t.name || r.to_table === t.name).length;
    const ranked = [...tables].sort((a, b) => keysOf(b) - keysOf(a));
    const pick = (name) => select(tables.find((t) => t.name === name));
    list = L.rail({ search: true, placeholder: "Find a table", onSelect: pick,
      insights: ranked.length ? [{ title: "Most connected", text: ranked[0].name, onClick: () => pick(ranked[0].name) }] : [],
      groups: [{ title: "Tables", items: tables.map((t) => ({ id: t.name, label: t.name, sub: `${t.columns.length} fields`, count: keysOf(t), tone: String(t.source || "").startsWith("inferred") ? "faint" : "saffron" })) }] });
    L.walk({ into: frame.el, go: pick, steps: ranked.slice(0, 10).map((t) => ({ id: t.name, text: `${t.name} has ${t.columns.length} fields and ${keysOf(t)} ${keysOf(t) === 1 ? "key" : "keys"} joining other tables.` })) });
    if (ranked.length) select(ranked[0]);
    root.append(el("h2", { text: "Data lineage" }), el("p", { class: "muted", text: "Which code writes each table, and which reads it." }));
    const sides = (name, access) => data.usage.filter((u) => u.table === name && (u.access === access || u.access === "read_write")).map((u) => String(u.symbol).split(":").pop()).join(", ");
    root.append(table("lineage", ["Written by", "Table", "Read by"], tables.filter((t) => data.usage.some((u) => u.table === t.name)).map((t) => [sides(t.name, "write"), t.name, sides(t.name, "read")])));
    const more = limits(data);
    if (more) root.append(more);
  });

  // ------------------------------------------------------------------ API pathways
  const method = (m) => el("span", { class: `method method-${String(m).toLowerCase()}`, text: m });

  views.apis = page_("API pathways", "Every route this repository serves, and who calls it.", (report) => {
    const api = report.sections.api;
    if (!status(api, "No HTTP routes or clients were found that this analysis can read.")) return;
    const root = main();
    const clients = api.clients || [];
    const unmatched = api.unmatched_clients || [];
    const broken = unmatched.filter((c) => !c.base_unknown && !c.external);
    const elsewhere = unmatched.filter((c) => c.base_unknown || c.external);
    root.append(el("div", { class: "cards" }, stat(api.routes.length, "Routes"), stat(clients.filter((c) => c.route).length, "Calls linked to a route"), stat(broken.length, "Calls to routes that don't exist here"), stat(elsewhere.length, "Calls to other services")));
    const flowLink = (r) => el("a", { href: `#/flows?${new URLSearchParams({ flow: `flow:${String(r.id).replace(/^route:/, "")}` })}`, text: "Open its flow" });
    let list = null;
    let graph = null;
    const select = (id) => {
      const r = api.routes.find((x) => x.id === id);
      if (!r) return;
      const callers = clients.filter((c) => c.route === r.id);
      graph?.highlight(new Set([r.id, `handler:${r.handler || r.id}`, ...callers.map((c) => `client:${c.caller}`)]), r.id);
      list?.select(id);
      const notes = [r.unmounted ? "not mounted" : "", r.prefix_unknown ? "prefix unknown" : "", r.catch_all ? "catch-all" : ""].filter(Boolean);
      L.dock(L.detail({ title: `${r.method} ${r.path}`, where: String(r.handler || "").split(":").slice(1).join(":") || r.handler_name, tags: notes, facts: [[callers.length, "Callers"]], actions: [flowLink(r)] },
        ...L.linkList("Called from", callers.map((c) => `${String(c.caller).split(":").pop()}, ${c.evidence}`))));
    };
    const shownRoutes = api.routes.slice(0, 40);
    const callersShown = clients.filter((c) => c.route && shownRoutes.some((r) => r.id === c.route));
    const nodes = [
      ...new Map(callersShown.map((c) => [`client:${c.caller}`, { id: `client:${c.caller}`, kind: "client", label: String(c.caller).split(":").pop(), sub: String(c.evidence || "caller"), column: 0 }])).values(),
      ...shownRoutes.map((r) => ({ id: r.id, kind: "route", label: `${r.method} ${r.path}`, sub: "route", column: 1 })),
      ...new Map(shownRoutes.map((r) => [`handler:${r.handler || r.id}`, { id: `handler:${r.handler || r.id}`, kind: "handler", label: String(r.handler || r.handler_name || "handler").split(":").pop(), sub: "handler", column: 2 }])).values(),
    ];
    const edges = [
      ...callersShown.map((c) => ({ source: `client:${c.caller}`, target: c.route, kind: "http", kindLabel: "calls", inferred: true })),
      ...shownRoutes.map((r) => ({ source: r.id, target: `handler:${r.handler || r.id}`, kind: "handles", kindLabel: "handled by" })),
    ];
    graph = window.DevGuru.drawGraph({ nodes, edges, label: "Callers, routes and handlers", onSelect: (node) => { if (node.kind === "route") select(node.id); } });
    const frame = L.stage({ id: "api-stage", legend: [["a call from this repository", "ember"], ["handled by", "saffron"]], hint: api.routes.length > 40 ? `The first 40 of ${api.routes.length} routes.` : "Callers on the left, routes in the middle, handlers on the right." });
    frame.fill(el("div", { class: "canvas-wrap" }, graph.canvas), window.DevGuru.panZoom(graph.canvas));
    root.append(frame.el);
    const prefix = (r) => `/${String(r.path).split("/").filter(Boolean).slice(0, 2).join("/")}`;
    list = L.rail({ search: true, placeholder: "Find a route", onSelect: select,
      insights: [broken.length ? { title: "Calls with no route here", text: `${broken.length} may be bugs`, onClick: () => document.querySelector("#api-broken")?.scrollIntoView({ block: "nearest" }) } : null],
      groups: [...new Set(api.routes.map(prefix))].map((name) => ({ title: name, items: api.routes.filter((r) => prefix(r) === name).map((r) => ({ id: r.id, label: `${r.method} ${r.path}`, count: clients.filter((c) => c.route === r.id).length, tone: { GET: "teal", POST: "saffron", PUT: "saffron", PATCH: "saffron", DELETE: "rose" }[r.method] || "violet" })) })) });
    L.walk({ into: frame.el, go: select, steps: api.routes.slice(0, 12).map((r) => ({ id: r.id, text: `${r.method} ${r.path} is handled by ${String(r.handler || r.handler_name || "something this analysis can't name").split(":").pop()}, and called from ${clients.filter((c) => c.route === r.id).length} ${clients.filter((c) => c.route === r.id).length === 1 ? "place" : "places"} here.` })) });
    if (api.routes.length) select(api.routes[0].id);
    const search = el("input", { type: "search", id: "route-search", placeholder: "Find a route", "aria-label": "Find a route" });
    const body = el("div", { id: "route-list" });
    const fill = () => {
      const words = search.value.toLowerCase();
      const rows = api.routes.filter((r) => `${r.method} ${r.path} ${r.handler}`.toLowerCase().includes(words));
      body.replaceChildren(table("routes", ["Method", "Path", "Handler", "Called from", "Notes", ""], rows.map((r) => {
        const callers = clients.filter((c) => c.route === r.id);
        const notes = [r.unmounted ? "not mounted" : "", r.prefix_unknown ? "prefix unknown" : "", r.catch_all ? "catch-all" : ""].filter(Boolean).join(", ");
        return [method(r.method), el("code", { text: r.path }), String(r.handler || "").split(":").slice(1).join(":") || r.handler_name || "", callers.length ? callers.map((c) => String(c.caller).split(":").pop()).join(", ") : "none found", notes,
          el("a", { href: `#/flows?${new URLSearchParams({ flow: `flow:${String(r.id).replace(/^route:/, "")}` })}`, text: "Flow" })];
      })));
    };
    search.addEventListener("input", fill);
    root.append(el("h2", { text: "Routes" }), search, body);
    fill();
    if (broken.length) {
      root.append(el("div", { class: "card warn-card", id: "api-broken" }, el("h2", { text: "These calls have no route here" }), el("p", { class: "muted", text: "They may be bugs, or may reach a service outside this repository." }),
        table("broken-calls", ["Call", "From"], broken.map((c) => [`${c.method} ${c.path}`, c.evidence]))));
    }
    if (elsewhere.length) root.append(el("h2", { text: "Calls to other services" }), table("other-calls", ["Call", "From"], elsewhere.map((c) => [`${c.method} ${c.host || ""}${c.path}`, c.evidence])));
    if ((api.specs || []).length) root.append(el("h2", { text: "API specifications" }), table("specs", ["File", "Title", "Operations"], api.specs.map((s) => [s.path, s.title, s.routes])));
    const more = limits(api);
    if (more) root.append(more);
  });

  // ------------------------------------------------------------------ architecture
  views.architecture = page_("Architecture", "An architecture model inferred from this repository, in CALM form. It's inferred, so check it against what you know.", (report) => {
    const calm = report.sections.calm;
    const overview = report.sections.overview;
    const root = main();
    root.append(el("div", { class: "cards" }, stat(overview.files, "Files"), stat(overview.loc, "Lines"), stat(Object.keys(overview.languages || {}).length, "Languages"), stat((overview.components || []).length, "Components")));
    if (status(calm, "No architecture could be inferred.")) {
      const model = calm.model;
      const components = model.components || [];
      const relations = model.relationships || [];
      const width = 210;
      // what depends on what reads left to right. Going round only as many times as there are components stops a cycle.
      const depth = new Map(components.map((c) => [c.id, 0]));
      for (let round = 0; round < components.length; round++) {
        for (const r of relations) {
          if (depth.has(r.source) && depth.has(r.target)) depth.set(r.target, Math.min(components.length - 1, Math.max(depth.get(r.target), depth.get(r.source) + 1)));
        }
      }
      // something nothing depends on sits next to what it uses, so its line doesn't cross what's between them
      for (const c of components) {
        const targets = relations.filter((r) => r.source === c.id && depth.has(r.target)).map((r) => depth.get(r.target));
        if (targets.length && !relations.some((r) => r.target === c.id)) depth.set(c.id, Math.max(0, Math.min(...targets) - 1));
      }
      const rows = new Map();
      const at = new Map();
      for (const c of components) {
        const column = depth.get(c.id);
        const row = rows.get(column) || 0;
        rows.set(column, row + 1);
        at.set(c.id, { x: 20 + column * (width + 80), y: 20 + row * 100 });
      }
      const across = Math.max(1, ...components.map((c) => depth.get(c.id) + 1));
      const down = Math.max(1, ...rows.values());
      const fullWidth = 40 + across * (width + 80);
      const fullHeight = 20 + down * 100;
      const canvas = svg("svg", { class: "erd graph", viewBox: `0 0 ${fullWidth} ${fullHeight}`, width: fullWidth, height: fullHeight, role: "group", "aria-label": `Architecture of ${components.length} components` });
      let lit = null;
      let list = null;
      const selectComponent = (id) => {
        const c = components.find((x) => x.id === id);
        if (!c) return;
        lit?.focus(id);
        list?.select(id);
        const known = (overview.components || []).find((k) => k.name === c.name || k.name === c.id);
        const going = relations.filter((r) => r.source === id);
        const coming = relations.filter((r) => r.target === id);
        L.dock(L.detail({ title: c.name || c.id, where: known?.path, tags: [c.type || "component", "inferred"], note: known?.evidence, facts: [[known?.files, "Files"], [known?.loc, "Lines"], [going.length + coming.length, "Links"]] },
          ...L.linkList("It uses", going.map((r) => `${r.target}: ${r.type || "uses"}, ${r.evidence || ""}`)),
          ...L.linkList("Used by", coming.map((r) => `${r.source}: ${r.type || "uses"}, ${r.evidence || ""}`))));
      };
      const lines = svg("g");
      for (const r of relations) {
        const a = at.get(r.source);
        const b = at.get(r.target);
        if (!a || !b || a === b) continue;
        const sameColumn = a.x === b.x;
        const onward = b.x > a.x;
        const x1 = onward || sameColumn ? a.x + width : a.x;
        const x2 = onward ? b.x : b.x + width;
        const reach = sameColumn ? 50 : Math.max(30, Math.abs(x2 - x1) / 2);
        const out = onward || sameColumn ? reach : -reach;
        const back = sameColumn ? -reach : out;
        lines.append(svg("path", { d: `M${x1} ${a.y + 35} C${x1 + out} ${a.y + 35} ${x2 - back} ${b.y + 35} ${x2} ${b.y + 35}`, class: "rel inferred", "marker-end": "url(#arch)", "data-from": r.source, "data-to": r.target, "data-source": r.source, "data-target": r.target }, svg("title", { text: `${r.source} to ${r.target}: ${r.type || ""} ${r.evidence || ""}` })));
      }
      const boxes = svg("g");
      for (const c of components) {
        const p = at.get(c.id);
        const box = svg("g", { class: `table-card kind-${c.type || "other"}`, "data-component": c.id, "data-id": c.id, "data-column": String(depth.get(c.id)), transform: `translate(${p.x} ${p.y})`, tabindex: "0", role: "button", "aria-label": `${c.name || c.id}, ${c.type || "component"}` },
          svg("rect", { width, height: 70, rx: 10 }), svg("text", { x: 12, y: 28, class: "table-name", text: short(c.name || c.id, 24) }), svg("text", { x: 12, y: 50, class: "col-type", text: c.type || "" }));
        box.addEventListener("click", () => selectComponent(c.id));
        box.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectComponent(c.id); } });
        boxes.append(box);
      }
      canvas.append(svg("defs", {}, svg("marker", { id: "arch", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 7, markerHeight: 7, orient: "auto" }, svg("path", { d: "M0 0L8 4L0 8z", class: "arrow-head" }))), lines, boxes);
      lit = L.fx(canvas);
      L.tools(el("button", { type: "button", class: "chip", id: "download-calm", text: "Download CALM model", on: { click: () => download("system.calm.json", JSON.stringify(model, null, 2), "application/json") } }));
      const frame = L.stage({ id: "calm-stage", legend: [["inferred from the repository", "saffron", true]], hint: "Inferred, so check it against what you know." });
      frame.fill(el("div", { class: "canvas-wrap", id: "calm-diagram" }, canvas), window.DevGuru.panZoom(canvas));
      root.append(frame.el);
      list = L.rail({ search: true, placeholder: "Find a component", onSelect: selectComponent,
        groups: [{ title: "Components", items: components.map((c) => ({ id: c.id, label: c.name || c.id, sub: c.type, count: relations.filter((r) => r.source === c.id || r.target === c.id).length })) }] });
      L.walk({ into: frame.el, go: selectComponent, steps: components.map((c) => ({ id: c.id, text: `${c.name || c.id} is a ${c.type || "component"}, with ${relations.filter((r) => r.source === c.id || r.target === c.id).length} links to the others.` })) });
      if (components.length) selectComponent(components[0].id);
      root.append(el("h2", { text: "How they connect" }),
        relations.length ? table("calm-links", ["From", "To", "How", "Evidence"], relations.map((r) => [r.source, r.target, r.type, r.evidence])) : el("p", { class: "muted", text: "No links between components were found." }));
      if (calm.drift) {
        const pair = (p) => `${p[0]} to ${p[1]}`;
        const rows = [
          ...(calm.drift.components_only_declared || []).map((c) => ["Component", c, "Declared, but not found in the code"]),
          ...(calm.drift.components_only_inferred || []).map((c) => ["Component", c, "Found in the code, but not declared"]),
          ...(calm.drift.relationships_only_declared || []).map((p) => ["Link", pair(p), "Declared, but not found in the code"]),
          ...(calm.drift.relationships_only_inferred || []).map((p) => ["Link", pair(p), "Found in the code, but not declared"]),
        ];
        root.append(el("h2", { text: "Differences from the declared model" }), el("p", { class: "muted mono", text: calm.drift.declared_path || "" }),
          rows.length ? table("calm-drift", ["What", "Name", "Difference"], rows) : el("p", { class: "muted", id: "calm-drift-none", text: "The code matches the declared model." }));
      }
    }
    root.append(el("h2", { text: "Components" }), table("components", ["Name", "Kind", "Language", "Folder", "Files", "Lines", "Why"], (overview.components || []).map((c) => [c.name, c.kind, c.language, c.path, c.files, c.loc, c.evidence])));
    root.append(el("p", { class: "muted", id: "languages", text: `Languages: ${Object.entries(overview.languages || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join(", ")}` }));
    if ((overview.source_roots || []).length) root.append(el("p", { class: "muted", text: `Source roots: ${overview.source_roots.join(", ")}` }));
    for (const part of [calm, overview]) { const more = limits(part); if (more) root.append(more); }
  });

  // ------------------------------------------------------------------ quality
  views.quality = page_("Quality", "Complexity, size and tests, measured from the source.", (report) => {
    const quality = report.sections.quality;
    if (!status(quality, "No source was found to measure.")) return;
    const root = main();
    const t = quality.totals;
    root.append(el("div", { class: "cards" }, stat(t.loc, "Lines"), stat(t.functions, "Functions"), stat(t.avg_complexity, "Average complexity"), stat(t.max_complexity, "Highest complexity"),
      stat(t.documented_ratio === null || t.documented_ratio === undefined ? null : `${Math.round(t.documented_ratio * 100)}%`, "Documented"), stat(t.test_functions, `Tests, in ${t.test_files} ${t.test_files === 1 ? "file" : "files"}`)));
    const hotspots = quality.hotspots || [];
    const heat = (value, top) => { const f = Math.min(1, (value || 0) / Math.max(top, 1)); return f > 0.66 ? "#ff6b3d" : (f > 0.33 ? "#ffb347" : "#ffd27a"); };
    const files = (quality.files || []).filter((f) => (f.loc || 0) > 0);
    const topComplexity = Math.max(...files.map((f) => f.max_complexity || 0), 1);
    let list = null;
    let cells = null;
    const showFile = (path) => {
      const f = files.find((x) => x.path === path);
      if (!f) return;
      cells?.select(path);
      list?.select(path);
      L.dock(L.detail({ title: path.split("/").pop(), where: path, facts: [[f.loc, "Lines"], [f.functions, "Functions"], [f.max_complexity, "Highest complexity"]] }, ...L.linkList("Most complex here", hotspots.filter((h) => h.path === path).map((h) => `${String(h.symbol).split(":").pop()}: ${h.complexity}`))));
    };
    const showHotspot = (key) => {
      const h = hotspots.find((x) => x.symbol === key);
      if (!h) return;
      cells?.select(h.path);
      list?.select(key);
      const panel = L.detail({ title: String(h.symbol).split(":").pop(), where: `${h.path}:${h.line}`, tags: h.estimated ? ["an estimate"] : [], facts: [[h.complexity, "Complexity"], [h.length, "Lines"]] });
      L.dock(panel);
      window.DevGuru.showSource(panel, `${h.path}:${h.line}`);
    };
    const frame = L.stage({ id: "quality-stage", legend: [["higher complexity", "ember"], ["lower", "saffron"]] });
    frame.hint("Size is lines, colour is the highest complexity in the file.");
    cells = L.treemap({ label: "Files by size and complexity", onSelect: showFile, items: files.slice(0, 120).map((f) => ({ id: f.path, label: f.path.split("/").pop(), sub: `${f.loc} lines`, value: f.loc, color: heat(f.max_complexity, topComplexity) })) });
    frame.fill(cells.canvas);
    root.append(frame.el);
    list = L.rail({ search: true, placeholder: "Find a function or file", onSelect: (id) => (hotspots.some((h) => h.symbol === id) ? showHotspot(id) : showFile(id)),
      groups: [{ title: "Most complex", items: hotspots.map((h) => ({ id: h.symbol, label: String(h.symbol).split(":").pop(), sub: h.path, count: h.complexity, tone: h.complexity > 20 ? "rose" : (h.complexity > 10 ? "ember" : "saffron") })) },
        { title: "Largest files", items: [...files].sort((a, b) => b.loc - a.loc).slice(0, 12).map((f) => ({ id: f.path, label: f.path.split("/").pop(), sub: f.path, count: f.loc, tone: "violet" })) }] });
    L.walk({ into: frame.el, go: showHotspot, steps: hotspots.slice(0, 8).map((h) => ({ id: h.symbol, text: `${String(h.symbol).split(":").pop()} in ${h.path} has a complexity of ${h.complexity}, over ${h.length} lines.` })) });
    if (hotspots.length) showHotspot(hotspots[0].symbol);
    const bands = [["1 to 5", 1, 5], ["6 to 10", 6, 10], ["11 to 20", 11, 20], ["Over 20", 21, Infinity]];
    const counts = bands.map(([, low, high]) => hotspots.filter((h) => h.complexity >= low && h.complexity <= high).length);
    const biggest = Math.max(...counts, 1);
    const chart = svg("svg", { class: "bars", viewBox: "0 0 420 130", role: "img", "aria-label": `Complexity of the ${hotspots.length} most complex functions: ${bands.map(([n], i) => `${n}: ${counts[i]}`).join(", ")}` });
    bands.forEach(([name], i) => {
      const height = (counts[i] / biggest) * 80;
      chart.append(svg("rect", { x: 20 + i * 100, y: 95 - height, width: 70, height, rx: 4, class: "bar" }),
        svg("text", { x: 55 + i * 100, y: 90 - height, "text-anchor": "middle", class: "col", text: String(counts[i]) }),
        svg("text", { x: 55 + i * 100, y: 115, "text-anchor": "middle", class: "col-type", text: name }));
    });
    root.append(el("h2", { text: "Most complex functions" }), el("p", { class: "muted", text: `How complex the ${hotspots.length} most complex functions are.` }), el("div", { class: "canvas-wrap bars-wrap" }, chart),
      table("hotspots", ["Function", "Complexity", "Lines", "Where"], hotspots.map((h) => [`${String(h.symbol).split(":").pop()}${h.estimated ? " (estimate)" : ""}`, h.complexity, h.length, `${h.path}:${h.line}`])));
    root.append(el("h2", { text: "Largest files" }), table("largest", ["File", "Lines", "Functions", "Highest complexity"], [...(quality.files || [])].sort((a, b) => (b.loc || 0) - (a.loc || 0)).slice(0, 20).map((f) => [f.path, f.loc, f.functions, f.max_complexity])));
    const more = limits(quality);
    if (more) root.append(more);
  });

  // ------------------------------------------------------------------ coverage
  // How the repository is tested, from its files: shown whether or not a coverage report exists
  const testTopology = (report, root) => {
    const t = report.sections.tests;
    if (!t || t.status !== "found") return;
    root.append(el("h2", { text: "How it's tested" }),
      el("div", { class: "cards" }, stat(t.files, "Test files"), stat(t.tests, "Tests"), stat(`${t.imported_by_tests} of ${t.source_files}`, "Source files a test imports")),
      table("test-suites", ["Kind", "Framework", "Files", "Tests", "Code it exercises"], (t.suites || []).map((s) => [s.kind, s.framework, s.files, s.tests, s.exercises_count])));
    if ((t.untested || []).length) {
      root.append(el("p", { class: "muted", text: `${t.untested_count} source files no test imports. A test may still reach them over HTTP or a subprocess, so this is inferred; coverage is the stronger evidence.` }),
        table("test-untested", ["Not imported by any test"], t.untested.map((p) => [p])));
    }
  };

  views.coverage = page_("Coverage", "What your tests cover, read from a report you already have. Tests aren't run here.", (report) => {
    const coverage = report.sections.coverage;
    const root = main();
    testTopology(report, root);
    if (coverage.status !== "found") {
      root.append(el("p", { id: "coverage-missing", text: "No coverage report was found, so coverage is unknown here, not zero." }),
        el("p", { class: "muted", text: "To produce one, run your tests with coverage, then analyse again:" }), el("pre", { class: "source" }, el("code", { text: "pytest --cov --cov-report=xml      # Python\nnpx jest --coverage                # JavaScript" })));
      L.nothing(root, "No coverage report here.", "No coverage report was found, so coverage is unknown here, not zero.");
      const more = limits(coverage);
      if (more) root.append(more);
      return;
    }
    const pct = (rate) => (rate === null || rate === undefined ? null : `${Math.round(rate * 100)}%`);
    const covered = coverage.files || [];
    const heat = (rate) => (rate === null || rate === undefined ? "#a19cb8" : (rate >= 0.8 ? "#3dd6c6" : (rate >= 0.5 ? "#ffb347" : "#ff6f91")));
    let list = null;
    let cells = null;
    const showFile = (path) => {
      const f = covered.find((x) => x.path === path);
      if (!f) return;
      cells?.select(path);
      list?.select(path);
      L.dock(L.detail({ title: path.split("/").pop(), where: path, facts: [[pct(f.line_rate), "Covered"], [f.lines_covered, "Lines run"], [f.lines_total, "Lines"]], note: f.line_rate === null || f.line_rate === undefined ? "The report doesn't say for this file." : `${f.lines_total === undefined ? "" : `${f.lines_total - f.lines_covered} lines weren't run by the tests.`}` }));
    };
    const coverageFrame = L.stage({ id: "coverage-stage", legend: [["80% or more", "teal"], ["50% or more", "saffron"], ["less", "rose"]] });
    coverageFrame.hint(`Size is lines, colour is how much the tests ran. From ${coverage.source}.`);
    cells = L.treemap({ label: "Files by size and coverage", onSelect: showFile, items: covered.slice(0, 120).map((f) => ({ id: f.path, label: f.path.split("/").pop(), sub: pct(f.line_rate) || "unknown", value: Math.max(f.lines_total || 1, 1), color: heat(f.line_rate) })) });
    coverageFrame.fill(cells.canvas);
    const leastFirst = [...covered].sort((a, b) => (a.line_rate ?? 0) - (b.line_rate ?? 0));
    list = L.rail({ search: true, placeholder: "Find a file", onSelect: showFile,
      groups: [{ title: "Least covered first", items: leastFirst.map((f) => ({ id: f.path, label: f.path.split("/").pop(), sub: f.path, count: pct(f.line_rate), tone: f.line_rate >= 0.8 ? "teal" : (f.line_rate >= 0.5 ? "saffron" : "rose") })) }] });
    root.append(coverageFrame.el);
    L.walk({ into: coverageFrame.el, go: showFile, steps: leastFirst.slice(0, 8).map((f) => ({ id: f.path, text: `${f.path}: ${pct(f.line_rate) || "unknown"} of its lines ran under the tests.` })) });
    if (leastFirst.length) showFile(leastFirst[0].path);
    root.append(el("div", { class: "cards" }, stat(pct(coverage.line_rate), "Lines covered"), stat(pct(coverage.branch_rate), "Branches covered"), stat((coverage.files || []).length, "Files reported")),
      el("p", { class: "muted mono", text: `From ${coverage.source}` }), el("h2", { text: "By file, least covered first" }),
      table("coverage-files", ["File", "Covered", "Lines"], [...(coverage.files || [])].sort((a, b) => (a.line_rate ?? 0) - (b.line_rate ?? 0)).map((f) => [f.path, pct(f.line_rate), f.lines_total === undefined ? "" : `${f.lines_covered} of ${f.lines_total}`])));
    const more = limits(coverage);
    if (more) root.append(more);
  });

  // ------------------------------------------------------------------ CVEs
  const RANK = { critical: 0, high: 1, moderate: 2, medium: 2, low: 3, unknown: 4 };

  views.cves = page_("CVEs", "Known vulnerabilities in the packages this repository depends on.", (report) => {
    const deps = report.sections.dependencies;
    const root = main();
    const packages = deps.packages || [];
    const unpinned = packages.filter((p) => !p.version).length;
    root.append(el("div", { class: "cards" }, stat(packages.length, "Packages"), stat(packages.filter((p) => p.direct).length, "Direct"), stat(unpinned, "Unpinned, so can't be checked")));
    const check = el("button", { type: "button", id: "check-cves", text: "Check for known vulnerabilities", on: { click: () => startAnalysis(true).catch((e) => showError(root, e)) } });
    const checked = !(deps.status === "not_scanned" || deps.vulnerabilities === null || deps.vulnerabilities === undefined);
    const advisories = checked ? [...deps.vulnerabilities].sort((a, b) => (RANK[a.severity] ?? 4) - (RANK[b.severity] ?? 4)) : [];
    const tone = (severity) => L.SEVERITY_TONE[severity] || "faint";
    const adviceId = (v) => `${v.package}|${v.id}`;
    const direct = packages.filter((p) => p.direct);
    let pictureSelect = () => {};
    let list = null;
    const showAdvice = (id) => {
      const v = advisories.find((x) => adviceId(x) === id);
      if (!v) return;
      pictureSelect(id);
      list?.select(id);
      L.dock(L.detail({ title: v.id, where: `${v.package} ${v.version}`, tags: [el("span", { class: `pill sev-${v.severity}`, text: v.severity }), ...(v.aliases || []).filter((a) => a.startsWith("CVE"))], note: v.summary, facts: [[v.version, "You have"], [v.fixed_in || "none known", "Fixed in"]] },
        el("p", { text: v.fixed_in ? `Upgrade ${v.package} to ${v.fixed_in} or later.` : `No fix is known for ${v.package} yet.` })));
    };
    const showPackage = (name) => {
      const p = packages.find((x) => x.name === name);
      if (!p) return;
      pictureSelect(name);
      list?.select(name);
      L.dock(L.detail({ title: p.name, where: p.manifest, tags: [p.direct ? (p.dev ? "direct, dev" : "direct") : "indirect", p.ecosystem], facts: [[p.version || "not pinned", "Version"]] },
        el("p", { class: "muted", text: checked ? "No known vulnerability, as of this analysis." : "Not checked, so nothing is known about this package yet." })));
    };
    const frame = L.stage({ id: "cve-stage", legend: advisories.length ? [...new Set(advisories.map((v) => v.severity))].map((s) => [s, tone(s)]) : [["not checked", "faint", true]] });
    if (advisories.length) {
      const hit = [...new Set(advisories.map((v) => v.package))];
      const adviceOf = (name) => advisories.filter((v) => v.package === name);
      const picture = L.radial({ center: "Your dependencies", sub: `${advisories.length} known ${advisories.length === 1 ? "vulnerability" : "vulnerabilities"}`, label: "Vulnerable packages round your dependencies", onSelect: (name) => showAdvice(adviceId(adviceOf(name)[0])),
        items: hit.map((name) => { const worst = adviceOf(name)[0]; return { id: name, label: name, sub: `${adviceOf(name).length} ${adviceOf(name).length === 1 ? "advisory" : "advisories"}, ${worst.severity}`, tone: tone(worst.severity), big: true }; }) });
      pictureSelect = (id) => picture.select(String(id).split("|")[0]);
      frame.fill(picture.canvas);
    } else if (!direct.length) {
      frame.fill(L.waiting(packages.length ? "All of these are indirect. They're listed below." : "No packages were found here."));
    } else {
      const shown = direct.slice(0, 44);
      const picture = L.radial({ center: "Your dependencies", sub: checked ? "none known, as of this analysis" : "not checked yet", label: "Direct dependencies", onSelect: showPackage,
        items: shown.map((p) => ({ id: p.name, label: p.name, sub: p.version || "not pinned", tone: checked ? "teal" : "faint" })), more: direct.length > shown.length ? `and ${direct.length - shown.length} more below` : "" });
      pictureSelect = picture.select;
      frame.fill(picture.canvas);
    }
    root.append(frame.el);
    list = L.rail({ search: true, placeholder: "Find a package", onSelect: (id) => (id.includes("|") ? showAdvice(id) : showPackage(id)),
      groups: [{ title: "Worst first", items: advisories.map((v) => ({ id: adviceId(v), label: v.package, sub: v.id, count: v.severity, tone: tone(v.severity) })) },
        { title: checked ? "Direct dependencies" : "Direct dependencies, not checked", items: direct.map((p) => ({ id: p.name, label: p.name, sub: p.version || "not pinned", tone: checked ? "teal" : "faint" })) }] });
    if (advisories.length) {
      L.walk({ into: frame.el, go: showAdvice, steps: advisories.slice(0, 10).map((v) => ({ id: adviceId(v), text: `${v.package} ${v.version}: ${v.severity}. ${v.fixed_in ? `Fixed in ${v.fixed_in}.` : "No fix known."}` })) });
      showAdvice(adviceId(advisories[0]));
    } else if (direct.length) showPackage(direct[0].name);
    if (deps.status === "not_scanned" || deps.vulnerabilities === null || deps.vulnerabilities === undefined) {
      root.append(el("p", { id: "cves-unknown", text: deps.status === "failed" ? "The check failed, so nothing is known about vulnerabilities here. That doesn't mean there are none." : "These packages haven't been checked, so nothing is known about vulnerabilities here yet." }),
        el("p", { class: "muted", text: "Checking sends package names and versions to https://osv.dev. Nothing else leaves your computer, and nothing is sent until you ask." }), check);
    } else {
      const found = [...deps.vulnerabilities].sort((a, b) => (RANK[a.severity] ?? 4) - (RANK[b.severity] ?? 4));
      if (!found.length) {
        root.append(el("p", { id: "cves-clean", text: `No known vulnerabilities in the ${packages.length - unpinned} packages checked, as of this analysis.` }));
      } else {
        const counts = Object.keys(RANK).map((name) => [name, found.filter((v) => v.severity === name).length]).filter(([, n]) => n);
        root.append(el("div", { class: "cards", id: "cve-counts" }, ...counts.map(([name, n]) => stat(n, name))),
          table("cve-list", ["Package", "Version", "Severity", "Advisory", "Fixed in", "Summary"], found.map((v) => [v.package, v.version, el("span", { class: `pill sev-${v.severity}`, text: v.severity }), [v.id, ...(v.aliases || []).filter((a) => a.startsWith("CVE"))].join(", "), v.fixed_in || "no fix known", String(v.summary || "").length > 180 ? `${String(v.summary).slice(0, 180)}...` : v.summary])));
      }
      root.append(check);
    }
    if (packages.length) {
      root.append(el("details", { id: "package-list" }, el("summary", { text: `All packages (${packages.length})` }),
        table("packages", ["Package", "Version", "Ecosystem", "Kind", "From"], packages.map((p) => [p.name, p.version || "not pinned", p.ecosystem, p.direct ? (p.dev ? "direct, dev" : "direct") : "indirect", p.manifest]))));
    }
    const more = limits(deps);
    if (more) root.append(more);
  });

  // ------------------------------------------------------------------ saving tokens
  // ---------------------------------------------------------------- findings
  const FIRST = { critical: 0, high: 1, medium: 2, low: 3 };
  views.findings = async () => {
    page("Findings", "What scanners and test runs already reported, from the reports in this repository, and what to fix first. Nothing was run.");
    const root = main();
    await withAnalysis(root, (report) => {
      const data = report.sections.findings;
      if (!data) { root.append(el("p", { text: "This analysis has no findings section. Analyse the repository again." })); return; }
      const found = data.findings || [];
      const tests = data.tests || [];
      const failed = tests.reduce((sum, t) => sum + t.failed, 0);
      const total = tests.reduce((sum, t) => sum + t.total, 0);
      root.append(el("div", { class: "cards" }, stat(data.reports?.length ? found.length : null, "Scanner findings"), stat(total ? total : null, "Tests in the reports"), stat(total ? failed : null, "Tests failing")));
      const worst = found.filter((f) => f.severity).slice(0, 44);
      const failures = tests.flatMap((t) => t.failures);
      const findingId = (f, i) => `finding:${i}`;
      const failureId = (f, i) => `test:${i}`;
      const items = [...failures.map((f, i) => ({ id: failureId(f, i), label: f.name, sub: "failing test", tone: "rose", big: true })),
        ...worst.map((f, i) => ({ id: findingId(f, i), label: f.rule, sub: f.path ? f.path.split("/").pop() : f.tool, tone: L.SEVERITY_TONE[f.severity] || "faint", big: FIRST[f.severity] <= 1 }))];
      let picture = null;
      let list = null;
      const show = (id) => {
        picture?.select(id);
        list?.select(id);
        const [kind, at] = id.split(":");
        if (kind === "test") {
          const f = failures[Number(at)];
          L.dock(L.detail({ title: f.name, where: f.report, tags: ["failing test"], note: f.message || "See the report." }));
          return;
        }
        const f = worst[Number(at)];
        const panel = L.detail({ title: f.rule, where: f.path ? `${f.path}${f.line ? `:${f.line}` : ""}` : "", tags: [el("span", { class: `pill sev-${f.severity}`, text: f.severity }), f.tool], note: f.message },
          f.remediation ? el("p", {}, el("strong", { text: "What to do: " }), f.remediation) : null);
        L.dock(panel);
        if (f.path && f.line) window.DevGuru.showSource(panel, `${f.path}:${f.line}`);
      };
      const frame = L.stage({ id: "findings-stage", legend: items.length ? [["critical or failing", "rose"], ["high", "ember"], ["medium", "saffron"], ["low", "teal"]] : [] });
      if (items.length) {
        picture = L.radial({ center: "This repository", sub: `${found.length} findings, ${failed} failing tests`, label: "Findings and failing tests", items, onSelect: show });
        frame.fill(picture.canvas);
      } else frame.fill(L.waiting(data.status === "not_found" ? "There's no SARIF or JUnit report here, so these are unknown." : "The reports here list nothing to fix."));
      root.append(frame.el);
      list = L.rail({ search: true, placeholder: "Find a rule or file", onSelect: show,
        groups: [{ title: "Failing tests", items: failures.map((f, i) => ({ id: failureId(f, i), label: f.name, sub: f.report, tone: "rose" })) },
          { title: "Worst first", items: worst.map((f, i) => ({ id: findingId(f, i), label: f.rule, sub: f.path, count: f.severity, tone: L.SEVERITY_TONE[f.severity] || "faint" })) }],
        note: "Nothing reported." });
      L.walk({ into: frame.el, go: show, steps: items.slice(0, 10).map((i) => ({ id: i.id, text: `${i.label}: ${i.sub}.` })) });
      if (items.length) show(items[0].id);
      if (data.status === "not_found") root.append(el("p", { id: "findings-unknown", text: "There's no SARIF or JUnit report here, so these are unknown. That doesn't mean there are none." }));
      const vulns = (report.sections.dependencies?.vulnerabilities || []).filter((v) => v.fixed_in);
      const steps = [
        ...tests.flatMap((t) => t.failures).slice(0, 10).map((f) => [`Failing test`, f.name, f.message || "See the report."]),
        ...found.filter((f) => FIRST[f.severity] <= 1).slice(0, 10).map((f) => [f.severity, `${f.rule} in ${f.path}${f.line ? `:${f.line}` : ""}`, f.remediation || f.message]),
        ...[...new Map(vulns.map((v) => [v.package, v])).values()].slice(0, 10).map((v) => ["Vulnerable package", `${v.package} ${v.version}`, `Upgrade to ${v.fixed_in} or later.`]),
      ];
      if (steps.length) root.append(el("h2", { text: "What to fix first" }), table("findings-first", ["What", "Where", "What to do"], steps));
      if (found.length) {
        root.append(el("h2", { text: data.findings_total > found.length ? `Scanner findings (worst ${found.length} of ${data.findings_total})` : "Scanner findings" }),
          table("findings-list", ["Severity", "Rule", "Where", "Tool", "Message"], found.map((f) => [el("span", { class: `pill sev-${f.severity}`, text: f.severity }), f.rule, f.path ? `${f.path}${f.line ? `:${f.line}` : ""}` : "", f.tool, f.message])));
      }
      if (tests.length) {
        root.append(el("h2", { text: "Test results" }), table("findings-tests", ["Report", "Total", "Passed", "Failed", "Skipped"], tests.map((t) => [t.report, t.total, t.passed, t.failed, t.skipped])));
        if (failures.length) root.append(table("findings-failures", ["Failing test", "Message", "Report"], failures.map((f) => [f.name, f.message, f.report])));
      }
      const more = limits(data);
      if (more) root.append(more);
    });
  };

  // ---------------------------------------------------------------- what's certain
  const SECTION_NAMES = { overview: "Overview", data: "Data", api: "API pathways", flows: "End-to-end flows", calm: "Architecture", quality: "Quality", coverage: "Coverage", dependencies: "CVEs", notebooks: "Notebooks", findings: "Findings" };
  const STATE_WORDS = { found: "Found", none: "Nothing here", not_found: "Unknown: no report here", not_scanned: "Unknown: not checked", failed: "This analysis failed", partial: "Partly read" };
  views.certainty = async () => {
    page("What's certain", "How far to trust each view: what was read, what was inferred, and everything the analysis couldn't tell.");
    const root = main();
    await withAnalysis(root, (report) => {
      const sections = Object.entries(report.sections);
      const count = (status) => sections.filter(([, s]) => s.status === status).length;
      const unknown = count("not_found") + count("not_scanned");
      const edges = report.sections.calm?.model?.relationships || [];
      const inferredTables = (report.sections.data?.tables || []).filter((t) => String(t.source || "").startsWith("inferred")).length;
      const notes = sections.reduce((sum, [, s]) => sum + (s.limits || []).length, 0);
      root.append(el("div", { class: "cards" }, stat(count("found"), "Views with results"), stat(unknown, "Views that are unknown"), stat(count("failed"), "Views that failed"), stat(notes, "Limits noted")));
      const TONE = { found: "teal", none: "violet", partial: "saffron", not_found: "faint", not_scanned: "faint", failed: "rose" };
      let picture = null;
      let list = null;
      const show = (name) => {
        const s = report.sections[name];
        picture?.select(name);
        list?.select(name);
        L.dock(L.detail({ title: SECTION_NAMES[name] || name, tags: [STATE_WORDS[s.status] || s.status], facts: [[(s.limits || []).length, "Limits"]] }, ...L.linkList("What it can't tell", s.limits || [])));
      };
      const frame = L.stage({ id: "certainty-stage", legend: [["has results", "teal"], ["partly read", "saffron"], ["unknown", "faint"], ["failed", "rose"]] });
      picture = L.radial({ center: "How far to trust this", sub: `${count("found")} of ${sections.length} views have results`, label: "Each view and its state", onSelect: show,
        items: sections.map(([name, s]) => ({ id: name, label: SECTION_NAMES[name] || name, sub: STATE_WORDS[s.status] || s.status, tone: TONE[s.status] || "faint" })) });
      frame.fill(picture.canvas);
      root.append(frame.el);
      list = L.rail({ search: true, placeholder: "Find a view", onSelect: show, groups: [{ title: "Views", items: sections.map(([name, s]) => ({ id: name, label: SECTION_NAMES[name] || name, sub: STATE_WORDS[s.status] || s.status, count: (s.limits || []).length, tone: TONE[s.status] || "faint" })) }] });
      L.walk({ into: frame.el, go: show, steps: sections.map(([name, s]) => ({ id: name, text: `${SECTION_NAMES[name] || name}: ${STATE_WORDS[s.status] || s.status}, with ${(s.limits || []).length} limits noted.` })) });
      if (sections.length) show(sections[0][0]);
      root.append(el("h2", { text: "What each view rests on" }), table("certainty-sections", ["View", "State", "Limits"], sections.map(([name, s]) => [SECTION_NAMES[name] || name, STATE_WORDS[s.status] || s.status, (s.limits || []).length])));
      root.append(el("h2", { text: "What's always inferred" }), el("ul", { id: "certainty-inferred" },
        el("li", { text: "Links between code come from names and imports, not from running it, so a call through a variable or a framework's magic can be missing." }),
        el("li", { text: `The architecture, with ${edges.length} ${edges.length === 1 ? "link" : "links"}, is read from files such as Compose files, so check it against what you know.` }),
        el("li", { text: `${inferredTables} ${inferredTables === 1 ? "table is" : "tables are"} known only from how code uses ${inferredTables === 1 ? "it" : "them"}, with no model or SQL file.` })));
      const rows = sections.flatMap(([name, s]) => (s.limits || []).map((limit) => [SECTION_NAMES[name] || name, limit]));
      root.append(el("h2", { text: "Everything it couldn't tell" }), rows.length ? table("certainty-limits", ["View", "Limit"], rows) : el("p", { class: "muted", text: "None noted." }));
    });
  };

  // ---------------------------------------------------------------- notebooks
  views.notebooks = async () => {
    page("Notebooks", "What each notebook does, in its own words, and how they feed each other. No cell was run.");
    const root = main();
    await withAnalysis(root, (report) => {
      const data = report.sections.notebooks;
      if (!status(data, "No notebooks here.")) return;
      const all = data.notebooks || [];
      const originals = all.filter((n) => !n.same_as);
      const copies = all.length - originals.length;
      root.append(el("div", { class: "cards" }, stat(originals.length, "Notebooks"), stat(data.written_total, "Files they write"), stat((data.links || []).length, "Links between them"),
        stat(originals.reduce((sum, n) => sum + n.cells.code, 0), "Code cells")));
      if (copies) root.append(el("p", { class: "muted", id: "notebook-copies", text: `${copies} ${copies === 1 ? "copy" : "copies"} of these, such as an executed version, aren't counted again.` }));
      const detail = el("div", { id: "notebook-detail" });
      let list = null;
      const paths = originals.map((n) => n.path);
      const byPath = new Map(originals.map((n) => [n.path, n]));
      let current = 0;
      const short = (path) => path.split("/").pop().replace(/\.ipynb$/, "");
      const rows = (id, title, heads, body) => (body.length ? [el("h3", { text: title }), table(id, heads, body)] : []);
      const words = (list, none) => (list.length ? list.join(", ") : none);
      const show = (index) => {
        current = Math.max(0, Math.min(paths.length - 1, index));
        const n = byPath.get(paths[current]);
        list?.select(n.path);
        const from = (data.links || []).filter((l) => l.to === n.path);
        const to = (data.links || []).filter((l) => l.from === n.path);
        const facts = [`${n.cells.code} code cells and ${n.cells.markdown} text cells.`];
        if (n.written.length) facts.push(`It writes ${n.written.length} ${n.written.length === 1 ? "file" : "files"}.`);
        if (n.defines.length) facts.push(`It defines ${n.defines.length} functions and classes of its own.`);
        const fed = new Set(from.map((l) => l.from)).size;
        const feeds = new Set(to.map((l) => l.to)).size;
        if (fed) facts.push(`It builds on ${fed} other ${fed === 1 ? "notebook" : "notebooks"}.`);
        if (feeds) facts.push(feeds === 1 ? "One other notebook builds on it." : `${feeds} other notebooks build on it.`);
        const outline = el("ol", { class: "notebook-outline", id: "notebook-outline" }, ...n.outline.map((o) => el("li", { class: `level-${o.level}` },
          el("strong", { text: o.title }), el("span", { class: "muted mono", text: ` cell ${o.cell}` }), o.summary ? el("p", { text: o.summary }) : null)));
        const source = el("div", { id: "notebook-source" });
        const written = n.written.map((w) => [
          el("button", { type: "button", class: "ghost link", text: w.path, on: { click: () => showWritten(source, w.path) } }),
          `cell ${w.cell}`, w.lines, w.symbols.join(", ") || "",
        ]);
        graph.highlight(new Set([n.path, ...from.map((l) => l.from), ...to.map((l) => l.to)]), n.path);
        L.dock(L.detail({ title: n.title, where: n.path, note: n.purpose, facts: [[n.cells.code, "Code cells"], [n.written.length, "Files written"], [n.defines.length, "Defines"]] },
          el("p", { id: "notebook-facts", text: facts.join(" ") }),
          ...L.linkList("Builds on", [...new Set(from.map((l) => short(l.from)))]),
          ...L.linkList("Used by", [...new Set(to.map((l) => short(l.to)))]),
          el("h3", { class: "eyebrow", text: "Packages" }), el("div", { class: "tagline" }, ...(n.imports.length ? n.imports.slice(0, 16).map((name) => el("span", { class: "tag", text: name })) : [el("span", { class: "muted", text: "none found" })]))));
        detail.replaceChildren(el("h2", { id: "notebook-title", text: n.title }),
          ...(n.purpose ? [el("p", { id: "notebook-purpose", text: n.purpose })] : []),
          ...(n.outline.length ? [el("h3", { text: n.outline_total > n.outline.length ? `What it covers (first ${n.outline.length} of ${n.outline_total})` : "What it covers" }), outline] : []),
          ...rows("notebook-written", "Files it writes", ["File", "Where", "Lines", "Defines"], written), source,
          ...rows("notebook-from", "Builds on", ["Notebook", "Through", "How"], from.map((l) => [short(l.from), l.via, l.kind])),
          ...rows("notebook-to", "Used by", ["Notebook", "Through", "How"], to.map((l) => [short(l.to), l.via, l.kind])),
          el("h3", { text: "What it uses" }), el("p", {}, el("strong", { text: "Packages: " }), words(n.imports, "none found")),
          el("p", {}, el("strong", { text: "Data it reads: " }), words(n.reads, "none named in its code")),
          el("p", {}, el("strong", { text: "Data it writes: " }), words(n.writes, "none named in its code")),
          ...(n.defines.length ? [el("p", {}, el("strong", { text: "Defines: " }), n.defines.join(", "))] : []));
      };
      const showWritten = async (box, path) => {
        box.replaceChildren(el("p", { class: "muted", text: `Loading ${path}...` }));
        try {
          const found = await window.DevGuru.api(window.DevGuru.scoped("/api/v1/source", { path }));
          box.replaceChildren(el("h3", { text: path }), el("pre", { class: "source" }, el("code", { text: found.lines.join("\n") })));
        } catch (error) {
          box.replaceChildren(el("p", { class: "muted", text: `Source isn't available: ${error.message}` }));
        }
      };
      const pairs = new Map();
      for (const link of data.links || []) {
        if (!byPath.has(link.from) || !byPath.has(link.to)) continue;
        const key = `${link.from}\0${link.to}`;
        const pair = pairs.get(key) || { source: link.from, target: link.to, kind: "calls", kindLabel: "builds on", kinds: ["calls"], count: 0 };
        pair.count += 1;
        pairs.set(key, pair);
      }
      const graph = window.DevGuru.drawGraph({
        nodes: originals.map((n) => ({ id: n.path, kind: "file", label: short(n.path), sub: n.folder })),
        edges: [...pairs.values()],
        label: "How the notebooks feed each other",
        onSelect: (node) => show(paths.indexOf(node.id)),
      });
      L.tools(
        el("button", { type: "button", class: "chip", id: "notebook-previous", text: "‹ Previous notebook", on: { click: () => show(current - 1) } }),
        el("button", { type: "button", class: "chip", id: "notebook-next", text: "Next notebook ›", on: { click: () => show(current + 1) } }));
      const frame = L.stage({ id: "notebook-stage", legend: [["builds on", "saffron"]], hint: "Hover a notebook to see what feeds it." });
      frame.fill(el("div", { class: "canvas-wrap", id: "notebook-graph" }, graph.canvas), window.DevGuru.panZoom(graph.canvas));
      root.append(frame.el, detail);
      list = L.rail({ search: true, placeholder: "Find a notebook", onSelect: (p) => show(paths.indexOf(p)),
        groups: (data.groups || []).map((group) => ({ title: group.folder, items: group.notebooks.filter((p) => byPath.has(p)).map((p) => ({ id: p, label: byPath.get(p).title, sub: short(p), count: byPath.get(p).written.length || undefined })) })) });
      L.walk({ into: frame.el, go: (p) => show(paths.indexOf(p)), steps: originals.map((n) => ({ id: n.path, text: `${n.title}: ${n.purpose || `${n.cells.code} code cells, writing ${n.written.length} files.`}` })) });
      const more = limits(data);
      if (more) root.append(more);
      if (paths.length) show(0);
    });
  };

  views.context = async () => {
    page("Saving tokens", "A small map of this repository for an AI assistant, and which tool to use next.");
    const root = main();
    try {
      const context = await window.DevGuru.api(window.DevGuru.scoped("/api/v1/context"));
      L.tools(el("button", { type: "button", class: "chip", id: "copy-map", text: "Copy the map", on: { click: async (e) => { await navigator.clipboard.writeText(context.map); e.target.textContent = "Copied"; } } }));
      const questions = context.routes.map((r, i) => ({ ...r, id: `q${i}` }));
      const toolNames = [...new Set(questions.map((r) => r.use))];
      let graph = null;
      let list = null;
      const show = (id) => {
        const r = questions.find((q) => q.id === id);
        if (!r) return;
        graph?.highlight(new Set([id, `tool:${r.use}`]), id);
        list?.select(id);
        L.dock(L.detail({ title: r.question, tags: [r.use], note: r.why }));
      };
      graph = window.DevGuru.drawGraph({ label: "Which tool answers which question",
        nodes: [...questions.map((q) => ({ id: q.id, kind: "question", label: q.question, sub: "a question" })), ...toolNames.map((name) => ({ id: `tool:${name}`, kind: "handler", label: name, sub: "the cheapest answer" }))],
        edges: questions.map((q) => ({ source: q.id, target: `tool:${q.use}`, kind: "calls", kindLabel: "use" })),
        onSelect: (node) => { if (!node.id.startsWith("tool:")) show(node.id); } });
      const frame = L.stage({ id: "context-stage", legend: [["the cheapest way to answer", "saffron"]], hint: "Each question, and the tool that answers it for the fewest tokens." });
      frame.fill(el("div", { class: "canvas-wrap" }, graph.canvas), window.DevGuru.panZoom(graph.canvas));
      list = L.rail({ search: true, placeholder: "Find a question", onSelect: show,
        insights: [{ title: "The map", text: `About ${context.tokens_estimate} tokens, ${context.cached ? "from its saved copy" : "just rebuilt"}`, onClick: () => document.querySelector("#context-map")?.scrollIntoView({ block: "nearest" }) }],
        groups: [{ title: "Questions", items: questions.map((q) => ({ id: q.id, label: q.question, sub: q.use })) }] });
      root.append(el("div", { class: "cards" }, stat(context.tokens_estimate, "Tokens in this map"), stat("Yes", context.cached ? "Up to date, from its saved copy" : "Up to date, just rebuilt"), stat(context.budget, "Budget")),
        frame.el,
        el("pre", { class: "source", id: "context-map" }, el("code", { text: context.map })),
        el("h2", { text: "Which tool for which question" }), table("routes-table", ["Question", "Use", "Why"], context.routes.map((r) => [r.question, r.use, r.why])),
        el("h2", { text: "Using it by default" }), el("p", { class: "muted", text: "This adds a note of about 80 tokens where your assistant reads project instructions, for Claude Code, Codex, Copilot, Kiro, Cursor and Amazon Q. --local keeps it out of commits. ananke context disable removes it." }),
        el("pre", { class: "source" }, el("code", { text: "ananke context enable --local --dry-run\nananke context enable --local" })),
        el("h2", { text: "Tools" }), table("context-tools", ["Tool", "Ready", "For", "Licence", "Set up"], Object.entries(context.tools).map(([name, tool]) => [name, tool.ready ? "yes" : "no", tool.for, tool.licence, typeof tool.setup === "string" ? tool.setup : (tool.setup ? tool.setup.add_to_claude_code : "")])));
      L.walk({ into: frame.el, go: show, steps: questions.map((q) => ({ id: q.id, text: `${q.question} Use ${q.use}: ${q.why}` })) });
      if (questions.length) show(questions[0].id);
    } catch (error) {
      showError(root, error);
    }
  };
})();
