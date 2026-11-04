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
  const section = el("section", {}, el("h1", { text: title }));
  if (lede) section.append(el("p", { class: "lede", text: lede }));
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
    main.append(el("h2", { text: "What the harness can run" }));
    main.append(el("div", { class: "row" }, ...caps.run_kinds.map((k) => el("code", { class: "pill", text: k }))));
    main.append(el("div", { class: "row" }, el("a", { href: "#/runs", text: "Go to runs" }), el("a", { href: "#/code", text: "Explore the code" })));
  } catch (error) {
    showError(main, error);
  }
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
  main.append(el("div", { class: "row" }, start), slot);
  try {
    const history = await api(scoped("/api/v1/runs"));
    if (!history.runs.length) {
      main.append(el("p", { class: "muted", text: "No runs in this workspace yet." }));
      return;
    }
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
  main.append(head, el("div", { class: "row" }, cancel), notes, el("h2", { text: "Events" }), timeline, el("h2", { text: "Artifacts" }), files,
    el("p", {}, el("a", { href: "#/runs", text: "All runs" })));

  let stopped = false;
  state.stop = () => { stopped = true; };
  let after = 0;
  let wait = POLL_MS;

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
    head.replaceChildren(statePill(run.state), el("span", { text: run.kind }),
      run.complete ? el("span", { class: "muted", text: "Evidence complete" }) : null);
    cancel.hidden = !ACTIVE.has(run.state);
    notes.replaceChildren(...warnings(run));
    const seen = await api(scoped(`/api/v1/runs/${runId}/events`, { after }));
    if (seen.gap) timeline.append(el("li", { class: "muted", text: `Events ${seen.gap.from} to ${seen.gap.to} are no longer kept.` }));
    for (const event of seen.events) { addEvent(event); after = event.seq; }
    const listed = await api(scoped(`/api/v1/runs/${runId}/artifacts`));
    files.replaceChildren(listed.artifacts.length
      ? el("ul", {}, ...listed.artifacts.map((a) => el("li", {},
        el("a", { href: scoped(`/api/v1/runs/${runId}/artifacts/${encodeURIComponent(a.name)}`), download: a.name, text: a.name }),
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
      if (!ACTIVE.has(run.state)) return;
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
  main.append(el("div", { class: "row" }, el("label", { class: "field" }, "Group by", select),
    path ? el("button", { type: "button", class: "ghost", text: `Showing ${path}: show everything`, on: { click: () => go({ path: "" }) } }) : null));
  try {
    const view = await api(scoped("/api/v1/code", { collapse, budget: 200, ...(path ? { path } : {}) }));
    const a = view.edge_accounting;
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
    if (!found.capabilities.length) {
      main.append(el("p", { class: "muted", text: words ? "Nothing matches." : "No capabilities from this workspace's sources." }));
      return;
    }
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
const UNSUPPORTED = {
  workflows: ["Workflows", "Assembling workflows in the browser isn't in this version.", ["ananke app workflow-preview DRAFT", "ananke app workflow-run DRAFT --backend B --plan-hash H --key K"]],
  quality: ["Quality", "Quality views aren't in this version.", ["dev explore ."]],
  docs: ["Documentation", "The documentation studio isn't in this version.", ["dev present SLIDES.md", "dev diagram DOCUMENT.md"]],
  learning: ["Learning review", "Reviewing learning candidates in the browser isn't in this version.", ["dev learning review NAME"]],
};

function unsupported([title, text, commands]) {
  const main = page(title, text);
  main.append(el("h2", { text: "What works today" }), el("ul", {}, ...commands.map((c) => el("li", {}, el("code", { text: c })))));
}

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
  if (section === "") await overview();
  else if (section === "runs") await runs();
  else if (section === "code") await code(query);
  else if (section === "sources") await sources(query);
  else if (Object.hasOwn(UNSUPPORTED, section)) unsupported(UNSUPPORTED[section]);
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

init();
