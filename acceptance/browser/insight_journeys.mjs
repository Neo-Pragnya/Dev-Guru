#!/usr/bin/env node
// Real-Chrome journeys for the repository views, against a real `dev serve` and the real Ananke harness.
//   node acceptance/browser/insight_journeys.mjs [--shots DIR] [--repo PATH]
// `dev` must be on PATH. Each run builds its own temporary Git workspace, so nothing depends on what's on this computer:
// few enough files that all of them fit the Code page's node budget, enough symbols that a graph build takes seconds.
// Prints one line per journey and exits 1 on any failure.
import { execFileSync, spawn } from "node:child_process";
import { cpSync, renameSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const HOSTILE_NAME = "<img src=x onerror=alert(1)>.py";
const args = process.argv.slice(2);
const shots = args.includes("--shots") ? resolve(args[args.indexOf("--shots") + 1]) : null;
if (args.length && !shots && !args.includes("--network") && !args.includes("--repo")) { console.error("usage: insight_journeys.mjs [--shots DIR] [--repo PATH] [--network]"); process.exit(2); }
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"].find(existsSync);
if (!CHROME) { console.error("Chrome not found; set CHROME"); process.exit(2); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function buildWorkspace(root) {
  const from = args.includes("--repo") ? resolve(args[args.indexOf("--repo") + 1]) : join(import.meta.dirname, "..", "fixtures", "shop");
  cpSync(from, root, { recursive: true, filter: (p) => !/(^|\/)(node_modules|\.git|\.venv|venv|\.ananke|dist)(\/|$)/.test(p.slice(from.length)) });
  if (!args.includes("--repo")) {
    // a declared architecture that differs from the code, so the difference can be checked
    mkdirSync(join(root, ".ananke", "architecture"), { recursive: true });
    writeFileSync(join(root, ".ananke", "architecture", "system.calm.json"), JSON.stringify({ components: [{ id: "backend", name: "backend" }, { id: "payments", name: "payments" }], relationships: [] }));
  }
  // old pins on purpose, for known CVE answers, kept out of the repository as manifests so no scanner mistakes them for ours
  if (!args.includes("--repo")) for (const f of ["backend/requirements.txt", "frontend/package.json"]) renameSync(join(root, `${f}.pins`), join(root, f));
  const git = (...a) => execFileSync("git", ["-C", root, ...a], { stdio: "ignore" });
  if (!args.includes("--repo")) {
    // reports a scanner and a test run left behind
    writeFileSync(join(root, "scan.sarif"), JSON.stringify({ runs: [{ tool: { driver: { name: "CodeQL", rules: [{ id: "py/sql-injection", properties: { "security-severity": "9.8" }, help: { text: "Use a parameter." } }, { id: "py/unused", defaultConfiguration: { level: "note" } }] } }, results: [{ ruleId: "py/unused", message: { text: "Unused import" }, locations: [{ physicalLocation: { artifactLocation: { uri: "backend/app/main.py" }, region: { startLine: 1 } } }] }, { ruleId: "py/sql-injection", message: { text: "A query built from user input" }, locations: [{ physicalLocation: { artifactLocation: { uri: "backend/app/services/orders.py" }, region: { startLine: 6 } } }] }] }] }));
    writeFileSync(join(root, "junit.xml"), '<testsuite><testcase classname="tests.orders" name="test_create"/><testcase classname="tests.orders" name="test_refund"><failure message="refund was 0"/></testcase></testsuite>');
    // a capability Ananke really knows, so a workflow can compile
    const skill = join(root, "skills", "demo-step");
    mkdirSync(skill, { recursive: true });
    writeFileSync(join(skill, "SKILL.md"), "---\nname: demo-step\ndescription: A step for testing workflows.\nlicense: MIT\nversion: 1.0.0\n---\n\n# Demo\n");
    execFileSync("ananke", ["registry", "init"], { cwd: root, stdio: "ignore" });
    execFileSync("ananke", ["registry", "learn", "skills/demo-step", "--namespace", "demo"], { cwd: root, stdio: "ignore" });
  }
  git("init", "-q"); git("add", "-A"); git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init");
}

const scratch = realpathSync(mkdtempSync(join(tmpdir(), "dg-web-")));
const workspace = join(scratch, "shop");
mkdirSync(workspace);
mkdirSync(join(scratch, "home"));
const profile = join(scratch, "chrome");
mkdirSync(profile);
buildWorkspace(workspace);

const server = spawn("dev", ["serve", workspace, "--no-open"], { stdio: ["ignore", "pipe", "inherit"], env: { ...process.env, HOME: join(scratch, "home") } });
let chrome = null;
const quit = (code) => {
  if (chrome) chrome.kill("SIGKILL");
  server.kill("SIGKILL");
  setTimeout(() => { // Chrome writes to its profile as it goes down
    try { rmSync(scratch, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* the OS clears temp */ }
    process.exit(code);
  }, 300);
};
const login = await new Promise((done, fail) => {
  let out = "";
  server.stdout.on("data", (d) => { out += d; const m = out.match(/http:\/\/127\.0\.0\.1:\d+\/login\?token=\S+/); if (m) done(m[0]); });
  server.on("error", (e) => fail(new Error(`can't start dev (is it on PATH?): ${e.message}`)));
  server.on("exit", (c) => fail(new Error(`dev serve exited ${c}`)));
}).catch((e) => { console.log(`✗ ${e.message}`); quit(1); return new Promise(() => {}); });
const origin = new URL(login).origin;
// Port 0: Chrome picks a free port and writes it down, so parallel runs can't collide.
chrome = spawn(CHROME, ["--headless=new", "--window-size=1440,900", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check", "--use-mock-keychain", "--password-store=basic", "--disable-gpu", "about:blank"], { stdio: "ignore" });
setTimeout(() => { console.log("✗ journeys timed out"); quit(1); }, Number(process.env.JOURNEY_TIMEOUT_MS || 240000));
let target;
for (let i = 0; i < 600 && !target; i++) { // a busy machine can take a while to start Chrome
  await sleep(150);
  try {
    const port = readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0];
    target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page");
  } catch { /* not up yet */ }
}
if (!target) { console.log("✗ Chrome exposed no DevTools target"); quit(1); await sleep(1000); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map(); let problems = []; const requests = [];
let expectOffline = false;
let expectedStatus = /status of (401|404|503)/; // a refused request the page handles isn't a fault
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") problems.push("exception: " + (msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text));
  if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") {
    const { text, url } = msg.params.entry;
    if (!expectOffline && !expectedStatus.test(text)) problems.push(`log: ${text} ${url || ""}`);
  }
  if (msg.method === "Page.javascriptDialogOpening") problems.push("dialog opened: " + msg.params.message);
  if (msg.method === "Network.requestWillBeSent") requests.push(msg.params.request.url);
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || "evaluate failed"); return r.result?.result?.value; };
await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable"); await send("Log.enable");
await send("Emulation.setFocusEmulationEnabled", { enabled: true });
const viewport = (width, height, mobile = false) => send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
const until = async (expr, what, ms = 60000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try { if (await evaluate(expr)) return; } catch { /* the page is between documents */ }
    await sleep(100);
  }
  throw new Error(`timed out waiting for ${what}`);
};
// The app marks #main aria-busy until a page has its data, so nothing here waits a guessed number of seconds.
const PAGE_READY = `document.readyState === "complete" && !!document.querySelector("#main h1") && !document.querySelector("#main").hasAttribute("aria-busy")`;
const ready = () => until(PAGE_READY, "the page to load", 90000);
const goto = async (url) => { await send("Page.navigate", { url }); await sleep(100); await ready(); };
const reload = async () => { await send("Page.reload"); await sleep(100); await ready(); };
const route = async (hash) => { await evaluate(`location.hash = ${JSON.stringify(hash)}`); await ready(); };
const key = async (k, code = k, vk = 0) => { for (const type of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key: k, code, windowsVirtualKeyCode: vk }); await sleep(80); };
const shot = async (name) => { if (!shots) return; mkdirSync(shots, { recursive: true }); const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true }); writeFileSync(join(shots, `${name}.png`), Buffer.from(r.result.data, "base64")); };
const text = (selector) => evaluate(`document.querySelector(${JSON.stringify(selector)})?.textContent ?? ""`);
const results = [];
async function journey(name, fn) {
  problems = [];
  try { const detail = (await fn()) || ""; if (problems.length) throw new Error(problems.slice(0, 3).join(" | ")); results.push(true); console.log(`✓ ${name}${detail ? `: ${detail}` : ""}`); }
  catch (e) { results.push(false); console.log(`✗ ${name}: ${e.message || e}`); await shot(`failed-${results.length}`).catch(() => {}); }
}
const expect = (c, m) => { if (!c) throw new Error(m); };
const runState = `document.querySelector("#run-state .pill")?.textContent`;
const startRuns = (n) => evaluate(`(async () => {
  const s = await (await fetch("/api/v1/session")).json();
  const w = (await (await fetch("/api/v1/workspaces")).json()).workspaces[0].id;
  const ids = [];
  for (let i = 0; i < ${n}; i++) {
    const r = await fetch("/api/v1/runs", { method: "POST", headers: { "Content-Type": "application/json", [s.csrf_header]: s.csrf_token }, body: JSON.stringify({ workspace: w, kind: "graph.build", parameters: {}, idempotency_key: crypto.randomUUID() }) });
    ids.push((await r.json()).run_id);
  }
  return ids;
})()`);
const expectGolden = !args.includes("--repo");
const analyse = async () => {
  const ids = await evaluate(`(async () => {
    const s = await (await fetch("/api/v1/session")).json();
    const w = (await (await fetch("/api/v1/workspaces")).json()).workspaces[0].id;
    const ids = [];
    for (const kind of ["graph.build", "repo.analyze"]) {
      const r = await fetch("/api/v1/runs", { method: "POST", headers: { "Content-Type": "application/json", [s.csrf_header]: s.csrf_token }, body: JSON.stringify({ workspace: w, kind, parameters: {}, idempotency_key: kind }) });
      ids.push((await r.json()).run_id);
    }
    return ids;
  })()`);
  for (const runId of ids) {
    await route(`#/runs/${runId}`);
    await until(`["succeeded", "failed"].includes(${runState})`, `the run`, 180000);
    expect((await evaluate(runState)) === "succeeded", `run ${runId} ended ${await evaluate(runState)}`);
  }
};

await goto(login);
await journey("before any analysis, a page offers one and shows no invented data", async () => {
  await route("#/data");
  expect(await evaluate(`!!document.querySelector("#analyze")`), "no offer to analyse");
  expect(!(await evaluate(`!!document.querySelector(".erd")`)), "a diagram with no data");
});
await journey("analysing the repository runs on the real harness", analyse);

await journey("the code map connects folders, and says how many links it found", async () => {
  await route("#/map");
  const r = await evaluate(`({ nodes: document.querySelectorAll(".graph .node").length, edges: document.querySelectorAll(".graph .edge").length, summary: document.querySelector("#map-summary").textContent })`);
  await shot("map");
  expect(r.edges > 0, `no links drawn: ${r.summary}`);
  await sleep(300); // the map sizes itself on its first frame
  const wholeMapShown = await evaluate(`(() => { const f = document.querySelector(".graph").parentElement; return f.scrollWidth <= f.clientWidth + 2; })()`);
  expect(wholeMapShown, "the map doesn't fit its frame at a desktop width");
  const labelHeight = await evaluate(`document.querySelector(".graph .node-label").getBoundingClientRect().height`);
  expect(labelHeight >= 10, `labels too small to read: ${labelHeight}px tall`);
  if (expectGolden) {
    const edgeTitles = await evaluate(`[...document.querySelectorAll(".graph .edge title")].map((t) => t.textContent).join(" | ")`);
    expect(/http/.test(edgeTitles), `the frontend isn't joined to the backend: ${edgeTitles.slice(0, 200)}`);
    expect(/writes[^|]*table:orders/.test(edgeTitles), `no table links: ${edgeTitles.slice(0, 200)}`);
  }
  return `${r.nodes} nodes, ${r.edges} links`;
});
if (expectGolden) await journey("a node works from the keyboard, and shows its impact and a path to a table", async () => {
  await route("#/map");
  await sleep(300);
  await evaluate(`[...document.querySelectorAll(".graph .node")].find((n) => n.querySelector(".node-label").textContent.endsWith("services")).focus()`);
  await key("Enter", "Enter", 13);
  await until(`!!document.querySelector("#map-impact-count")`, "the details to open");
  const count = await text("#map-impact-count");
  expect(/could affect \d+ other/.test(count), count);
  const picked = await evaluate(`(() => { const p = document.querySelector("#map-path-to"); const o = [...p.options].find((x) => x.textContent === "orders"); p.value = o.value; p.dispatchEvent(new Event("change", { bubbles: true })); return o.textContent; })()`);
  const steps = await evaluate(`[...document.querySelectorAll("#map-path li")].map((l) => l.textContent)`);
  expect(steps.length >= 2 && steps[steps.length - 1] === picked, `no path to ${picked}: ${steps.join(" > ")}`);
});
if (expectGolden) await journey("opening a folder shows its files, joined across folders by real imports", async () => {
  await route("#/map?path=frontend");
  const labels = await evaluate(`[...document.querySelectorAll(".graph .node .node-label")].map((n) => n.textContent)`);
  await shot("map-frontend");
  expect(labels.includes("src/api.ts") && labels.includes("lib/http.ts"), labels.join(", "));
  expect(labels.includes("routers/orders.py"), `the backend file it calls isn't shown: ${labels.join(", ")}`);
  const body = await evaluate(`[...document.querySelectorAll("#map-text td")].map((c) => c.textContent).join(" ")`);
  expect(body.includes("frontend/src/api.ts") && body.includes("frontend/src/lib/http.ts"), "the import isn't listed");
  await route("#/map?path=backend/app/services");
  expect((await evaluate(`document.querySelectorAll(".graph .node").length`)) >= 1, "nothing connected in services");
});
if (expectGolden) await journey("selecting a function shows what uses it, with its source", async () => {
  await route("#/map?path=backend/app/services/orders.py");
  await evaluate(`[...document.querySelectorAll(".graph .node")].find((n) => n.getAttribute("aria-label").includes("create_order"))?.dispatchEvent(new MouseEvent("click", { bubbles: true }))`);
  await until(`document.querySelector("#inspector .source")`, "the source excerpt");
  const t = await text("#inspector");
  expect(t.includes("create_order") && t.includes("def create_order"), t.slice(0, 200));
});
if (expectGolden) await journey("a flow runs from the frontend call, through the route, to the tables", async () => {
  await route(`#/flows?${new URLSearchParams({ flow: "flow:POST /api/orders" })}`);
  await until(`document.querySelector("#flow-steps li")`, "the flow's steps");
  const steps = await text("#flow-steps");
  await shot("flow");
  for (const wanted of ["createOrder", "create_order", "orders", "order_items"]) expect(steps.includes(wanted), `${wanted} missing: ${steps}`);
  expect((await text("#flow-note")).includes("Reaches a data store"), await text("#flow-note"));
  const before = await text("#flow-detail h2");
  await evaluate(`document.querySelector("#flow-next").click()`);
  await until(`document.querySelector("#flow-detail h2").textContent !== ${JSON.stringify(before)}`, "the next step");
  expect((await text("#unmatched-calls")).includes("GET /api/invoices"), "the broken call isn't shown");
});
if (expectGolden) await journey("the ERD draws the real tables and keys, and a table shows the code that uses it", async () => {
  await route("#/data");
  const r = await evaluate(`({ tables: [...document.querySelectorAll(".table-card .table-name")].map((n) => n.textContent).sort(), lines: document.querySelectorAll(".erd .rel").length })`);
  await shot("erd");
  expect(JSON.stringify(r.tables) === JSON.stringify(["audit_log", "customers", "order_items", "orders"]), r.tables.join(", "));
  expect(r.lines === 3, `${r.lines} relationships`);
  await evaluate(`[...document.querySelectorAll(".table-card")].find((n) => n.getAttribute("aria-label").includes("Table orders,")).dispatchEvent(new MouseEvent("click", { bubbles: true }))`);
  const usage = await text("#table-usage");
  expect(usage.includes("write") && usage.includes("create_order"), usage);
  expect((await text("#table-columns")).includes("customer_id"), "no columns");
  expect((await text("#lineage")).includes("record_audit"), "no lineage");
});
if (expectGolden) await journey("API pathways list the routes, link callers, and show the broken call", async () => {
  await route("#/apis");
  const routes = await text("#routes");
  await shot("apis");
  for (const wanted of ["/api/orders", "/api/customers/{customer_id}", "/api/customers/reports/sales", "/health", "createOrder"]) expect(routes.includes(wanted), `${wanted} missing`);
  expect((await text("#broken-calls")).includes("/api/invoices"), "the broken call isn't shown");
});
const linesThroughCards = () => evaluate(`(() => {
    const cards = [...document.querySelectorAll(".table-card")].map((c) => c.getBoundingClientRect());
    return [...document.querySelectorAll("path.rel")].filter((line) => {
      const length = line.getTotalLength();
      for (let i = 2; i < 19; i++) {
        const p = line.getPointAtLength((length * i) / 20).matrixTransform(line.getScreenCTM());
        if (cards.some((c) => p.x > c.left + 2 && p.x < c.right - 2 && p.y > c.top + 2 && p.y < c.bottom - 2)) return true;
      }
      return false;
    }).length;
  })()`);
if (expectGolden) await journey("no ERD line runs through a table", async () => {
  await route("#/data");
  const bad = await linesThroughCards();
  expect(bad === 0, `${bad} lines run through a table`);
});
if (expectGolden) await journey("the architecture is drawn from the inferred model, and marked inferred", async () => {
  await route("#/architecture");
  const links = await text("#calm-links");
  await shot("architecture");
  expect((await evaluate(`document.querySelectorAll("#calm-diagram .table-card").length`)) >= 4, "too few components");
  const column = (id) => evaluate(`Number(document.querySelector('#calm-diagram [data-component="${id}"]').dataset.column)`);
  expect((await column("frontend")) < (await column("backend")) && (await column("backend")) < (await column("db")), "the diagram doesn't read frontend, backend, db");
  expect((await evaluate(`document.querySelectorAll("#calm-diagram path.rel").length`)) === 3, "the links aren't all drawn");
  const drift = await text("#calm-drift");
  expect(drift.includes("payments") && drift.includes("Declared, but not found in the code"), `the declared model's difference isn't shown: ${drift.slice(0, 120)}`);
  const crossing = await linesThroughCards();
  expect(crossing === 0, `${crossing} lines run through a component`);
  expect(links.includes("frontend") && links.includes("backend") && links.includes("db"), links);
  expect((await text("#main")).includes("inferred"), "not marked inferred");
});
if (expectGolden) await journey("quality names the real hotspot, and coverage shows the real report", async () => {
  await route("#/quality");
  await shot("quality");
  expect((await text("#hotspots")).includes("discount"), "no hotspot");
  await route("#/coverage");
  await shot("coverage");
  const t = await text("#main");
  expect(t.includes("75%") && t.includes("backend/app/services/orders.py"), t.slice(0, 200));
});
await journey("CVEs say they haven't been checked, not that they're clean, and make no network call", async () => {
  await route("#/cves");
  await shot("cves");
  expect(await evaluate(`!!document.querySelector("#cves-unknown") && !document.querySelector("#cves-clean")`), "reads as clean");
  expect((await text("#main")).includes("osv.dev"), "doesn't say where a check would go");
  expect(requests.every((u) => u.startsWith(origin) || u.startsWith("data:") || u.startsWith("blob:")), "something was fetched elsewhere");
});
// Uses the network, so it runs only when asked: --network.
if (args.includes("--network")) await journey("checking for CVEs finds the known ones, with fixes", async () => {
  await route("#/cves");
  await evaluate(`document.querySelector("#check-cves").click()`);
  // the check runs as a run, and the page follows it
  await until(`location.hash.startsWith("#/runs/") && /succeeded|failed/i.test(document.querySelector("#run-state .pill")?.textContent || "")`, "the check to finish", 180000);
  expect(/succeeded/i.test(await evaluate(runState)), `the check ended: ${await evaluate(runState)}`);
  await route("#/cves");
  await shot("cves-found");
  const list = await text("#cve-list");
  expect(/jinja2/i.test(list), `jinja2's known CVEs aren't listed: ${list.slice(0, 160)}`);
  expect(/\d+\.\d+/.test(list), "no fixed version is shown");
});
if (expectGolden) await journey("the overview summarises every section, and says what's unknown", async () => {
  await route("#/");
  await until(`!!document.querySelector("#overview-sections")`, "the summary");
  const t = await text("#overview-sections");
  for (const part of ["Code map", "End-to-end flows", "4 tables", "5 routes", "Architecture", "Quality", "Coverage", "CVEs"]) expect(t.includes(part), `missing ${part}: ${t}`);
});
await journey("a workflow draft is built by keyboard-friendly form, and Ananke's own errors come back", async () => {
  await route("#/workflows");
  await evaluate(`(() => { const p = document.querySelector("#workflow-preset"); p.value = "review"; p.dispatchEvent(new Event("change", { bubbles: true })); })()`);
  await sleep(100);
  expect((await evaluate(`document.querySelectorAll(".workflow-step").length`)) === 2, "the preset didn't load");
  expect((await text("#workflow-edges")).includes("plan.plan"), "the steps weren't linked by type");
  const before = requests.length;
  await evaluate(`document.querySelector("#workflow-preview").click()`);
  await until(`!!document.querySelector("#workflow-issues")`, "Ananke's answer");
  const issues = await text("#workflow-issues");
  expect(/[A-Z]+_[A-Z]+/.test(issues), `no typed error: ${issues.slice(0, 120)}`);
  expect(requests.length >= before, "no request");
  const runs = await evaluate(`fetch("/api/v1/runs?workspace=" + encodeURIComponent(document.querySelector("#workspace").value)).then((r) => r.json()).then((d) => d.runs.filter((x) => x.kind === "workflow.run").length)`);
  expect(runs === 0, "a preview started something");
});
if (expectGolden) await journey("the canvas works from the keyboard, keeps types honest, and shares one draft with the form", async () => {
  await route("#/workflows");
  await evaluate(`(() => { const p = document.querySelector("#workflow-preset"); p.value = "review"; p.dispatchEvent(new Event("change", { bubbles: true })); for (const c of document.querySelectorAll(".step-capability")) { c.value = "demo/demo-step@1.0.0"; c.dispatchEvent(new Event("input", { bubbles: true })); } document.querySelector("#workflow-mode-canvas").click(); })()`);
  await sleep(100);
  expect((await evaluate(`document.querySelectorAll("#workflow-canvas .workflow-node").length`)) === 2, "the canvas has no steps");
  expect((await evaluate(`document.querySelectorAll("#workflow-canvas .workflow-edge").length`)) === 1, "the form's link isn't drawn");
  // arrow keys move a step, and nothing Ananke sees changes
  const hash = async () => { await evaluate(`document.querySelector("#workflow-preview").click()`); await until(`!!document.querySelector("#workflow-hash") || !!document.querySelector("#workflow-issues")`, "the preview"); expect(!(await evaluate(`!!document.querySelector("#workflow-issues")`)), `problems: ${await text("#workflow-issues")}`); return text("#workflow-hash"); };
  const first = await hash();
  await evaluate(`document.querySelector('[data-id="plan"]').focus()`);
  const before = await evaluate(`document.querySelector('[data-id="plan"]').getAttribute("transform")`);
  await key("ArrowRight", "ArrowRight", 39);
  const after = await evaluate(`document.querySelector('[data-id="plan"]').getAttribute("transform")`);
  expect(before !== after, "the arrow key didn't move it");
  expect(await evaluate(`document.activeElement?.dataset?.id === "plan"`), "focus was lost");
  await evaluate(`document.querySelector("#workflow-result").replaceChildren()`);
  expect((await hash()) === first, "moving a step changed the plan");
  // a link of the wrong type is refused, and says why
  await evaluate(`(() => { document.querySelector("#workflow-mode-form").click(); const o = document.querySelectorAll(".step-outputs")[1]; o.value = "findings:json/v1"; o.dispatchEvent(new Event("change", { bubbles: true })); document.querySelector("#workflow-mode-canvas").click(); })()`);
  await evaluate(`document.querySelector('[data-port="out:review:findings"]').focus()`);
  await key("Enter", "Enter", 13);
  await evaluate(`document.querySelector('[data-port="in:review:plan"]').dispatchEvent(new MouseEvent("click", { bubbles: true }))`);
  expect(/can't take its own output/.test(await text("#workflow-status")), await text("#workflow-status"));
  await evaluate(`(() => { document.querySelector("#workflow-mode-form").click(); const i = document.querySelectorAll(".step-inputs")[1]; i.value = "plan:json/v1"; i.dispatchEvent(new Event("change", { bubbles: true })); document.querySelector("#workflow-mode-canvas").click(); })()`);
  await evaluate(`document.querySelector('[data-port="out:plan:plan"]').dispatchEvent(new MouseEvent("click", { bubbles: true }))`);
  await evaluate(`document.querySelector('[data-port="in:review:plan"]').dispatchEvent(new MouseEvent("click", { bubbles: true }))`);
  expect(/don't fit/.test(await text("#workflow-status")), `a wrong type was linked: ${await text("#workflow-status")}`);
  await evaluate(`(() => { document.querySelector("#workflow-mode-form").click(); const i = document.querySelectorAll(".step-inputs")[1]; i.value = "plan:markdown/v1"; i.dispatchEvent(new Event("change", { bubbles: true })); document.querySelector("#workflow-mode-canvas").click(); })()`);
  await evaluate(`document.querySelector('[data-port="out:plan:plan"]').dispatchEvent(new MouseEvent("click", { bubbles: true }))`);
  await evaluate(`document.querySelector('[data-port="in:review:plan"]').dispatchEvent(new MouseEvent("click", { bubbles: true }))`);
  expect(/Connected plan.plan to review.plan/.test(await text("#workflow-status")), await text("#workflow-status"));
  // export and import give the same plan, whatever the order
  const exported = await evaluate(`new Promise((done) => { const real = URL.createObjectURL; URL.createObjectURL = (b) => { b.text().then(done); URL.createObjectURL = real; return real.call(URL, b); }; document.querySelector("#workflow-export").click(); })`);
  const draft = JSON.parse(exported);
  expect(!("layout" in draft) && !JSON.stringify(draft).includes("transform"), "where steps sit leaked into the draft");
  await evaluate(`document.querySelector("#workflow-result").replaceChildren()`);
  const second = await hash();
  draft.nodes.reverse();
  await evaluate(`(() => { const t = new DataTransfer(); t.items.add(new File([${JSON.stringify(JSON.stringify(draft))}], "d.json", { type: "application/json" })); const i = document.querySelector("#workflow-import"); i.files = t.files; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
  await sleep(200);
  await evaluate(`document.querySelector("#workflow-result").replaceChildren()`);
  expect((await hash()) === second, "export and import changed the plan");
  for (const [w, h, mobile] of [[390, 844, true], [768, 1024, false], [1440, 900, false]]) {
    await viewport(w, h, mobile);
    await sleep(80);
    expect(await evaluate(`document.documentElement.scrollWidth <= window.innerWidth + 1`), `sideways scroll at ${w}px`);
    expect(await evaluate(`document.querySelector("#workflow-canvas").getBoundingClientRect().width > 0`), `no canvas at ${w}px`);
  }
  await shot("workflow-canvas");
});
await journey("a deck comes from a Markdown file, and a path out of the workspace is refused", async () => {
  expectedStatus = /status of (400|401|404|503)/;
  await route("#/docs");
  await until(`!!document.querySelector("#documents")`, "the list");
  const r = await evaluate(`(async () => {
    const token = document.querySelector("#workspace").value;
    const session = await fetch("/api/v1/session").then((x) => x.json());
    const post = (body) => fetch("/api/v1/documents/build", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", [session.csrf_header]: session.csrf_token }, body: JSON.stringify({ workspace: token, ...body }) });
    const out = await post({ path: "../../etc/hosts.md", what: "deck" });
    return { status: out.status, listed: document.querySelector("#documents").textContent };
  })()`);
  expect(r.status === 400, `the escape got ${r.status}`);
  expect(r.listed.includes(".md"), r.listed);
  await evaluate(`document.querySelector('#documents button[aria-label^="Make a deck"]').click()`);
  await until(`!!document.querySelector("#document-built") || !!document.querySelector('#document-result [role="alert"]')`, "the deck");
  expect(await evaluate(`!!document.querySelector("#document-built")`), `no deck: ${await text("#document-result")}`);
  expectedStatus = /status of (401|404|503)/;
});
await journey("learning review says when there's nothing to review", async () => {
  await route("#/learning");
  await until(`!!document.querySelector("#learning-none") || !!document.querySelector("#learning-list")`, "the list");
});
if (expectGolden) await journey("findings come from the repository's own reports, worst first, with what to fix first", async () => {
  await route("#/findings");
  await until(`!!document.querySelector("#findings-list")`, "the findings");
  const r = await evaluate(`({ first: document.querySelector("#findings-list tbody tr td")?.textContent, list: document.querySelector("#findings-first")?.textContent || "", tests: document.querySelector("#findings-tests")?.textContent || "", failing: document.querySelector("#findings-failures")?.textContent || "" })`);
  expect(r.first === "critical", `the worst isn't first: ${r.first}`);
  expect(r.list.includes("Use a parameter") && r.list.includes("test_refund"), `what to fix: ${r.list.slice(0, 200)}`);
  expect(r.failing.includes("test_refund"), r.failing);
  await shot("findings");
});
await journey("what's certain lists each view's state, and every limit", async () => {
  await route("#/certainty");
  await until(`!!document.querySelector("#certainty-sections")`, "the page");
  const t = await text("#certainty-sections");
  expect(/Unknown: not checked/.test(t), `a CVE check that hasn't run isn't called unknown: ${t.slice(0, 200)}`);
  expect((await text("#certainty-limits")).length > 40, "no limits are listed");
  await shot("certainty");
});
await journey("saving tokens shows a small map and the tools", async () => {
  await route("#/context");
  await shot("context");
  expect((await text("#context-map")).includes("repository map"), "no map");
  expect((await text("#context-tools")).includes("GPL-3.0-or-later"), "no licence");
});
await journey("every new page has no sideways scroll on a phone, and no script errors", async () => {
  await viewport(390, 844, true);
  for (const page of ["map", "flows", "data", "apis", "architecture", "quality", "coverage", "cves", "context"]) {
    await route(`#/${page}`);
    const r = await evaluate(`({ w: document.documentElement.scrollWidth, v: innerWidth })`);
    expect(r.w <= r.v + 1, `${page}: ${r.w} wide on ${r.v}`);
  }
  await viewport(1440, 900);
});
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} journey(s) failed` : `all ${results.length} journeys passed`);
quit(failed ? 1 : 0);
