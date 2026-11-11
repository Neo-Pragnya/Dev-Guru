"""A swimlane drawing and an offline viewer for a process Ananke read. Ananke decides what the process is.

The viewer also lets you co-design it: step through the process (choosing at each decision), see every way through
it, rename steps and lanes, and download the result as Markdown in the format ``dev bpmn`` reads, so a change goes
back through Ananke rather than around it.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any

MAX_PATHS = 50

LANE_H = 140
LABEL_W = 130
COL_W = 170
BOX_W = 130
BOX_H = 58


def _columns(model: dict[str, Any]) -> dict[str, int]:
    outgoing: dict[str, list[str]] = {}
    for flow in model["flows"]:
        outgoing.setdefault(flow["source"], []).append(flow["target"])
    column = {n["id"]: 0 for n in model["nodes"] if n["kind"] == "start"}
    waiting = list(column)
    while waiting:
        now = waiting.pop(0)
        for target in outgoing.get(now, []):
            if target not in column:
                column[target] = column[now] + 1
                waiting.append(target)
    deepest = max(column.values(), default=0)
    return {n["id"]: column.get(n["id"], deepest + 1) for n in model["nodes"]}


def _wrap(text: str, width: int = 19, lines: int = 3) -> list[str]:
    out: list[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + len(word) + 1 > width:
            out.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        out.append(current)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: width - 3] + "..."
    return out


def render(model: dict[str, Any]) -> str:
    """A swimlane diagram as SVG. Text is escaped, and nothing in it runs or loads."""
    columns = _columns(model)
    lanes = {lane: i for i, lane in enumerate(model["lanes"])}
    used: dict[tuple[int, int], int] = {}
    centre: dict[str, tuple[int, int, str]] = {}
    for node in model["nodes"]:
        col, row = columns[node["id"]], lanes.get(node["lane"], 0)
        stacked = used.get((col, row), 0)
        used[(col, row)] = stacked + 1
        centre[node["id"]] = (
            LABEL_W + 40 + col * COL_W + BOX_W // 2,
            row * LANE_H + LANE_H // 2 + stacked * 22,
            node["kind"],
        )
    width = LABEL_W + 80 + (max(columns.values(), default=0) + 1) * COL_W
    height = max(1, len(lanes)) * LANE_H
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{escape(str(model["name"]), quote=True)}">',
        "<style>.lane{fill:#faf7f2;stroke:#c9c2b6}.alt{fill:#f3efe8}.lab{font:600 13px system-ui,sans-serif;fill:#3a2f25}"
        ".box{fill:#fff;stroke:#7a6a58;stroke-width:1.5}.dec{fill:#fff4dc;stroke:#b27a1e;stroke-width:1.5}.ev{fill:#fff;stroke:#2c7a6b;stroke-width:2}.fin{fill:#fff;stroke:#a33;stroke-width:3}"
        ".t{font:12px system-ui,sans-serif;fill:#2a2118}.l{font:11px system-ui,sans-serif;fill:#6b5a48}.e{fill:none;stroke:#6b5a48;stroke-width:1.4}.h{fill:#6b5a48}</style>",
        '<defs><marker id="a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path class="h" d="M0 0L8 4L0 8z"/></marker></defs>',
    ]
    for lane, row in lanes.items():
        y = row * LANE_H
        parts.append(
            f'<rect class="lane{" alt" if row % 2 else ""}" x="0" y="{y}" width="{width}" height="{LANE_H}"/>'
        )
        parts.append(
            f'<text class="lab" x="12" y="{y + LANE_H // 2 + 4}">{escape(str(lane)[:18])}</text>'
        )

    def half(kind: str) -> int:
        return BOX_W // 2 if kind == "task" else (30 if kind == "decision" else 16)

    for flow in model["flows"]:
        a, b = centre.get(flow["source"]), centre.get(flow["target"])
        if not a or not b:
            continue
        x1, y1, x2, y2 = a[0] + half(a[2]), a[1], b[0] - half(b[2]), b[1]
        if x2 <= x1:  # a link back: out of the side and around
            x1, x2 = a[0] - half(a[2]), b[0] + half(b[2])
            path = f"M{x1} {y1} C{x1 - 60} {y1 - 70} {x2 + 60} {y2 - 70} {x2} {y2}"
        else:
            bend = max(30, (x2 - x1) // 2)
            path = f"M{x1} {y1} C{x1 + bend} {y1} {x2 - bend} {y2} {x2} {y2}"
        parts.append(
            f'<path class="e" d="{path}" marker-end="url(#a)"><title>{escape(str(flow["id"]))}</title></path>'
        )
        if flow.get("label"):
            parts.append(
                f'<text class="l" x="{(x1 + x2) // 2}" y="{(y1 + y2) // 2 - 6}" text-anchor="middle">{escape(str(flow["label"])[:20])}</text>'
            )
    for node in model["nodes"]:
        x, y, kind = centre[node["id"]]
        title = f"<title>{escape(str(node['name']))} ({escape(str(node.get('evidence') or ''))})</title>"
        if kind == "start":
            parts.append(
                f'<g data-node="{escape(str(node["id"]), quote=True)}">{title}<circle class="ev" cx="{x}" cy="{y}" r="16"/></g>'
            )
            continue
        if kind == "end":
            parts.append(
                f'<g data-node="{escape(str(node["id"]), quote=True)}">{title}<circle class="fin" cx="{x}" cy="{y}" r="16"/></g>'
            )
            continue
        lines = _wrap(str(node["name"]))
        if kind == "decision":
            shape = f'<polygon class="dec" points="{x},{y - 30} {x + 30},{y} {x},{y + 30} {x - 30},{y}"/>'
            text_y = y + 46
        else:
            shape = f'<rect class="box" x="{x - BOX_W // 2}" y="{y - BOX_H // 2}" width="{BOX_W}" height="{BOX_H}" rx="8"/>'
            text_y = y - (len(lines) - 1) * 7 + 4
        words = "".join(
            f'<text class="t" x="{x}" y="{text_y + i * 14}" text-anchor="middle">{escape(line)}</text>'
            for i, line in enumerate(lines)
        )
        parts.append(
            f'<g data-node="{escape(str(node["id"]), quote=True)}">{title}{shape}{words}</g>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _outgoing(model: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for flow in model["flows"]:
        out.setdefault(flow["source"], []).append(flow)
    return out


def steps(model: dict[str, Any]) -> list[dict[str, Any]]:
    """The process as numbered steps (tasks and decisions, in document order), each with where it goes next.

    ``after`` is the text that follows the step's name (`` End.``, `` Go to step 4.``) and ``branches`` the lines
    beneath it, so the Markdown can be written with any name or lane put in.
    """
    kinds = {n["id"]: n["kind"] for n in model["nodes"]}
    numbered = [n for n in model["nodes"] if n["kind"] not in ("start", "end")]
    number = {n["id"]: i for i, n in enumerate(numbered, start=1)}
    out = _outgoing(model)

    def where(target: str) -> str:
        return "end" if kinds.get(target) == "end" else f"go to step {number.get(target, '?')}"

    result = []
    for n in numbered:
        i = number[n["id"]]
        flows = out.get(n["id"], [])
        after, branches = "", []
        if n["kind"] == "decision" or len(flows) > 1:
            branches = [f"   - {f.get('label') or 'Then'}: {where(f['target'])}" for f in flows]
        elif flows:
            target = flows[0]["target"]
            if kinds.get(target) == "end":
                after = " End."
            elif number.get(target) != i + 1:
                after = f" Go to step {number.get(target, '?')}."
        result.append(
            {
                "number": i,
                "id": n["id"],
                "kind": n["kind"],
                "name": n["name"],
                "lane": n["lane"],
                "after": after,
                "branches": branches,
                "next": [f["target"] for f in flows],
                "labels": [f.get("label") or "" for f in flows],
            }
        )
    return result


def sentence(name: str, after: str) -> str:
    """A step's name and what follows it (`` End.``): a full stop between them unless the name has one."""
    return name + ("." if after and name[-1:] not in ".?!" else "") + after


def to_markdown(model: dict[str, Any]) -> str:
    """The process in the Markdown format ``dev bpmn`` reads: reading it back gives the same steps and links."""
    lines = [f"# {model['name']}", ""]
    for step in steps(model):
        lines.append(f"{step['number']}. {step['lane']}: {sentence(step['name'], step['after'])}")
        lines += step["branches"]
    return "\n".join(lines) + "\n"


def paths(model: dict[str, Any], limit: int = MAX_PATHS) -> list[list[str]]:
    """Every way from the start to an end (at most ``limit``), as node ids. A route that goes back to a step it has
    already passed is listed once and ends there, so a loop shows without repeating forever."""
    out = _outgoing(model)
    kinds = {n["id"]: n["kind"] for n in model["nodes"]}
    found: list[list[str]] = []
    stack = [[n["id"]] for n in model["nodes"] if n["kind"] == "start"]
    while stack and len(found) < limit:
        route = stack.pop()
        here = route[-1]
        if kinds.get(here) == "end":
            found.append(route)
            continue
        for flow in reversed(out.get(here, [])):
            if flow["target"] in route:  # a loop: list it once, ending where it goes back to
                found.append([*route, flow["target"]])
            else:
                stack.append([*route, flow["target"]])
    return found


def viewer(model: dict[str, Any], bpmn: str) -> str:
    """One offline page: the diagram, what doesn't hold together, each step with its source, and the BPMN to save."""
    rows = "".join(
        f"<tr><td>{escape(str(n['name']))}</td><td>{escape(str(n['kind']))}</td><td>{escape(str(n['lane']))}</td><td><code>{escape(str(n.get('evidence') or ''))}</code></td></tr>"
        for n in model["nodes"]
    )
    problems = "".join(f"<li>{escape(str(p))}</li>" for p in model.get("problems", []))
    warning = (
        f'<section class="warn" id="problems"><h2>This process doesn\'t hold together</h2><ul>{problems}</ul></section>'
        if problems
        else ""
    )
    encoded = escape(bpmn)
    name = escape(str(model["name"]))
    names = {n["id"]: str(n["name"]) for n in model["nodes"]}
    all_routes = paths(model)
    routes = "".join(
        "<li>"
        + " → ".join(escape(names.get(i, i)) for i in route)
        + (" (and round again)" if route[-1] in route[:-1] else "")
        + "</li>"
        for route in all_routes
    )
    more_routes = (
        f'<p class="muted">Only the first {MAX_PATHS} are listed.</p>'
        if len(all_routes) >= MAX_PATHS
        else ""
    )
    numbered = steps(model)
    edit_rows = "".join(
        f'<tr><td>{s["number"]}</td><td><input id="lane-{s["number"]}" aria-label="Lane of step {s["number"]}" value="{escape(str(s["lane"]), quote=True)}"></td>'
        f'<td><input id="name-{s["number"]}" aria-label="Step {s["number"]}" value="{escape(str(s["name"]), quote=True)}"></td></tr>'
        for s in numbered
    )
    out = _outgoing(model)
    data = (
        json.dumps(
            {
                "name": str(model["name"]),
                "start": next((n["id"] for n in model["nodes"] if n["kind"] == "start"), None),
                "names": names,
                "lanes": {n["id"]: str(n["lane"]) for n in model["nodes"]},
                "kinds": {n["id"]: n["kind"] for n in model["nodes"]},
                "next": {k: [f["target"] for f in v] for k, v in out.items()},
                "labels": {k: [f.get("label") or "" for f in v] for k, v in out.items()},
                "steps": [
                    {k: s[k] for k in ("number", "name", "lane", "after", "branches")}
                    for s in numbered
                ],
            },
            ensure_ascii=True,
        )
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'">
<title>{name}</title><style>body{{font:15px/1.5 system-ui,sans-serif;margin:0;padding:20px;color:#2a2118;background:#fffdf9}}h1{{margin:0 0 4px}}.muted{{color:#6b5a48}}
.frame{{overflow:auto;border:1px solid #ddd5c8;border-radius:10px;margin:16px 0;background:#fff}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #eee6da;overflow-wrap:anywhere}}
.warn{{border:1px solid #c98a1b;background:#fff7e6;border-radius:10px;padding:4px 16px}}button{{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid #7a6a58;background:#fff;cursor:pointer}}pre{{overflow:auto;max-height:320px;background:#f7f3ec;padding:10px;border-radius:8px}}
input{{font:inherit;width:100%;box-sizing:border-box;padding:4px 6px;border:1px solid #c9c2b6;border-radius:6px}}#diagram .on rect,#diagram .on circle,#diagram .on polygon{{stroke:#d9480f;stroke-width:4}}
button:disabled{{opacity:.55;cursor:default}}</style></head>
<body><h1>{name}</h1><p class="muted">Read from {escape(str(model.get("source") or "a process file"))}. It's a description to review, and nothing runs it.</p>{warning}
<div class="frame" id="diagram">{render(model)}</div>
<p><button id="save" type="button">Save the BPMN</button> <span class="muted">Opens in tools like Camunda Modeler. Check an edited copy with <code>ananke process check</code>.</span></p>
<h2>Walk through it</h2><p class="muted">Step through the process from the start. At a decision, choose a way.</p>
<p><button id="sim-step" type="button">Start</button> <button id="sim-reset" type="button">Reset</button> <span id="sim-choices"></span></p>
<ol id="sim-log" aria-live="polite"></ol>
<h2>Every way through</h2><ol id="routes">{routes}</ol>{more_routes}
<h2>Steps</h2><table id="steps"><thead><tr><th>Step</th><th>Kind</th><th>Lane</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Change it</h2><p class="muted">Rename a step or move it to another lane, then download the Markdown and run <code>dev bpmn</code> on it. Ananke reads it again, so a change can't skip its checks.</p>
<table id="edit"><thead><tr><th>#</th><th>Lane</th><th>Step</th></tr></thead><tbody>{edit_rows}</tbody></table>
<p><button id="save-md" type="button">Download the Markdown</button></p>
<details><summary>BPMN</summary><pre id="bpmn">{encoded}</pre></details>
<script type="application/json" id="process-data">{data}</script>
<script>(function(){{
function dl(text,type,name){{var a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{{type:type}}));a.download=name;a.click();URL.revokeObjectURL(a.href);}}
document.getElementById("save").addEventListener("click",function(){{dl(document.getElementById("bpmn").textContent,"application/xml","process.bpmn");}});
var D=JSON.parse(document.getElementById("process-data").textContent);
document.getElementById("save-md").addEventListener("click",function(){{
var lines=["# "+D.name,""];D.steps.forEach(function(s){{var lane=document.getElementById("lane-"+s.number).value.trim()||s.lane;var name=document.getElementById("name-"+s.number).value.trim()||s.name;
lines.push(s.number+". "+lane+": "+name+(s.after&&!/[.?!]$/.test(name)?".":"")+s.after);s.branches.forEach(function(b){{lines.push(b);}});}});dl(lines.join("\\n")+"\\n","text/markdown","process.md");}});
var node=null,log=document.getElementById("sim-log"),choices=document.getElementById("sim-choices"),btn=document.getElementById("sim-step");
function mark(id){{document.querySelectorAll("#diagram [data-node]").forEach(function(g){{g.classList.toggle("on",g.getAttribute("data-node")===id);}});}}
function go(id){{node=id;mark(id);var li=document.createElement("li");li.textContent=D.names[id]+" ("+D.lanes[id]+")";log.appendChild(li);choices.textContent="";
var nx=D.next[id]||[];if(!nx.length){{btn.disabled=true;btn.textContent=D.kinds[id]==="end"?"Done":"Stuck here";return;}}
if(nx.length===1){{btn.disabled=false;btn.textContent="Next";return;}}
btn.disabled=true;nx.forEach(function(t,i){{var b=document.createElement("button");b.type="button";b.textContent=(D.labels[id][i]||"Then")+" → "+D.names[t];b.addEventListener("click",function(){{go(t);}});choices.appendChild(b);choices.appendChild(document.createTextNode(" "));}});}}
btn.addEventListener("click",function(){{if(node===null){{go(D.start);}}else if((D.next[node]||[]).length===1){{go(D.next[node][0]);}}}});
document.getElementById("sim-reset").addEventListener("click",function(){{node=null;log.textContent="";choices.textContent="";btn.disabled=!D.start;btn.textContent="Start";mark(null);}});
if(!D.start){{btn.disabled=true;}}
}})();</script></body></html>
"""


__all__ = ["paths", "render", "sentence", "steps", "to_markdown", "viewer"]
