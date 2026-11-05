// Data, API pathways, architecture, quality, coverage and CVEs. Unknown is never shown as zero or as clean.
"use strict";

(() => {
  const { el, page, views, withAnalysis, startAnalysis, showError, when } = window.DevGuru;
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
    main().append(el("p", { class: "muted", id: "section-status", text: section.status === "failed" ? "This analysis failed, so nothing is known here." : none }));
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
    const heights = Array(columnsAcross).fill(20);
    order.forEach((name, i) => {
      const x = i % columnsAcross;
      const visible = Math.min(byName.get(name).columns.length, 10);
      const height = HEAD + visible * ROW + (byName.get(name).columns.length > 10 ? ROW : 0) + 8;
      place.set(name, { x: 20 + x * (CARD_WIDTH + 90), y: heights[x], height });
      heights[x] += height + 44;
    });
    const canvas = svg("svg", { class: "erd", viewBox: `0 0 ${40 + columnsAcross * (CARD_WIDTH + 90)} ${Math.max(...heights) + 20}`, role: "group", "aria-label": `Diagram of ${order.length} tables` });
    const lines = svg("g");
    for (const r of relationships) {
      const from = place.get(r.from_table);
      const to = place.get(r.to_table);
      if (!from || !to || r.from_table === r.to_table) continue;
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
      const line = svg("path", { d: `M${x1} ${y1} C${x1 + bendOut} ${y1} ${x2 - bendIn} ${y2} ${x2} ${y2}`, class: `rel${r.origin === "inferred" ? " inferred" : ""}`, "marker-end": "url(#one)", "marker-start": r.cardinality === "one-to-one" ? "url(#one)" : "url(#many)" },
        svg("title", { text: `${r.from_table}.${r.from_column} to ${r.to_table}.${r.to_column}, ${r.cardinality}` }));
      lines.append(line);
    }
    const cards = svg("g");
    for (const name of order) {
      const t = byName.get(name);
      const at = place.get(name);
      const inferred = String(t.source || "").startsWith("inferred");
      const card = svg("g", { class: `table-card${inferred ? " inferred" : ""}`, transform: `translate(${at.x} ${at.y})`, tabindex: "0", role: "button", "aria-label": `Table ${name}, ${t.columns.length} columns` },
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
    return canvas;
  }

  views.data = page_("Data", "The tables this repository defines or uses, how they relate, and which code touches them.", (report) => {
    const data = report.sections.data;
    if (!status(data, "No tables were found: no ORM models, SQL files or SQL in the code that this analysis can read.")) return;
    const root = main();
    const tables = data.tables;
    const inferredCount = tables.filter((t) => String(t.source || "").startsWith("inferred")).length;
    root.append(el("div", { class: "cards" }, stat(tables.length, "Tables"), stat(data.relationships.length, "Relationships"), stat(data.usage.length, "Places code uses them"), stat(inferredCount, "Known only from use")));
    root.append(el("div", { class: "row" },
      el("button", { type: "button", class: "ghost", id: "copy-erd", text: "Copy Mermaid ERD", on: { click: async (e) => { await navigator.clipboard.writeText(data.erd_mermaid); e.target.textContent = "Copied"; } } }),
      el("button", { type: "button", class: "ghost", id: "download-erd", text: "Download Mermaid ERD", on: { click: () => download("erd.mmd", data.erd_mermaid, "text/plain") } })));
    const detail = el("aside", { class: "inspector", id: "table-detail", "aria-live": "polite" }, el("p", { class: "muted", text: "Select a table to see its fields and the code that uses it." }));
    const select = (t) => {
      const uses = data.usage.filter((u) => u.table === t.name);
      const related = data.relationships.filter((r) => r.from_table === t.name || r.to_table === t.name);
      detail.replaceChildren(el("h2", { text: t.name }), el("p", { class: "muted mono", text: `${t.source}: ${t.evidence || "no definition found"}` }),
        table("table-columns", ["Field", "Type", "Key", "Null"], t.columns.map((c) => [c.name, c.type, c.primary_key ? "primary" : (c.foreign_key ? `to ${c.foreign_key}` : ""), c.nullable === false ? "no" : (c.nullable ? "yes" : "")])),
        el("h3", { text: `Code that uses it (${uses.length})` }),
        uses.length ? el("ul", { id: "table-usage" }, ...uses.map((u) => el("li", {}, el("strong", { text: u.access }), ` ${String(u.symbol).split(":").slice(1).join(":")} `, el("span", { class: "muted mono", text: u.evidence })))) : el("p", { class: "muted", text: "No code found using it." }),
        el("h3", { text: `Relationships (${related.length})` }),
        el("ul", {}, ...related.map((r) => el("li", { text: `${r.from_table}.${r.from_column} to ${r.to_table}.${r.to_column}, ${r.cardinality}` }))));
    };
    const stage = el("div", { id: "erd-stage" });
    const groupOf = (t) => t.schema || String(t.evidence || "").split("/")[0] || "other";
    const draw = (shown) => {
      const names = new Set(shown.map((t) => t.name));
      stage.replaceChildren(el("div", { class: "canvas-wrap" }, erd(shown, data.relationships.filter((r) => names.has(r.from_table) && names.has(r.to_table)), select)));
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
    root.append(el("div", { class: "map-layout" }, stage, detail));
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
    if (broken.length) {
      root.append(el("div", { class: "card warn-card", id: "api-broken" }, el("h2", { text: "These calls have no route here" }), el("p", { class: "muted", text: "They may be bugs, or may reach a service outside this repository." }),
        table("broken-calls", ["Call", "From"], broken.map((c) => [`${c.method} ${c.path}`, c.evidence]))));
    }
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
      const canvas = svg("svg", { class: "erd", viewBox: `0 0 ${40 + across * (width + 80)} ${20 + down * 100}`, role: "group", "aria-label": `Architecture of ${components.length} components` });
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
        lines.append(svg("path", { d: `M${x1} ${a.y + 35} C${x1 + out} ${a.y + 35} ${x2 - back} ${b.y + 35} ${x2} ${b.y + 35}`, class: "rel inferred", "marker-end": "url(#arch)", "data-from": r.source, "data-to": r.target }, svg("title", { text: `${r.source} to ${r.target}: ${r.type || ""} ${r.evidence || ""}` })));
      }
      const boxes = svg("g");
      for (const c of components) {
        const p = at.get(c.id);
        boxes.append(svg("g", { class: `table-card kind-${c.type || "other"}`, "data-component": c.id, "data-column": String(depth.get(c.id)), transform: `translate(${p.x} ${p.y})` },
          svg("rect", { width, height: 70, rx: 10 }), svg("text", { x: 12, y: 28, class: "table-name", text: short(c.name || c.id, 24) }), svg("text", { x: 12, y: 50, class: "col-type", text: c.type || "" })));
      }
      canvas.append(svg("defs", {}, svg("marker", { id: "arch", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 7, markerHeight: 7, orient: "auto" }, svg("path", { d: "M0 0L8 4L0 8z", class: "arrow-head" }))), lines, boxes);
      root.append(el("div", { class: "canvas-wrap", id: "calm-diagram" }, canvas),
        el("div", { class: "row" }, el("button", { type: "button", class: "ghost", id: "download-calm", text: "Download CALM model", on: { click: () => download("system.calm.json", JSON.stringify(model, null, 2), "application/json") } })),
        el("h2", { text: "How they connect" }),
        relations.length ? table("calm-links", ["From", "To", "How", "Evidence"], relations.map((r) => [r.source, r.target, r.type, r.evidence])) : el("p", { class: "muted", text: "No links between components were found." }));
      if (calm.drift) root.append(el("h2", { text: "Differences from the declared model" }), el("pre", { class: "source" }, el("code", { text: JSON.stringify(calm.drift, null, 1) })));
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
  views.coverage = page_("Coverage", "What your tests cover, read from a report you already have. Tests aren't run here.", (report) => {
    const coverage = report.sections.coverage;
    const root = main();
    if (coverage.status !== "found") {
      root.append(el("p", { id: "coverage-missing", text: "No coverage report was found, so coverage is unknown here, not zero." }),
        el("p", { class: "muted", text: "To produce one, run your tests with coverage, then analyse again:" }), el("pre", { class: "source" }, el("code", { text: "pytest --cov --cov-report=xml      # Python\nnpx jest --coverage                # JavaScript" })));
      const more = limits(coverage);
      if (more) root.append(more);
      return;
    }
    const pct = (rate) => (rate === null || rate === undefined ? null : `${Math.round(rate * 100)}%`);
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
          table("cve-list", ["Package", "Version", "Severity", "Advisory", "Fixed in", "Summary"], found.map((v) => [v.package, v.version, el("span", { class: `pill sev-${v.severity}`, text: v.severity }), [v.id, ...(v.aliases || []).filter((a) => a.startsWith("CVE"))].join(", "), v.fixed_in || "no fix known", v.summary])));
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
  views.context = async () => {
    page("Saving tokens", "A small map of this repository for an AI assistant, and which tool to use next.");
    const root = main();
    try {
      const context = await window.DevGuru.api(window.DevGuru.scoped("/api/v1/context"));
      root.append(el("div", { class: "cards" }, stat(context.tokens_estimate, "Tokens in this map"), stat("Yes", context.cached ? "Up to date, from its saved copy" : "Up to date, just rebuilt"), stat(context.budget, "Budget")),
        el("div", { class: "row" }, el("button", { type: "button", class: "ghost", id: "copy-map", text: "Copy the map", on: { click: async (e) => { await navigator.clipboard.writeText(context.map); e.target.textContent = "Copied"; } } })),
        el("pre", { class: "source", id: "context-map" }, el("code", { text: context.map })),
        el("h2", { text: "Which tool for which question" }), table("routes-table", ["Question", "Use", "Why"], context.routes.map((r) => [r.question, r.use, r.why])),
        el("h2", { text: "Using it by default" }), el("p", { class: "muted", text: "This adds a short note where your assistant reads project instructions, for Claude Code, Codex, Copilot, Kiro, Cursor and Amazon Q. ananke context disable removes it." }),
        el("pre", { class: "source" }, el("code", { text: "ananke context enable --dry-run\nananke context enable" })),
        el("h2", { text: "Tools" }), table("context-tools", ["Tool", "Ready", "For", "Licence", "Set up"], Object.entries(context.tools).map(([name, tool]) => [name, tool.ready ? "yes" : "no", tool.for, tool.licence, typeof tool.setup === "string" ? tool.setup : (tool.setup ? tool.setup.add_to_claude_code : "")])));
    } catch (error) {
      showError(root, error);
    }
  };
})();
