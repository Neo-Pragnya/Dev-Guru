#!/usr/bin/env node
// Real-Chrome journeys for a dev bpmn process viewer (no test framework, Node 22+ and Chrome).
//   node acceptance/browser/process_journeys.mjs <viewer.html> [--hostile] [--shots DIR]
// Walks the process through a decision, edits a step and reads back the downloaded Markdown, checks that nothing is
// fetched, that hostile step names stay text, and that the page fits a phone. Exits 1 on any failure.
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const report = resolve(args[0] || "");
const opt = (k) => (args.includes(k) ? args[args.indexOf(k) + 1] : null);
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

await viewport(1280, 900);
await journey("the process can be walked through a decision to an end", async () => {
  await go();
  await evaluate(`document.getElementById("sim-step").click()`);
  let steps = 0;
  for (let i = 0; i < 40; i++) {
    const s = await evaluate(`({ next: !document.getElementById("sim-step").disabled, choices: document.querySelectorAll("#sim-choices button").length, label: document.getElementById("sim-step").textContent })`);
    if (s.choices) { await evaluate(`document.querySelectorAll("#sim-choices button")[document.querySelectorAll("#sim-choices button").length - 1].click()`); steps++; continue; }
    if (!s.next) { expect(s.label === "Done", `stopped with "${s.label}"`); break; }
    await evaluate(`document.getElementById("sim-step").click()`); steps++;
  }
  const t = await evaluate(`({ log: document.querySelectorAll("#sim-log li").length, on: document.querySelectorAll("#diagram .on").length })`);
  expect(t.log >= 3, `only ${t.log} steps walked`);
  expect(t.on === 1, `${t.on} nodes highlighted`);
  await shot("process-walk");
  return `${t.log} steps`;
});
await journey("reset starts again", async () => {
  await evaluate(`document.getElementById("sim-reset").click()`);
  const t = await evaluate(`({ log: document.querySelectorAll("#sim-log li").length, on: document.querySelectorAll("#diagram .on").length, label: document.getElementById("sim-step").textContent })`);
  expect(t.log === 0 && t.on === 0 && t.label === "Start", JSON.stringify(t));
});
await journey("an edited step downloads as Markdown dev bpmn can read", async () => {
  await go();
  const md = await evaluate(`(async () => {
    let blob = null; URL.createObjectURL = (b) => { blob = b; return "blob:captured"; };
    HTMLAnchorElement.prototype.click = function () {};
    document.getElementById("name-1").value = "Take the order";
    document.getElementById("lane-1").value = "Front desk";
    document.getElementById("save-md").click();
    return blob ? await blob.text() : "";
  })()`);
  expect(md.startsWith("# "), "no Markdown captured");
  expect(md.includes("1. Front desk: Take the order"), "the edit isn't in the Markdown");
  writeFileSync(process.env.PROCESS_MD_OUT || join(tmpdir(), "process-edited.md"), md);
  return md.split("\n").length + " lines";
});
await journey("nothing is fetched from the network", async () => {
  requests.length = 0;
  await go();
  const remote = requests.filter((u) => !u.startsWith("file:") && !u.startsWith("data:") && !u.startsWith("blob:"));
  expect(remote.length === 0, "fetched " + remote.slice(0, 3).join(", "));
});
if (hostile) {
  await journey("hostile step names stay text", async () => {
    await go();
    await evaluate(`document.getElementById("sim-step").click()`);
    const t = await evaluate(`({ img: document.querySelectorAll("#sim-log img, #routes img, #steps img, #diagram img").length, pwned: !!window.__pwned })`);
    expect(t.img === 0 && !t.pwned, JSON.stringify(t));
  });
}
await viewport(390, 844, true);
await journey("it fits a phone", async () => {
  await go();
  const t = await evaluate(`({ sw: document.documentElement.scrollWidth, iw: window.innerWidth })`);
  expect(t.sw <= t.iw + 1, `page is ${t.sw}px wide on a ${t.iw}px screen`);
});
ws.close(); chrome.kill();
const failed = results.filter((r) => !r.ok).length;
console.log(failed ? `${failed} of ${results.length} journeys failed` : `all ${results.length} journeys passed`);
process.exit(failed ? 1 : 0);
