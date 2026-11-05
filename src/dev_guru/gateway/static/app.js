// The Dev Guru web interface. No build step and no dependencies. Text from the server only ever reaches the page through
// textContent, so a hostile file name or message stays text. All domain decisions are Ananke's; this only shows them.
"use strict";

const ACTIVE = new Set(["queued", "running"]);
const POLL_MS = 1000;
const MAX_BACKOFF_MS = 8000;
const RUN_ID = /^run-[0-9a-f]+$/; // the only form the gateway accepts
const LINK = /^(#\/|\/api\/v1\/)/; // pages here and gateway routes, so no value can become a javascript: link
const state = { csrf: null, csrfHeader: null, workspaces: [], workspace: null, stop: null, graphKey: null, shown: 0 };

function el(tag, props, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (key === "text") node.textContent = value;
    else if (key === "href" && !LINK.test(value)) throw new TypeError("not a link this interface makes");
    else if (key === "on") for (const [name, fn] of Object.entries(value)) node.addEventListener(name, fn);
    else if (value !== undefined && value !== null && value !== false) node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children) if (child !== null && child !== undefined) node.append(child);
  return node;
}

class ApiError extends Error {
  constructor(status, code, message, retryable) {
    super(message);
    Object.assign(this, { status, code, retryable });
  }
}

async function api(path, body) {
  if (window.DEV_GURU_STATIC) {
    try {
      return window.DEV_GURU_STATIC(path, body);
    } catch (error) {
      throw new ApiError(error.status || 404, error.code || "NOT_IN_THIS_REPORT", error.message, false);
    }
  }
  const options = { credentials: "same-origin" };
  if (body !== undefined) {
    options.method = "POST";
    options.headers = { "Content-Type": "application/json", [state.csrfHeader]: state.csrf };
    options.body = JSON.stringify({ workspace: state.workspace, ...body });
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError(0, "UNREACHABLE", "Can't reach the gateway.", true);
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(response.status, "BAD_RESPONSE", "The gateway sent an unreadable response.", false);
  }
  if (response.ok) return data;
  const error = data.error || {};
  if (response.status === 401) banner("Your session has ended. Run dev serve again and open the new link.", true);
  throw new ApiError(response.status, error.code || "ERROR", error.message || "The request failed.", !!error.retryable);
}

const scoped = (path, query = {}) => {
  const params = new URLSearchParams({ workspace: state.workspace, ...query });
  return `${path}?${params}`;
};

function banner(text, bad = false) {
  const node = document.querySelector("#banner");
  node.hidden = !text;
  node.textContent = text || "";
  node.classList.toggle("bad", bad);
}

function showError(main, error, ...actions) {
  main.append(el("div", { class: "card warning", role: "alert" },
    el("strong", { text: error.code }), el("p", { text: error.message }), ...actions));
}

function page(title, lede) {
  // A new section each time: whatever an earlier page is still waiting for lands in one that's gone.
  window.DevGuru.lantern?.reset();
  const section = el("section", {}, el("header", { class: "stage-head" },
    el("div", {}, el("h1", { text: title }), lede ? el("p", { class: "lede", text: lede }) : null),
    el("div", { class: "stage-tools", id: "stageTools" })));
  document.querySelector("#main").replaceChildren(section);
  document.title = `${title} · Dev Guru`;
  return section;
}

const statePill = (value) => el("span", { class: `pill ${value}`, text: value });

function when(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? String(iso || "") : date.toLocaleString();
}

function warnings(run) {
  return (run.warnings || []).map((w) => el("div", { class: "card warning" },
    el("strong", { text: w.code }), el("p", { text: w.message })));
}

// ------------------------------------------------------------------ overview
async function overview() {
  const main = page("Overview", "What's connected. Ananke does the work; Dev Guru shows it to you.");
  try {
    const [health, caps, runs] = await Promise.all([
      api("/api/v1/health"), api(scoped("/api/v1/capabilities")), api(scoped("/api/v1/runs")),
    ]);
    main.append(el("div", { class: "cards" },
      el("div", { class: "card" }, el("span", { class: "stat", text: health.harness.ananke_version || "none" }), "Ananke Plexus"),
      el("div", { class: "card" }, el("span", { class: "stat", text: health.gateway }), "Dev Guru"),
      el("div", { class: "card" }, el("span", { class: "stat", text: String(runs.total) }), "Runs in this workspace")));
    await repositorySummary(main, runs);
    main.append(el("h2", { text: "What the harness can run" }));
    main.append(el("div", { class: "row" }, ...caps.run_kinds.map((k) => el("code", { class: "pill", text: k }))));
  } catch (error) {
    showError(main, error);
  }
}

// One line for each repository view, or an offer to analyse. Unknown stays unknown.
async function repositorySummary(main, runs) {
  const L = window.DevGuru.lantern;
  const analysed = (runs.runs || []).some((r) => r.kind === "repo.analyze" && r.state === "succeeded");
  // The stage first: it goes above the words that follow.
  const frame = L.stage({ id: "overview-stage", legend: [["has results", "teal"], ["needs a look", "ember"], ["unknown", "faint"]], hint: "Every view of this repository. Select one for a line about it." });
  main.append(frame.el);
  const paint = (items, center) => {
    let picture = null;
    let list = null;
    const show = (id) => {
      const item = items.find((i) => i.id === id);
      if (!item) return;
      picture.select(id);
      list.select(id);
      L.dock(L.detail({ title: item.label, note: item.sub, actions: [el("a", { class: "btn", href: `#/${item.href.slice(2)}`, text: `Open ${item.label}` })] }));
    };
    picture = L.radial({ center, sub: `${items.length} views`, label: "Every view of this repository", items, onSelect: show });
    frame.fill(picture.canvas);
    list = L.rail({ search: true, placeholder: "Find a view", onSelect: show, insights: [{ title: "Runs", text: `${runs.total} in this workspace`, href: "#/runs" }, { title: "Code", text: "Explore the code graph", href: "#/code" }],
      groups: [{ title: "Views", items: items.map((i) => ({ id: i.id, label: i.label, sub: i.sub, tone: i.tone })) }] });
    L.walk({ into: frame.el, go: show, steps: items.map((i) => ({ id: i.id, text: `${i.label}: ${i.sub}.` })) });
    if (items.length) show(items[0].id);
  };
  main.append(el("h2", { text: "This repository" }));
  if (!analysed) {
    paint(["Code map", "End-to-end flows", "Data", "API pathways", "Architecture", "Quality", "Coverage", "CVEs"].map((label, i) => ({ id: `v${i}`, label, sub: "not analysed yet", tone: "faint", href: "#/map" })), "This repository");
    main.append(el("p", { id: "overview-unanalysed", text: "It hasn't been analysed yet. " }, el("a", { href: "#/map", text: "Open the code map to analyse it" })));
    return;
  }
  const report = await api(scoped("/api/v1/intel"));
  const s = report.sections;
  const line = (href, title, text) => el("tr", {}, el("td", {}, el("a", { href, text: title })), el("td", { text }));
  const count = (list, noun) => `${(list || []).length} ${noun}${(list || []).length === 1 ? "" : "s"}`;
  const vulns = s.dependencies.vulnerabilities;
  main.append(el("table", { id: "overview-sections" }, el("tbody", {},
    line("#/map", "Code map", `${s.overview.files} files, ${s.overview.loc} lines`),
    line("#/flows", "End-to-end flows", count(s.flows.flows, "flow")),
    line("#/data", "Data", `${count(s.data.tables, "table")}, ${count(s.data.relationships, "relationship")}`),
    line("#/apis", "API pathways", `${count(s.api.routes, "route")}, ${count(s.api.unmatched_clients, "call")} with no route here`),
    line("#/architecture", "Architecture", `${count(s.overview.components, "component")}, inferred`),
    line("#/quality", "Quality", `Average complexity ${s.quality.totals?.avg_complexity ?? "unknown"}`),
    line("#/coverage", "Coverage", typeof s.coverage.line_rate === "number" ? `${Math.round(s.coverage.line_rate * 100)}% of lines` : "Unknown: no report found"),
    line("#/cves", "CVEs", vulns === null || vulns === undefined ? "Not checked" : count(vulns, "known vulnerability").replace("vulnerabilitys", "vulnerabilities")),
    line("#/context", "Saving tokens", "A small map for an AI assistant"))));
  const known = (ok) => (ok ? "teal" : "faint");
  const tally = (list) => (list || []).length;
  const covered = typeof s.coverage.line_rate === "number";
  const broken = (s.api.unmatched_clients || []).filter((c) => !c.base_unknown && !c.external).length;
  const items = [
    { href: "#/map", label: "Code map", sub: `${s.overview.files} files, ${s.overview.loc} lines`, tone: "teal", big: true },
    { href: "#/flows", label: "End-to-end flows", sub: count(s.flows.flows, "flow"), tone: known(tally(s.flows.flows)) },
    { href: "#/data", label: "Data", sub: `${count(s.data.tables, "table")}, ${count(s.data.relationships, "relationship")}`, tone: known(tally(s.data.tables)) },
    { href: "#/apis", label: "API pathways", sub: `${count(s.api.routes, "route")}${broken ? `, ${broken} ${broken === 1 ? "call leads" : "calls lead"} nowhere` : ""}`, tone: broken ? "ember" : known(tally(s.api.routes)) },
    { href: "#/architecture", label: "Architecture", sub: `${count(s.overview.components, "component")}, inferred`, tone: "teal" },
    { href: "#/quality", label: "Quality", sub: `Average complexity ${s.quality.totals?.avg_complexity ?? "unknown"}`, tone: "teal" },
    { href: "#/coverage", label: "Coverage", sub: covered ? `${Math.round(s.coverage.line_rate * 100)}% of lines` : "Unknown: no report found", tone: covered ? (s.coverage.line_rate < 0.5 ? "ember" : "teal") : "faint" },
    { href: "#/cves", label: "CVEs", sub: vulns === null || vulns === undefined ? "Not checked" : count(vulns, "known vulnerability").replace("vulnerabilitys", "vulnerabilities"), tone: vulns === null || vulns === undefined ? "faint" : (vulns.length ? "rose" : "teal"), big: !!vulns?.length },
    ...(s.findings ? [{ href: "#/findings", label: "Findings", sub: s.findings.status === "not_found" ? "Unknown: no report here" : count(s.findings.findings, "finding"), tone: s.findings.status === "not_found" ? "faint" : (tally(s.findings.findings) ? "ember" : "teal") }] : []),
    ...(tally(s.notebooks?.notebooks) ? [{ href: "#/notebooks", label: "Notebooks", sub: count(s.notebooks.notebooks, "notebook"), tone: "violet" }] : []),
    { href: "#/certainty", label: "What's certain", sub: "How far to trust each view", tone: "violet" },
    { href: "#/context", label: "Saving tokens", sub: "A small map for an AI assistant", tone: "violet" },
  ].map((item) => ({ ...item, id: item.href }));
  paint(items, s.overview.name || "This repository");
}

// ------------------------------------------------------------------ runs
async function startGraphRun(after) {
  // Trying again after a lost connection repeats the same request, in case the first one did arrive.
  state.graphKey = state.graphKey || crypto.randomUUID();
  let run;
  try {
    run = await api("/api/v1/runs", { kind: "graph.build", parameters: {}, idempotency_key: state.graphKey });
  } catch (error) {
    if (error.status !== 0) state.graphKey = null;
    throw error;
  }
  state.graphKey = null;
  after(run);
}

async function runs() {
  const main = page("Runs", "Runs live in Ananke, so they survive a reload or a closed tab.");
  const start = el("button", { type: "button", id: "start-graph", text: "Build the code graph" });
  const slot = el("div");
  start.addEventListener("click", async () => {
    start.disabled = true;
    slot.replaceChildren();
    try {
      await startGraphRun((run) => { location.hash = `#/runs/${run.run_id}`; });
    } catch (error) {
      start.disabled = false;
      const retry = error.code === "STALE_PLAN" ? el("button", { type: "button", class: "ghost", text: "Rescan and try again", on: { click: () => start.click() } }) : null;
      showError(slot, error, retry);
    }
  });
  const L = window.DevGuru.lantern;
  L.tools(start);
  const frame = L.stage({ id: "runs-stage", compact: true, legend: [["succeeded", "teal"], ["failed", "rose"], ["still going", "saffron"]] });
  main.append(frame.el, slot);
  try {
    const history = await api(scoped("/api/v1/runs"));
    if (!history.runs.length) {
      frame.fill(L.waiting("No runs yet. Build the code graph to see the first one here."));
      main.append(el("p", { class: "muted", text: "No runs in this workspace yet." }));
      return;
    }
    const toneOf = (r) => (r.state === "succeeded" ? "teal" : (ACTIVE.has(r.state) ? "saffron" : (r.state === "failed" ? "rose" : "faint")));
    const recent = [...history.runs].slice(0, 7).reverse();
    let picture = null;
    let list = null;
    const show = (id) => {
      const r = history.runs.find((x) => x.run_id === id);
      if (!r) return;
      picture?.select(id);
      list?.select(id);
      L.dock(L.detail({ title: r.kind, where: r.run_id, tags: [statePill(r.state)], note: `Started ${when(r.created_at)}.`, actions: [el("a", { class: "btn", href: `#/runs/${r.run_id}`, text: "Open this run" })] }));
    };
    picture = L.pipeline({ label: "The latest runs, oldest first", onSelect: show, steps: recent.map((r) => ({ id: r.run_id, label: r.kind, sub: r.state, tone: toneOf(r) })) });
    frame.fill(picture.canvas);
    list = L.rail({ search: true, placeholder: "Find a run", onSelect: show, groups: [{ title: "Newest first", items: history.runs.map((r) => ({ id: r.run_id, label: r.kind, sub: when(r.created_at), tone: toneOf(r) })) }] });
    show(history.runs[0].run_id);
    if (history.total > history.runs.length) main.append(el("p", { class: "muted", text: `The latest ${history.runs.length} of ${history.total} runs.` }));
    const body = el("tbody");
    for (const run of history.runs) {
      body.append(el("tr", {},
        el("td", {}, el("a", { href: `#/runs/${run.run_id}`, class: "mono", text: run.run_id })),
        el("td", { text: run.kind }), el("td", {}, statePill(run.state)), el("td", { text: when(run.created_at) })));
    }
    main.append(el("div", { class: "wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ...["Run", "Kind", "State", "Started"].map((h) => el("th", { scope: "col", text: h })))), body)));
  } catch (error) {
    showError(main, error);
  }
}

async function runDetail(runId, loaded) {
  const main = page("Run", "");
  main.append(el("p", { class: "mono", id: "run-id", text: runId }));
  const head = el("div", { class: "row", id: "run-state" });
  const notes = el("div", { id: "run-warnings" });
  const timeline = el("ol", { class: "events", id: "events", "aria-label": "Run events" });
  const files = el("div", { id: "artifacts" });
  const cancel = el("button", { type: "button", class: "ghost", id: "cancel", text: "Cancel run", hidden: true });
  const L = window.DevGuru.lantern;
  const frame = L.stage({ id: "run-stage", compact: true });
  const track = (run) => {
    const finished = !ACTIVE.has(run.state);
    const picture = L.pipeline({ label: "Where this run has got to", steps: [
      { id: "queued", label: "Queued", tone: "teal" },
      { id: "running", label: "Running", tone: run.state === "queued" ? "faint" : (finished ? "teal" : "saffron"), waiting: run.state === "queued" },
      { id: "done", label: finished ? run.state : "Done", sub: finished ? (run.complete ? "Evidence complete" : "") : "not yet", tone: !finished ? "faint" : (run.state === "succeeded" ? "teal" : (run.state === "failed" ? "rose" : "saffron")), waiting: !finished },
    ] });
    frame.fill(picture.canvas);
  };
  main.append(frame.el, head, el("div", { class: "row" }, cancel), notes, el("h2", { text: "Events" }), timeline);
  L.dock(el("div", { class: "detail" }, el("h2", { text: "Artifacts" }), files));
  L.tools(el("a", { class: "chip", href: "#/runs", text: "‹ All runs" }));
  api(scoped("/api/v1/runs")).then((all) => {
    if (stopped) return;
    const list = L.rail({ groups: [{ title: "Newest first", items: all.runs.map((r) => ({ id: r.run_id, label: r.kind, sub: when(r.created_at), href: `#/runs/${r.run_id}`, tone: r.state === "succeeded" ? "teal" : (ACTIVE.has(r.state) ? "saffron" : (r.state === "failed" ? "rose" : "faint")) })) }] });
    list.select(runId);
  }).catch(() => { /* the list only helps you move around */ });

  let stopped = false;
  let shownState = null;
  state.stop = () => { stopped = true; };
  let after = 0;
  let wait = POLL_MS;
  let lastEvent = null;
  // Ananke records a run's final state just before its final event, so a read can land between the two.
  let finalChecks = 3;

  cancel.addEventListener("click", async () => {
    cancel.disabled = true;
    try {
      await api(`/api/v1/runs/${runId}/cancel`, {});
    } catch (error) {
      cancel.disabled = false;
      banner(`${error.code}: ${error.message}`, true);
    }
  });

  const addEvent = (event) => {
    const text = event.payload && event.payload.step ? `${event.type}: ${event.payload.step}` : event.type;
    timeline.append(el("li", {}, el("span", { text }), " ", el("span", { class: "muted", text: when(event.at) })));
  };

  async function refresh() {
    const run = await api(scoped(`/api/v1/runs/${runId}`));
    if (shownState !== run.state) { shownState = run.state; track(run); }
    head.replaceChildren(statePill(run.state), el("span", { text: run.kind }),
      run.complete ? el("span", { class: "muted", text: "Evidence complete" }) : null);
    cancel.hidden = !ACTIVE.has(run.state);
    notes.replaceChildren(...warnings(run));
    const seen = await api(scoped(`/api/v1/runs/${runId}/events`, { after }));
    if (seen.gap) timeline.append(el("li", { class: "muted", text: `Events ${seen.gap.from} to ${seen.gap.to} are no longer kept.` }));
    for (const event of seen.events) { addEvent(event); after = event.seq; lastEvent = event.type; }
    const listed = await api(scoped(`/api/v1/runs/${runId}/artifacts`));
    files.replaceChildren(listed.artifacts.length
      ? el("ul", {}, ...listed.artifacts.map((a) => el("li", {},
        window.DEV_GURU_STATIC ? el("span", { text: a.name }) : el("a", { href: scoped(`/api/v1/runs/${runId}/artifacts/${encodeURIComponent(a.name)}`), download: a.name, text: a.name }),
        el("span", { class: "muted", text: ` ${a.size} bytes · ${a.producer}` }))))
      : el("p", { class: "muted", text: ACTIVE.has(run.state) ? "None yet." : "This run produced none." }));
    return run;
  }

  while (!stopped) {
    try {
      const run = await refresh();
      if (stopped) return;
      banner("");
      wait = POLL_MS;
      if (!ACTIVE.has(run.state) && (lastEvent === `run.${run.state}` || --finalChecks <= 0)) return;
    } catch (error) {
      if (stopped) return;
      if (!error.retryable) {
        showError(main, error);
        return;
      }
      banner(`Connection lost. The run carries on in Ananke. Trying again in ${Math.round(wait / 1000)}s.`);
      wait = Math.min(wait * 2, MAX_BACKOFF_MS);
    } finally {
      loaded();
    }
    await new Promise((resolve) => setTimeout(resolve, wait));
  }
}

// ------------------------------------------------------------------ code
async function code(query) {
  const main = page("Code", "A view of Ananke's code graph, kept within a node budget. Nothing here changes your files.");
  const collapse = query.get("collapse") || "directory";
  const path = query.get("path") || "";
  const go = (changes) => {
    const next = new URLSearchParams({ collapse, ...(path ? { path } : {}), ...changes });
    if (!next.get("path")) next.delete("path");
    location.hash = `#/code?${next}`;
  };
  const select = el("select", { id: "collapse", on: { change: (e) => go({ collapse: e.target.value }) } },
    ...[["directory", "Folders"], ["file", "Files"], ["none", "Every symbol"]].map(([value, text]) =>
      el("option", { value, text, selected: value === collapse })));
  window.DevGuru.lantern.tools(el("label", { class: "field" }, "Group by", select),
    path ? el("button", { type: "button", class: "chip", text: `Showing ${path}: show everything`, on: { click: () => go({ path: "" }) } }) : null);
  try {
    const view = await api(scoped("/api/v1/code", { collapse, budget: 200, ...(path ? { path } : {}) }));
    const a = view.edge_accounting;
    const L = window.DevGuru.lantern;
    const frame = L.stage({ id: "code-stage", legend: [["imports", "violet"], ["calls", "teal"]], hint: view.nodes.length > 60 ? `The 60 most connected of ${view.nodes.length} shown here. The table below has them all.` : "Hover to light up what connects." });
    const degree = new Map();
    for (const e of view.edges) for (const id of [e.source, e.target]) degree.set(id, (degree.get(id) || 0) + 1);
    const drawn = [...view.nodes].sort((x, y) => (degree.get(y.node_id) || 0) - (degree.get(x.node_id) || 0)).slice(0, 60);
    const drawnIds = new Set(drawn.map((n) => n.node_id));
    let graph = null;
    let list = null;
    const openNode = (node) => go(node.kind === "directory" ? { collapse: "file", path: node.path === "." ? "" : `${node.path}/` } : { collapse: "none", path: node.path });
    const show = (id) => {
      const node = view.nodes.find((n) => n.node_id === id);
      if (!node) return;
      const coming = view.edges.filter((e) => e.target === id);
      const going = view.edges.filter((e) => e.source === id);
      graph?.highlight(new Set([id, ...coming.map((e) => e.source), ...going.map((e) => e.target)]), id);
      list?.select(id);
      const openable = (node.kind === "directory" || node.kind === "file") && collapse !== "none";
      L.dock(L.detail({ title: node.name || node.path || ".", where: node.path || node.source_location, tags: [node.kind], facts: [[node.members, "Items"], [coming.length, "Used by"], [going.length, "Uses"]],
        actions: [openable ? el("button", { type: "button", class: "btn", text: `Open ${node.name || node.path}`, on: { click: () => openNode(node) } }) : null] },
      ...L.linkList("Used by", coming.slice(0, 30).map((e) => e.source)), ...L.linkList("Uses", going.slice(0, 30).map((e) => e.target))));
    };
    const edgeKind = (e) => (e.kinds ? Object.keys(e.kinds)[0] : e.kind);
    if (drawn.length && window.DevGuru.drawGraph) {
      graph = window.DevGuru.drawGraph({ label: "The code graph", onSelect: (node) => show(node.id),
        nodes: drawn.map((n) => ({ id: n.node_id, kind: n.kind, label: n.name || n.path || ".", sub: n.members !== undefined ? `${n.members} items` : (n.source_location || n.kind) })),
        edges: view.edges.filter((e) => drawnIds.has(e.source) && drawnIds.has(e.target)).map((e) => ({ source: e.source, target: e.target, kind: edgeKind(e), kindLabel: edgeKind(e) })) });
      frame.fill(el("div", { class: "canvas-wrap" }, graph.canvas), window.DevGuru.panZoom(graph.canvas));
    } else frame.fill(L.waiting("Nothing to draw here."));
    main.append(frame.el);
    list = L.rail({ search: true, placeholder: "Find in this view", onSelect: show,
      insights: path ? [{ title: "Showing", text: `${path}: show everything`, onClick: () => go({ path: "" }) }] : [],
      groups: [...new Set(view.nodes.map((n) => n.kind))].map((kind) => ({ title: kind, items: view.nodes.filter((n) => n.kind === kind).map((n) => ({ id: n.node_id, label: n.name || n.path || ".", sub: n.path && n.path !== n.name ? n.path : undefined, count: degree.get(n.node_id) || undefined })) })) });
    L.walk({ into: frame.el, go: show, steps: drawn.slice(0, 8).map((n) => ({ id: n.node_id, text: `${n.name || n.path}, a ${n.kind}, has ${degree.get(n.node_id) || 0} links here.` })) });
    if (drawn.length) show(drawn[0].node_id);
    main.append(el("p", { class: "muted", id: "accounting",
      text: `${view.nodes.length} of ${view.total_nodes} shown. Links: ${a.shown} shown, ${a.inside_a_group} inside a group, ${a.to_nodes_not_shown} to items not shown, ${a.external_imports} third-party imports.` }));
    if (view.truncated) main.append(el("p", { class: "muted", text: "Over budget: the most connected items are shown. Narrow it down by opening a folder." }));
    const body = el("tbody");
    for (const node of view.nodes) {
      const openable = node.kind === "directory" || node.kind === "file";
      const name = openable && collapse !== "none"
        ? el("button", { type: "button", class: "ghost", text: node.path || node.name, on: { click: () => go(node.kind === "directory" ? { collapse: "file", path: node.path === "." ? "" : `${node.path}/` } : { collapse: "none", path: node.path }) } })
        : el("span", { text: node.name });
      body.append(el("tr", {}, el("td", {}, name), el("td", { text: node.kind }),
        el("td", { class: "mono", text: node.members !== undefined ? `${node.members} items` : (node.source_location || "") })));
    }
    main.append(el("div", { class: "wrap" }, el("table", { id: "code-table" },
      el("thead", {}, el("tr", {}, ...["Name", "Kind", "Where"].map((h) => el("th", { scope: "col", text: h })))), body)));
    main.append(el("h2", { text: "Links" }));
    const links = el("tbody");
    for (const edge of view.edges.slice(0, 200)) {
      const kinds = edge.kinds ? Object.entries(edge.kinds).map(([k, n]) => `${k} ${n}`).join(", ") : edge.kind;
      const inferred = edge.origins ? edge.origins.inferred > 0 : edge.origin === "inferred";
      links.append(el("tr", {}, el("td", { class: "mono", text: edge.source }), el("td", { class: "mono", text: edge.target }),
        el("td", { text: inferred ? `${kinds} (includes inferred)` : kinds })));
    }
    main.append(view.edges.length ? el("div", { class: "wrap" }, el("table", { id: "link-table" },
      el("thead", {}, el("tr", {}, ...["From", "To", "How"].map((h) => el("th", { scope: "col", text: h })))), links))
      : el("p", { class: "muted", text: "No links between these items." }));
    if (view.edges.length > 200) main.append(el("p", { class: "muted", text: `The first 200 of ${view.edges.length} links.` }));
    main.append(el("p", { class: "muted mono", text: `Source ${view.source_snapshot}` }));
  } catch (error) {
    const build = error.code === "GRAPH_MISSING"
      ? el("button", { type: "button", id: "build-graph", text: "Build the code graph", on: { click: () => startGraphRun((run) => { location.hash = `#/runs/${run.run_id}`; }).catch((e) => banner(`${e.code}: ${e.message}`, true)) } })
      : null;
    showError(main, error, build);
  }
}

// ------------------------------------------------------------------ capabilities
async function sources(query) {
  const main = page("Capabilities", "What your configured sources offer. Being listed doesn't mean a capability is trusted or will run.");
  const words = query.get("q") || "";
  const input = el("input", { type: "search", id: "search", value: words, "aria-label": "Search capabilities", placeholder: "Search" });
  const form = el("form", { class: "row", on: { submit: (e) => { e.preventDefault(); location.hash = `#/sources?${new URLSearchParams({ q: input.value })}`; } } },
    input, el("button", { type: "submit", class: "ghost", text: "Search" }));
  main.append(form);
  try {
    const found = await api(scoped("/api/v1/sources", { q: words }));
    const L = window.DevGuru.lantern;
    const frame = L.stage({ id: "sources-stage", hint: "What your sources offer. Being listed doesn't mean it's trusted." });
    main.append(frame.el);
    if (!found.capabilities.length) {
      const said = words ? "Nothing matches." : "No capabilities from this workspace's sources.";
      frame.fill(L.waiting(said));
      L.rail({ groups: [], note: said });
      L.dock(L.detail({ title: "Adding a source", note: "Point Ananke at a registry of skills or tools, and they're listed here.", actions: [] }, el("pre", { class: "source" }, el("code", { text: "ananke registry init\nananke registry learn PATH --namespace NAME" }))));
      return;
    }
    const kinds = [...new Set(found.capabilities.map((c) => c.kind))];
    const toneFor = (kind) => L.toneOf(kinds.indexOf(kind));
    let picture = null;
    let list = null;
    const show = (id) => {
      const c = found.capabilities.find((x) => x.identity === id);
      if (!c) return;
      picture.select(id);
      list.select(id);
      L.dock(L.detail({ title: c.identity, tags: [c.kind, c.version, c.licence], note: c.summary }));
    };
    const shown = found.capabilities.slice(0, 44);
    picture = L.radial({ center: "Your sources", sub: `${found.capabilities.length} capabilities`, label: "Capabilities by kind", onSelect: show,
      items: shown.map((c) => ({ id: c.identity, label: String(c.identity).split("/").pop(), sub: c.kind, tone: toneFor(c.kind) })), more: found.capabilities.length > shown.length ? `and ${found.capabilities.length - shown.length} more below` : "" });
    frame.fill(picture.canvas);
    list = L.rail({ search: true, placeholder: "Filter this list", onSelect: show, groups: kinds.map((kind) => ({ title: kind, items: found.capabilities.filter((c) => c.kind === kind).map((c) => ({ id: c.identity, label: String(c.identity).split("/").pop(), sub: c.version, tone: toneFor(kind) })) })) });
    L.walk({ into: frame.el, go: show, steps: shown.slice(0, 10).map((c) => ({ id: c.identity, text: `${c.identity}: ${c.summary || c.kind}` })) });
    show(shown[0].identity);
    const body = el("tbody");
    for (const c of found.capabilities) {
      body.append(el("tr", {}, el("td", { class: "mono", text: c.identity }), el("td", { text: c.kind }),
        el("td", { text: c.version }), el("td", { text: c.licence }), el("td", { text: c.summary })));
    }
    main.append(el("div", { class: "wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ...["Identity", "Kind", "Version", "Licence", "About"].map((h) => el("th", { scope: "col", text: h })))), body)));
  } catch (error) {
    showError(main, error);
  }
}

// ------------------------------------------------------------------ not here yet: say so, and say what works today
// ------------------------------------------------------------------ repository analysis, shared by map.js and insights.js
const views = {};
const analysisKeys = {};

async function startAnalysis(checkVulnerabilities) {
  const name = checkVulnerabilities ? "cves" : "plain";
  // Trying again after a lost connection repeats the same request, in case the first one did arrive.
  analysisKeys[name] = analysisKeys[name] || crypto.randomUUID();
  const run = await api("/api/v1/runs", {
    kind: "repo.analyze",
    parameters: checkVulnerabilities ? { check_vulnerabilities: true } : {},
    idempotency_key: analysisKeys[name],
  });
  delete analysisKeys[name];
  location.hash = `#/runs/${run.run_id}`;
}

// Calls render(report) with the newest analysis, or offers to run one. Asking for it is what starts it: nothing runs by itself.
async function withAnalysis(main, render) {
  try {
    const report = await api(scoped("/api/v1/intel"));
    render(report);
  } catch (error) {
    if (error.code !== "INTEL_MISSING") { showError(main, error); return; }
    const button = el("button", { type: "button", id: "analyze", text: "Analyse this repository" });
    button.addEventListener("click", () => startAnalysis(false).catch((e) => showError(main, e)));
    window.DevGuru.lantern.nothing(main, "Not analysed yet.", "This repository hasn't been analysed yet. Analysis reads its files and runs nothing.");
    main.append(el("p", { text: "This repository hasn't been analysed yet. Analysis reads its files and runs nothing." }), button);
  }
}

window.DevGuru = { el, api, scoped, page, banner, showError, when, statePill, views, withAnalysis, startAnalysis };

// ------------------------------------------------------------------ shell
async function route(moveFocus = true) {
  if (state.stop) state.stop();
  state.stop = null;
  banner("");
  const [path, search] = location.hash.replace(/^#\/?/, "").split("?");
  const query = new URLSearchParams(search || "");
  const [section, id] = path.split("/");
  for (const link of document.querySelectorAll("nav a")) {
    if (link.dataset.route === section) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  const main = document.querySelector("#main");
  const shown = ++state.shown;
  // busy until this page has its data; a later page takes over the mark
  const loaded = () => { if (shown === state.shown) main.removeAttribute("aria-busy"); };
  main.setAttribute("aria-busy", "true");
  if (section === "runs" && id) {
    if (!RUN_ID.test(id)) { page("Not found", "That isn't a run's address."); loaded(); if (moveFocus) main.focus(); return; }
    const detail = runDetail(id, loaded);
    if (moveFocus) main.focus();
    await detail;
    return;
  }
  if (Object.hasOwn(views, section)) {
    await views[section](main, query, id);
    loaded();
    if (moveFocus && shown === state.shown) main.focus();
    return;
  }
  if (section === "") await overview();
  else if (section === "runs") await runs();
  else if (section === "code") await code(query);
  else if (section === "sources") await sources(query);
  else page("Not found", "There's no such page.");
  loaded();
  if (moveFocus && shown === state.shown) main.focus(); // not on first load: the keyboard starts at the top, with the skip link
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("dev-guru-theme", theme); } catch { /* the choice just won't be remembered */ }
}

async function init() {
  let saved = null;
  try { saved = localStorage.getItem("dev-guru-theme"); } catch { /* not available here */ }
  setTheme(saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  if (window.DEV_GURU_STATIC) document.documentElement.classList.add("in-report");
  // inside the explorer, its tabs replace this page's own bar, under dev serve as in a report
  try {
    if (window.parent !== window && window.parent.document.querySelector("#serveFrame")) document.documentElement.classList.add("in-report");
    if (window.parent !== window && window.parent.document.documentElement.classList.contains("embed")) document.documentElement.classList.add("embed");
  } catch { /* not ours to read */ }
  document.querySelector("#theme").addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
  // The address holds the page, so the skip link moves focus instead of changing it.
  document.querySelector(".skip").addEventListener("click", (event) => { event.preventDefault(); document.querySelector("#main").focus(); });
  try {
    const session = await api("/api/v1/session");
    state.csrf = session.csrf_token;
    state.csrfHeader = session.csrf_header;
    state.workspaces = (await api("/api/v1/workspaces")).workspaces;
    const health = await api("/api/v1/health");
    const pill = document.querySelector("#harness");
    pill.textContent = health.ok ? `Ananke ${health.harness.ananke_version}` : "Ananke isn't compatible";
    pill.classList.add(health.ok ? "ok" : "bad");
  } catch (error) {
    showError(page("Dev Guru", ""), error);
    return;
  }
  const picker = document.querySelector("#workspace");
  for (const w of state.workspaces) picker.append(el("option", { value: w.id, title: w.path, text: w.name }));
  let remembered = null;
  try { remembered = sessionStorage.getItem("dev-guru-workspace"); } catch { /* not available here */ }
  const asked = new URLSearchParams(location.search).get("workspace"); // the explorer says which
  if (state.workspaces.some((w) => w.id === asked)) remembered = asked;
  state.workspace = state.workspaces.some((w) => w.id === remembered) ? remembered : state.workspaces[0].id;
  picker.value = state.workspace;
  picker.addEventListener("change", () => {
    state.workspace = picker.value;
    try { sessionStorage.setItem("dev-guru-workspace", state.workspace); } catch { /* not available here */ }
    if (location.hash.startsWith("#/runs/")) location.hash = "#/runs";
    else route();
  });
  addEventListener("hashchange", () => route());
  route(false);
}

// Every script has to be in before the first page draws.
addEventListener("load", init, { once: true });
