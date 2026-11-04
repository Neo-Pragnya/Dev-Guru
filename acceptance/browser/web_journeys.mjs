#!/usr/bin/env node
// Real-Chrome journeys for the web interface, against a real `dev serve` and the real Ananke harness.
//   node acceptance/browser/web_journeys.mjs [--shots DIR]
// `dev` must be on PATH. Each run builds its own temporary Git workspace, so nothing depends on what's on this computer:
// few enough files that all of them fit the Code page's node budget, enough symbols that a graph build takes seconds.
// Prints one line per journey and exits 1 on any failure.
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const HOSTILE_NAME = "<img src=x onerror=alert(1)>.py";
const args = process.argv.slice(2);
const shots = args.includes("--shots") ? resolve(args[args.indexOf("--shots") + 1]) : null;
if (args.length && !shots) { console.error("usage: web_journeys.mjs [--shots DIR]"); process.exit(2); }
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"].find(existsSync);
if (!CHROME) { console.error("Chrome not found; set CHROME"); process.exit(2); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function buildWorkspace(root) {
  const FOLDERS = 8, MODULES = 20, FUNCTIONS = 240;
  for (let p = 0; p < FOLDERS; p++) {
    mkdirSync(join(root, `pkg${p}`));
    writeFileSync(join(root, `pkg${p}`, "__init__.py"), "");
    for (let m = 0; m < MODULES; m++) {
      let source = `from pkg${(p + 1) % FOLDERS}.mod${m} import fn0 as other\n\n`;
      for (let f = 0; f < FUNCTIONS; f++) source += `def fn${f}(x):\n    y = x + ${f}\n    return other(y) if y < 0 else y\n\n`;
      writeFileSync(join(root, `pkg${p}`, `mod${m}.py`), source);
    }
  }
  writeFileSync(join(root, HOSTILE_NAME), "def hostile():\n    return 1\n");
  const git = (...a) => execFileSync("git", ["-C", root, ...a], { stdio: "ignore", env: { ...process.env, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1" } });
  git("init", "-q", ".");
  git("add", "-A");
  git("-c", "user.name=journeys", "-c", "user.email=journeys@example.com", "commit", "-qm", "fixture");
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
chrome = spawn(CHROME, ["--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check", "--use-mock-keychain", "--password-store=basic", "--disable-gpu", "about:blank"], { stdio: "ignore" });
setTimeout(() => { console.log("✗ journeys timed out"); quit(1); }, Number(process.env.JOURNEY_TIMEOUT_MS || 240000));
let target;
for (let i = 0; i < 200 && !target; i++) {
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
let expectedStatus = /status of (401|503)/; // a refused request the page handles isn't a fault
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
const shot = async (name) => { if (!shots) return; mkdirSync(shots, { recursive: true }); const r = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(join(shots, `${name}.png`), Buffer.from(r.result.data, "base64")); };
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
const runOf = (runId) => evaluate(`(async () => { const w = (await (await fetch("/api/v1/workspaces")).json()).workspaces[0].id; return await (await fetch("/api/v1/runs/${runId}?workspace=" + w)).json(); })()`);
const eventTypes = `[...document.querySelectorAll("#events li")].map((l) => l.textContent)`;
const drain = (ids) => until(`(async () => { const w = (await (await fetch("/api/v1/workspaces")).json()).workspaces[0].id; for (const id of ${JSON.stringify(ids)}) { const r = await (await fetch("/api/v1/runs/" + id + "?workspace=" + w)).json(); if (r.state === "queued" || r.state === "running") return false; } return true; })()`, "the runs to finish", 120000);

await viewport(1440, 900);
await journey("the login link signs in and leaves the address bar", async () => {
  await goto(login);
  const r = await evaluate(`({ path: location.pathname + location.search, h1: document.querySelector("h1")?.textContent, pill: document.querySelector("#harness").textContent })`);
  expect(r.path === "/", `address still shows ${r.path}`);
  expect(r.h1 === "Overview", `heading is ${r.h1}`);
  expect(/^Ananke \d/.test(r.pill), `harness pill says ${r.pill}`);
  await shot("overview");
  return r.pill;
});
await journey("the strict content policy holds: no inline code, and nothing blocked that the page needs", async () => {
  const r = await evaluate(`(() => { const s = getComputedStyle(document.querySelector(".top")); return { styled: s.display === "flex", inline: document.querySelectorAll("script:not([src]), style, [onclick]").length }; })()`);
  expect(r.styled, "the stylesheet didn't apply");
  expect(r.inline === 0, `${r.inline} inline elements`);
  const csp = await evaluate(`(async () => (await fetch("/")).headers.get("content-security-policy"))()`);
  expect(/default-src 'self'/.test(csp) && !/unsafe/.test(csp), `policy: ${csp}`);
  const blocked = await evaluate(`new Promise((done) => { const s = document.createElement("script"); s.textContent = "window.__inline = 1"; document.head.append(s); s.remove(); done(window.__inline === 1); })`);
  expect(!blocked, "an inline script ran");
  await sleep(200);
  problems = problems.filter((p) => !p.includes("Content Security Policy")); // that refusal was this check
});
await journey("the interface works from the keyboard alone", async () => {
  await goto(`${origin}/`);
  await key("Tab", "Tab", 9);
  expect((await evaluate(`document.activeElement.className`)) === "skip", "the first Tab isn't the skip link");
  await key("Enter", "Enter", 13);
  await sleep(150);
  const skipped = await evaluate(`({ focus: document.activeElement.id, h1: document.querySelector("h1").textContent, hash: location.hash })`);
  expect(skipped.focus === "main" && skipped.h1 === "Overview", `the skip link led to ${JSON.stringify(skipped)}`);
  await goto(`${origin}/`);
  let reached = false;
  for (let i = 0; i < 14 && !reached; i++) { await key("Tab", "Tab", 9); reached = (await evaluate(`document.activeElement.getAttribute("href")`)) === "#/runs"; }
  expect(reached, "Tab never reached Runs");
  expect((await evaluate(`getComputedStyle(document.activeElement).outlineStyle`)) === "solid", "focus isn't visible");
  await key("Enter", "Enter", 13);
  await ready();
  const r = await evaluate(`({ h1: document.querySelector("h1").textContent, focus: document.activeElement.id, current: document.querySelector('nav a[aria-current="page"]').textContent })`);
  expect(r.h1 === "Runs" && r.current === "Runs", JSON.stringify(r));
  expect(r.focus === "main", `focus went to ${r.focus}, not the new page`);
});
await journey("pages that don't exist yet say so and name what works today", async () => {
  const under = await evaluate(`(() => { const out = []; let later = false; for (const n of document.querySelector("nav").children) { if (n.classList.contains("nav-title")) later = n.textContent === "Not in this version"; else if (later) out.push(n.dataset.route); } return out; })()`);
  expect(under.join() === "workflows,quality,docs,learning", `listed as not in this version: ${under}`);
  for (const [hash, command] of [["#/workflows", "ananke app workflow-preview"], ["#/quality", "dev explore"], ["#/docs", "dev present"], ["#/learning", "dev learning review"]]) {
    await route(hash);
    const t = await text("#main");
    expect(/isn't in this version|aren't in this version/.test(t), `${hash} says: ${t.slice(0, 80)}`);
    expect(t.includes(command), `${hash} doesn't mention ${command}`);
  }
  await route("#/nowhere");
  expect((await text("h1")) === "Not found", "an unknown page isn't called out");
});
await journey("an address that isn't a run is refused without asking the gateway", async () => {
  const before = requests.length;
  await route("#/runs/..%2F..%2Fsession");
  expect((await text("h1")) === "Not found", `heading is ${await text("h1")}`);
  expect(requests.length === before, `it sent ${requests.slice(before).join(", ")}`);
  expectedStatus = /status of (401|404|503)/;
  await route("#/runs/run-0123");
  expect((await text("#main")).includes("RUN_NOT_FOUND"), "an unknown run isn't explained");
  expectedStatus = /status of (401|503)/;
});
await journey("quick moves between pages don't mix them up", async () => {
  await evaluate(`location.hash = "#/"`);
  await evaluate(`location.hash = "#/runs"`);
  await evaluate(`location.hash = "#/workflows"`);
  await ready();
  await sleep(1500); // what the earlier pages asked for has arrived by now
  const r = await evaluate(`({ h1: document.querySelectorAll("#main h1").length, title: document.querySelector("#main h1").textContent, cards: document.querySelectorAll("#main .cards").length, table: document.querySelectorAll("#main table").length })`);
  expect(r.h1 === 1 && r.title === "Workflows" && r.cards === 0 && r.table === 0, JSON.stringify(r));
});
await journey("with no graph yet, Code says so and offers to build it; the run is shown live", async () => {
  await route("#/code");
  expect((await text("#main")).includes("GRAPH_MISSING"), "no explanation that the graph is missing");
  await evaluate(`document.querySelector("#build-graph").click()`);
  await until(`location.hash.startsWith("#/runs/run-")`, "the run page");
  await ready();
  await until(`${runState} === "succeeded"`, "the run to finish", 120000);
  await until(`${eventTypes}.at(-1)?.startsWith("run.succeeded")`, "the final event in the timeline");
  const r = await evaluate(`({ events: ${eventTypes}, artifact: document.querySelector("#artifacts a")?.textContent, cancel: document.querySelector("#cancel").hidden })`);
  expect(r.events[0].startsWith("run.queued") && r.events.at(-1).startsWith("run.succeeded"), r.events.join(" | "));
  expect(r.artifact === "graph-snapshot.json", `artifact: ${r.artifact}`);
  expect(r.cancel, "a finished run still offers cancel");
  await shot("run");
  return `${r.events.length} events`;
});
await journey("reloading the tab returns to the same run", async () => {
  const before = await evaluate(`location.hash`);
  await reload();
  const r = await evaluate(`({ hash: location.hash, id: document.querySelector("#run-id")?.textContent, events: document.querySelectorAll("#events li").length })`);
  expect(r.hash === before && before.endsWith(r.id), JSON.stringify(r));
  await until(`${runState} === "succeeded"`, "the state after reload", 15000);
  expect(r.events > 0, "no events after reload");
});
await journey("reloading while a run is going keeps the run, with no event shown twice", async () => {
  const [runId] = await startRuns(1);
  await route(`#/runs/${runId}`);
  const state = await evaluate(runState);
  expect(state === "queued" || state === "running", `the run was already ${state}, so this proved nothing`);
  await reload();
  expect((await text("#run-id")) === runId, "the reload lost the run");
  await until(`${runState} === "succeeded"`, "the run after reload", 120000);
  const seen = await evaluate(eventTypes);
  const queued = seen.filter((e) => e.startsWith("run.queued")).length;
  const done = seen.filter((e) => e.startsWith("run.succeeded")).length;
  expect(queued === 1 && done === 1, seen.join(" | "));
  return `reloaded while ${state}`;
});
await journey("leaving a run's page and coming back doesn't touch the run", async () => {
  const [runId] = await startRuns(1);
  await route(`#/runs/${runId}`);
  await route("#/runs");
  expect((await text("#main")).includes(runId), "the history doesn't list the run");
  await route(`#/runs/${runId}`);
  await until(`${runState} === "succeeded"`, "the run", 120000);
  const seen = await evaluate(eventTypes);
  expect(!seen.some((e) => e.startsWith("run.cancelled")), seen.join(" | "));
});
await journey("an artifact downloads, and can't run as a page on this origin", async () => {
  const r = await evaluate(`(async () => { const a = document.querySelector("#artifacts a"); const res = await fetch(a.href); return { status: res.status, disposition: res.headers.get("content-disposition"), type: res.headers.get("content-type"), csp: res.headers.get("content-security-policy"), download: a.hasAttribute("download") }; })()`);
  expect(r.status === 200 && r.disposition.startsWith("attachment"), JSON.stringify(r));
  expect(r.type === "application/octet-stream" && /sandbox/.test(r.csp) && r.download, JSON.stringify(r));
});
await journey("events the harness no longer keeps are named as a gap, and the run still shows", async () => {
  const [runId] = await startRuns(1);
  await route(`#/runs/${runId}`);
  await until(`${runState} === "succeeded"`, "the run", 120000);
  // what event retention does: drop the oldest events from the run's record
  const log = join(workspace, ".ananke", "app", "runs", runId, "events.jsonl");
  const lines = readFileSync(log, "utf8").split("\n").filter(Boolean);
  writeFileSync(log, lines.slice(2).join("\n") + "\n");
  await reload();
  await until(`${runState} === "succeeded"`, "the run after reload", 15000);
  const seen = await evaluate(eventTypes);
  expect(seen[0].includes("Events 1 to 2 are no longer kept"), seen.join(" | "));
  expect(seen.at(-1).startsWith("run.succeeded"), seen.join(" | "));
  return `${lines.length - 2} of ${lines.length} kept`;
});
await journey("a hostile file name stays text", async () => {
  await route("#/code?collapse=file");
  const r = await evaluate(`({ shown: document.querySelector("#code-table").textContent.includes(${JSON.stringify(HOSTILE_NAME)}), imgs: document.querySelectorAll("#main img").length, rows: document.querySelectorAll("#code-table tbody tr").length })`);
  expect(r.shown, "the fixture's hostile name isn't on the page");
  expect(r.imgs === 0, JSON.stringify(r));
  await shot("code");
  return `${r.rows} rows`;
});
await journey("no link on any page can run script", async () => {
  for (const hash of ["#/", "#/runs", "#/code?collapse=file", "#/sources", "#/workflows"]) {
    await route(hash);
    const bad = await evaluate(`[...document.querySelectorAll("a[href]")].map((a) => a.protocol + " " + a.getAttribute("href")).filter((h) => !/^http: (#\\/|\\/api\\/v1\\/|#main$)/.test(h))`);
    expect(!bad.length, `${hash}: ${bad.slice(0, 3).join(", ")}`);
  }
});
await journey("Code groups by folder, opens a folder, and accounts for its links", async () => {
  await route("#/code?collapse=directory");
  const r = await evaluate(`({ rows: document.querySelectorAll("#code-table tbody tr").length, accounting: document.querySelector("#accounting").textContent })`);
  expect(r.rows > 0 && /Links: \d+ shown/.test(r.accounting), JSON.stringify(r));
  await evaluate(`[...document.querySelectorAll("#code-table tbody button")].find((b) => b.textContent.startsWith("pkg")).click()`);
  await until(`location.hash.includes("path=")`, "the folder to open");
  await ready();
  expect((await text("#main")).includes("show everything"), "no way back to everything");
});
await journey("losing the connection shows it, and the view catches up without repeating events", async () => {
  const [runId] = await startRuns(1);
  await route(`#/runs/${runId}`);
  expectOffline = true;
  await send("Network.emulateNetworkConditions", { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await until(`document.querySelector("#banner").textContent.includes("Connection lost")`, "the lost-connection note", 15000);
  await shot("offline");
  await send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await until(`${runState} === "succeeded" && document.querySelector("#banner").hidden`, "the run after reconnecting, with the note gone", 120000);
  expectOffline = false;
  const r = await evaluate(`({ queued: [...document.querySelectorAll("#events li")].filter(l => l.textContent.startsWith("run.queued")).length, last: document.querySelector("#events li:last-child").textContent })`);
  expect(r.queued === 1 && r.last.startsWith("run.succeeded"), JSON.stringify(r));
  return "reconnected";
});
await journey("cancel is one explicit button, and a cancelled run stays cancelled", async () => {
  // two workers: the first runs hold them, so the last is certainly still queued when it's cancelled
  const ids = await startRuns(4);
  const last = ids.at(-1);
  await route(`#/runs/${last}`);
  expect(!(await evaluate(`document.querySelector("#cancel").hidden`)), "no cancel button on a queued run");
  expect((await evaluate(runState)) === "queued", `the run was ${await evaluate(runState)}, so this proved nothing`);
  await evaluate(`document.querySelector("#cancel").click()`);
  await until(`${runState} === "cancelled"`, "the cancelled state", 15000);
  await shot("cancelled");
  await drain(ids);
  expect((await runOf(last)).state === "cancelled", `the run ended ${(await runOf(last)).state}`);
  expect((await evaluate(`document.querySelector("#cancel").hidden`)), "cancel is still offered");
  const others = await Promise.all(ids.slice(0, -1).map(runOf));
  expect(others.every((o) => o.state === "succeeded"), `cancelling one touched others: ${others.map((o) => o.state)}`);
});
await journey("a run that's already going can be cancelled, and doesn't then claim success", async () => {
  const ids = await startRuns(1);
  await route(`#/runs/${ids[0]}`);
  await until(`${runState} === "running"`, "the run to start", 60000);
  await evaluate(`document.querySelector("#cancel").click()`);
  await until(`${runState} === "cancelled"`, "the cancelled state", 15000);
  await sleep(6000); // the build finishes behind the cancellation
  const after = await runOf(ids[0]);
  expect(after.state === "cancelled", `the run ended ${after.state}`);
  await reload();
  const seen = await evaluate(eventTypes);
  expect(seen.some((e) => e.startsWith("run.cancelled")) && !seen.some((e) => e.startsWith("run.succeeded")), seen.join(" | "));
});
await journey("the theme switch works and is remembered", async () => {
  const before = await evaluate(`document.documentElement.dataset.theme`);
  await evaluate(`document.querySelector("#theme").click()`);
  await reload();
  const after = await evaluate(`document.documentElement.dataset.theme`);
  expect(after !== before, `still ${after}`);
  await shot(`theme-${after}`);
  return `${before} → ${after}`;
});
await journey("every page fits a phone, with no sideways scroll", async () => {
  await viewport(390, 844, true);
  for (const hash of ["#/", "#/runs", "#/code?collapse=file", "#/sources", "#/workflows"]) {
    await route(hash);
    const w = await evaluate(`[document.documentElement.scrollWidth, innerWidth]`);
    expect(w[0] <= w[1] + 1, `${hash}: ${w[0]} > ${w[1]}`);
    const nav = await evaluate(`[...document.querySelectorAll("nav a")].every((a) => { const r = a.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= innerWidth + 1; })`);
    expect(nav, `${hash}: a navigation link is off the screen`);
  }
  await shot("phone");
  await viewport(1440, 900);
  return "fits 390 px";
});
await journey("nothing is fetched from anywhere else", async () => {
  const outside = requests.filter((u) => !u.startsWith(origin) && !u.startsWith("about:") && !u.startsWith("data:"));
  expect(!outside.length, "requested: " + outside.slice(0, 3).join(", "));
  return `${requests.length} requests, all to this gateway`;
});
ws.close();
const failed = results.filter((r) => !r).length;
console.log(failed ? `${failed} journey(s) failed` : `all ${results.length} journeys passed`);
quit(failed ? 1 : 0);
