"""A swimlane drawing and an offline viewer for a process Ananke read. Ananke decides what the process is."""

from __future__ import annotations

from html import escape
from typing import Any

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
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'">
<title>{name}</title><style>body{{font:15px/1.5 system-ui,sans-serif;margin:0;padding:20px;color:#2a2118;background:#fffdf9}}h1{{margin:0 0 4px}}.muted{{color:#6b5a48}}
.frame{{overflow:auto;border:1px solid #ddd5c8;border-radius:10px;margin:16px 0;background:#fff}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #eee6da;overflow-wrap:anywhere}}
.warn{{border:1px solid #c98a1b;background:#fff7e6;border-radius:10px;padding:4px 16px}}button{{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid #7a6a58;background:#fff;cursor:pointer}}pre{{overflow:auto;max-height:320px;background:#f7f3ec;padding:10px;border-radius:8px}}</style></head>
<body><h1>{name}</h1><p class="muted">Read from {escape(str(model.get("source") or "a process file"))}. It's a description to review, and nothing runs it.</p>{warning}
<div class="frame" id="diagram">{render(model)}</div>
<p><button id="save" type="button">Save the BPMN</button> <span class="muted">Opens in tools like Camunda Modeler. Check an edited copy with <code>ananke process check</code>.</span></p>
<h2>Steps</h2><table id="steps"><thead><tr><th>Step</th><th>Kind</th><th>Lane</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>
<details><summary>BPMN</summary><pre id="bpmn">{encoded}</pre></details>
<script>document.getElementById("save").addEventListener("click",function(){{var a=document.createElement("a");a.href=URL.createObjectURL(new Blob([document.getElementById("bpmn").textContent],{{type:"application/xml"}}));a.download="process.bpmn";a.click();URL.revokeObjectURL(a.href);}});</script></body></html>
"""


__all__ = ["render", "viewer"]
