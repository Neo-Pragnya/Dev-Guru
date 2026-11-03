"""Small offline pages: the capability source picker and the learning-candidate review.

Same rules as the explorer: one file, a CSP that forbids network requests, embedded data as escaped JSON, and
untrusted text (summaries, skill text, diffs) written only through ``textContent``.
"""

from __future__ import annotations

import html
from typing import Any

from dev_guru.reports.render import safe_json

_HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; base-uri 'none'">
<title>{title}</title><style>
:root{{--bg:#0d0e1c;--panel:#15172f;--ink:#efedf9;--muted:#a4a6c9;--accent:#ffb347;--ok:#3dd6c6;--bad:#ff6f91;--line:rgba(160,165,255,.18)}}
@media (prefers-color-scheme:light){{:root{{--bg:#faf7f0;--panel:#fff;--ink:#1d1b2c;--muted:#5d5a73;--accent:#a3420f;--ok:#0b6f66;--bad:#b3264d;--line:rgba(40,30,90,.14)}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 Inter,system-ui,sans-serif}}main{{max-width:1080px;margin:0 auto;padding:24px 16px 64px}}
h1{{margin:0 0 4px}}.muted{{color:var(--muted)}}input{{font:inherit;width:100%;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:inherit}}
.chips{{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}}.chip{{border:1px solid var(--line);border-radius:999px;padding:3px 10px;background:var(--panel);color:inherit;font:inherit;font-size:13px;cursor:pointer}}
.chip[aria-pressed=true]{{border-color:var(--accent);color:var(--accent)}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}}
code,pre{{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:13px}}pre{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;overflow:auto}}
.ok{{color:var(--ok)}}.bad{{color:var(--bad)}}.add{{color:var(--ok)}}.del{{color:var(--bad)}}section{{margin-top:24px}}
</style></head><body><main id="main"></main>
<script type="application/json" id="data">{data}</script><script>{script}</script></body></html>"""

_SOURCES_JS = """(() => {
const D = JSON.parse(document.getElementById("data").textContent), main = document.getElementById("main");
const el = (t, p = {}, ...k) => { const n = document.createElement(t); Object.assign(n, p); n.append(...k); return n; };
const sources = [...new Set(D.items.map((c) => c.identity.split(":")[0]))].sort();
const picked = new Set();
const q = el("input", { type: "search", placeholder: "Filter by name or summary", ariaLabel: "Filter capabilities" });
const chips = el("div", { className: "chips", role: "group", ariaLabel: "Sources" });
const count = el("p", { className: "muted", ariaLive: "polite" });
const body = el("tbody");
main.append(el("h1", { textContent: "Capability sources" }), el("p", { className: "muted", textContent: "Every capability your project's sources offer, through Ananke's provider port. Identity is source:namespace/name; versions and digests are exact." }), q, chips, count,
  el("table", {}, el("thead", {}, el("tr", {}, ...["Capability", "Kind", "Version", "Licence", "Summary"].map((h) => el("th", { textContent: h })))), body));
for (const s of sources) { const b = el("button", { className: "chip", textContent: s }); b.setAttribute("aria-pressed", "false");
  b.onclick = () => { picked.has(s) ? picked.delete(s) : picked.add(s); b.setAttribute("aria-pressed", String(picked.has(s))); draw(); }; chips.append(b); }
function draw() {
  const words = q.value.toLowerCase().split(/\\s+/).filter(Boolean);
  const rows = D.items.filter((c) => (!picked.size || picked.has(c.identity.split(":")[0])) && words.every((w) => (c.identity + " " + c.summary).toLowerCase().includes(w)));
  body.replaceChildren(...rows.map((c) => el("tr", {}, el("td", {}, el("code", { textContent: c.identity })), el("td", { textContent: c.kind }),
    el("td", { textContent: c.version, title: "sha256:" + c.digest }), el("td", { textContent: c.licence }), el("td", { textContent: c.summary }))));
  count.textContent = rows.length + " of " + D.items.length + " capabilities";
}
q.oninput = draw; draw();
})();"""

_REVIEW_JS = """(() => {
const D = JSON.parse(document.getElementById("data").textContent), main = document.getElementById("main");
const el = (t, p = {}, ...k) => { const n = document.createElement(t); Object.assign(n, p); n.append(...k); return n; };
const ready = D.problems.length === 0;
main.append(el("h1", { textContent: "Learning candidate: " + D.name }),
  el("p", { className: ready ? "ok" : "bad", textContent: ready ? "Every gate passes: ready to promote." : "Not ready: " + D.problems.join("; ") }));
const cases = el("tbody", {}, ...D.cases.map((c) => el("tr", {}, el("td", { textContent: c.id }), el("td", { textContent: c.kind }),
  el("td", {}, el("code", { textContent: c.command || "" })), el("td", { className: c.passed === true ? "ok" : "bad", textContent: c.passed === true ? "passed" : c.passed === false ? "failed" : "not run" }))));
main.append(el("section", {}, el("h2", { textContent: "Evaluation" }), el("p", { className: "muted", textContent: D.evaluated_at ? "Evaluated " + D.evaluated_at : "Not evaluated yet" }),
  el("table", {}, el("thead", {}, el("tr", {}, ...["Case", "Kind", "Command", "Result"].map((h) => el("th", { textContent: h })))), cases)));
const rv = D.review;
main.append(el("section", {}, el("h2", { textContent: "Review" }), el("p", { textContent: rv ? rv.decision + " by " + rv.reviewer + ": " + rv.reason : "Not reviewed yet" })));
const prov = D.provenance || {};
main.append(el("section", {}, el("h2", { textContent: "Provenance" }), el("p", { className: "muted", textContent: "Visibility " + (prov.visibility || "?") + " · from runs " + ((prov.runs || []).join(", ") || "none recorded") + " · " + (prov.redactions || 0) + " redaction(s)" })));
for (const d of D.destinations) {
  const pre = el("pre");
  for (const line of d.diff.split("\\n")) pre.append(el("span", { className: line.startsWith("+") && !line.startsWith("+++") ? "add" : line.startsWith("-") && !line.startsWith("---") ? "del" : "", textContent: line + "\\n" }));
  main.append(el("section", {}, el("h2", { textContent: "Destination " + d.source }),
    el("p", { className: d.writable ? "" : "muted", textContent: (d.writable ? "Writable" : "Read-only") + " · " + d.visibility + " · " + (d.existing_version ? "would update version " + d.existing_version : "new capability") }), pre));
}
main.append(el("section", {}, el("h2", { textContent: "SKILL.md" }), el("pre", { textContent: D.skill_md })));
})();"""


def sources_page(items: list[dict[str, Any]]) -> str:
    return _HEAD.format(
        title="Capability sources · Dev Guru", data=safe_json({"items": items}), script=_SOURCES_JS
    )


def review_page(candidate: dict[str, Any]) -> str:
    return _HEAD.format(
        title=html.escape(f"{candidate['name']} · learning review · Dev Guru"),
        data=safe_json(candidate),
        script=_REVIEW_JS,
    )


__all__ = ["review_page", "sources_page"]
