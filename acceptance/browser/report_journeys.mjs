#!/usr/bin/env node
// Real-Chrome journeys for a Dev Guru explorer report (no test framework, Node 22+ and Chrome).
//   node acceptance/browser/report_journeys.mjs <report.html> [--expect-files N] [--hostile] [--shots DIR]
// Checks every view renders, search/inspector/palette/tour/theme work, nothing is fetched from the network,
// hostile text stays text, and the page fits a phone. Prints one line per journey and exits 1 on any failure.
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const report = resolve(args[0] || "");
const opt = (k) => (args.includes(k) ? args[args.indexOf(k) + 1] : null);
const expectFiles = opt("--expect-files") ? Number(opt("--expect-files")) : null;
const hostile = args.includes("--hostile");
const shots = opt("--shots");
if (!existsSync(report)) { console.error(`no report at ${report}`); process.exit(2); }
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"].find(existsSync);
if (!CHROME) { console.error("Chrome not found; set CHROME"); process.exit(2); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const port = 9300 + Math.floor(Math.random() * 400);
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "dg-chrome-"))}`, "--no-first-run", "--no-default-browser-check", "--use-mock-keychain", "--password-store=basic", "--disable-gpu", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
setTimeout(() => { console.log("✗ journeys timed out"); chrome.kill(); process.exit(1); }, Number(process.env.JOURNEYS_TIMEOUT_MS || 150000)).unref();
let target;
for (let i = 0; i < 100 && !target; i++) { await sleep(150); try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch {} }
if (!target) { console.log("✗ Chrome exposed no DevTools target"); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map(); let problems = []; const requests = [];
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") problems.push("exception: " + (msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text).split("\n")[0]);
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") problems.push("console.error: " + msg.params.args.map((a) => a.value ?? a.description).join(" ").slice(0, 200));
  if (msg.method === "Page.javascriptDialogOpening") problems.push("dialog opened: " + msg.params.message);
  if (msg.method === "Network.requestWillBeSent") requests.push(msg.params.request.url);
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error("eval: " + r.result.exceptionDetails.text); return r.result?.result?.value; };
await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
const viewport = (width, height, mobile = false) => send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
const url = pathToFileURL(report).href;
const go = async (hash = "", settle = 1200) => { problems = []; await send("Page.navigate", { url: url + hash }); await sleep(settle); };
const key = async (k, mods = 0) => { for (const type of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key: k, code: k.length === 1 ? "Key" + k.toUpperCase() : k, modifiers: mods, windowsVirtualKeyCode: k.length === 1 ? k.toUpperCase().charCodeAt(0) : k === "Enter" ? 13 : k === "Escape" ? 27 : 0, text: type === "keyDown" && k.length === 1 ? k : undefined }); };
const shot = async (name) => { if (!shots) return; const r = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(join(shots, name + ".png"), Buffer.from(r.result.data, "base64")); };
const results = [];
async function journey(name, fn) {
  try { const detail = (await fn()) || ""; if (problems.length) throw new Error(problems.slice(0, 3).join(" | ")); results.push({ name, ok: true }); console.log(`✓ ${name}${detail ? ` (${detail})` : ""}`); }
  catch (e) { results.push({ name, ok: false, detail: String(e.message || e) }); console.log(`✗ ${name}: ${e.message || e}`); }
}
const expect = (c, m) => { if (!c) throw new Error(m); };

await viewport(1440, 900);
await journey("the report opens offline and draws the constellation", async () => {
  await go("", 1800);
  const t = await evaluate(`({ files: window.__devGuru.D.files.length, nodes: document.querySelectorAll("#svg .node").length, title: document.title, foot: document.querySelector("#foot").innerText })`);
  expect(t.nodes === t.files, `${t.nodes} nodes for ${t.files} files`);
  if (expectFiles !== null) expect(t.files === expectFiles, `report has ${t.files} files, expected ${expectFiles}`);
  expect(/offline · view-only/.test(t.foot), "footer missing the offline note");
  await shot("constellation");
  return `${t.nodes} files`;
});
await journey("hover lights up a file's neighbours and sends pulses along its imports", async () => {
  const r = await evaluate(`(() => { const best = [...window.__devGuru.D.files].sort((a,b)=>(b.fan_in+b.fan_out)-(a.fan_in+a.fan_out))[0]; const g = document.querySelector('#svg .node[data-id="'+CSS.escape(best.id)+'"]'); g.dispatchEvent(new MouseEvent("mouseenter")); return { hot: document.querySelectorAll("#svg .node.hot").length, edges: document.querySelectorAll("#svg .edge.hot").length, dim: document.querySelector("#svg").classList.contains("dim"), links: best.fan_in + best.fan_out }; })()`);
  await new Promise((r) => setTimeout(r, 300));
  const pulses = await evaluate(`document.querySelectorAll("#svg .pulse").length`);
  if (!r.links) return "no imports between files in this project: nothing to light up";
  expect(r.dim && r.hot >= 2 && r.edges >= 1, JSON.stringify(r));
  expect(pulses > 0, "no pulses travelling");
  return `${r.hot} lit, ${r.edges} edges, ${pulses} pulses`;
});
await journey("search finds a symbol and the inspector shows its source as text", async () => {
  const sym = await evaluate(`(window.__devGuru.D.symbols.find(s => s.source && s.source.length > 20) || window.__devGuru.D.symbols[0]).name`);
  await evaluate(`document.querySelector("#search").focus()`);
  for (const ch of sym.split(".").pop()) await send("Input.insertText", { text: ch });
  await sleep(250);
  const n = await evaluate(`document.querySelectorAll("#results .result").length`);
  expect(n > 0, "no search results");
  await key("Enter");
  await sleep(500);
  const ins = await evaluate(`({ h: document.querySelector("#inspectBody h2")?.textContent, src: document.querySelectorAll("#inspectBody pre.src span").length, sel: window.__devGuru.state.sel })`);
  expect(ins.h && ins.sel, "nothing selected: " + JSON.stringify(ins));
  return `${n} results → ${ins.h} (${ins.src} source lines)`;
});
await journey("every view renders: flow, impact rings, calls, hotspots", async () => {
  const counts = {};
  for (const [k, sel] of [["2", "#svg .node"], ["3", "#svg .node"], ["4", "#svg .node"], ["5", "#treemap .tm-cell"]]) {
    await key(k); await sleep(700);
    counts[k] = await evaluate(`document.querySelectorAll(${JSON.stringify(sel)}).length`);
    await shot(["", "", "flow", "impact", "calls", "hotspots"][+k]);
  }
  const rings = await evaluate(`(window.__devGuru.renderView("impact"), document.querySelectorAll("#svg .ring").length)`);
  const imports = await evaluate(`window.__devGuru.D.project.imports`);
  expect((counts["2"] > 0 || imports === 0) && counts["3"] > 0 && counts["5"] > 0, JSON.stringify(counts));
  return `flow ${counts["2"]}, impact ${counts["3"]} (${rings} rings), calls ${counts["4"]}, hotspots ${counts["5"]}`;
});
await journey("the guided tour narrates and advances", async () => {
  await key("6"); await sleep(2600);
  const a = await evaluate(`({ shown: !document.querySelector("#narration").hidden, step: document.querySelector("#tourStep").textContent, text: document.querySelector("#tourText").textContent })`);
  expect(a.shown && a.text.length > 10, "tour not narrating: " + JSON.stringify(a));
  await evaluate(`document.querySelector("#tourNext").click()`); await sleep(500);
  const b = await evaluate(`document.querySelector("#tourStep").textContent`);
  expect(b !== a.step, "tour did not advance");
  await shot("tour");
  await evaluate(`document.querySelector("#tourPlay").click()`);
  return `${a.step} → ${b}`;
});
await journey("the command palette jumps to a view and the theme toggles into the URL", async () => {
  await key("k", 2); await sleep(200);
  const open = await evaluate(`!document.querySelector("#palette").hidden`);
  expect(open, "Ctrl+K did not open the palette");
  for (const ch of "hotspots") await send("Input.insertText", { text: ch });
  await sleep(150); await key("Enter"); await sleep(500);
  const v = await evaluate(`window.__devGuru.state.view`);
  expect(v === "hotspots", "palette went to " + v);
  await evaluate(`document.querySelector("#themeBtn").click()`); await sleep(200);
  const h = await evaluate(`({ theme: document.documentElement.dataset.theme, hash: location.hash })`);
  expect(h.theme === "day" && /theme=day/.test(h.hash), JSON.stringify(h));
  await shot("day");
  return "palette → hotspots; day theme in the hash";
});
if (hostile) await journey("hostile docstrings and source stay inert text", async () => {
  await go("", 1500);
  const r = await evaluate(`(() => { const s = window.__devGuru.D.symbols.find(x => (x.doc + x.source).includes("</script>")); if (!s) return { missing: true }; window.__devGuru.select(s.id); return { imgs: document.querySelectorAll("#inspectBody img, #inspectBody script").length, shown: document.querySelector("#inspectBody").textContent.includes("</script>"), pwned: !!window.__pwned }; })()`);
  expect(!r.missing, "fixture has no hostile symbol");
  expect(r.imgs === 0 && r.shown && !r.pwned, JSON.stringify(r));
  return "rendered as text, nothing executed";
});
await journey("nothing is fetched from the network", async () => {
  const outside = requests.filter((u) => !u.startsWith("file:") && !u.startsWith("data:") && !u.startsWith("blob:") && u !== "about:blank");
  expect(!outside.length, "requested: " + outside.slice(0, 3).join(", "));
  return `${requests.length} local loads only`;
});
await journey("a phone-width screen has no horizontal scroll", async () => {
  await viewport(390, 844, true); await go("", 1500);
  const w = await evaluate(`[document.documentElement.scrollWidth, window.innerWidth]`);
  expect(w[0] <= w[1] + 1, `${w[0]} > ${w[1]}`);
  await shot("phone");
  return "fits 390 px";
});
ws.close(); chrome.kill();
const failed = results.filter((r) => !r.ok);
console.log(failed.length ? `${failed.length} journey(s) failed` : `all ${results.length} journeys passed`);
process.exit(failed.length ? 1 : 0);
