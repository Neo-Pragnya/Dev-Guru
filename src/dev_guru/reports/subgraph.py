"""A bounded, expandable piece of the code graph, exported as Mermaid or SVG (``dev graph``).

It reads the explorer view model, so it shows only what Ananke found. You choose a level (package, file or
symbol), a focus, how many steps out to go (``depth``) and how many nodes to draw at most (``budget``). Nodes with
neighbours that weren't drawn say how many (``+3``), and the export names the command that shows them, so a
diagram can be expanded one step at a time instead of drawing the whole graph at once.

Inferred edges (calls found through imports) stay marked as inferred. Output is sorted, so the same model and
options always give the same text.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

SCHEMA = "dev-guru/subgraph@1"
LEVELS = ("package", "file", "symbol")
FORMATS = ("mermaid", "svg", "json")
DEFAULT_BUDGET = 40
KIND_ORDER = ("imports", "inherits", "calls")
MAX_BUDGET = 400


class SubgraphError(ValueError):
    pass


def _universe(
    model: dict[str, Any], level: str
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Nodes and edges at one level. Edges between the same two nodes are merged and counted."""
    files = {f["id"]: f for f in model.get("files", [])}
    symbols = {s["id"]: s for s in model.get("symbols", [])}
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    def add(s: str, t: str, kind: str, origin: str, file: str, line: int) -> None:
        if s == t:
            return
        edge = merged.setdefault(
            (s, t),
            {
                "s": s,
                "t": t,
                "k": kind,
                "kinds": {},
                "count": 0,
                "origin": origin,
                "file": file,
                "line": line,
            },
        )
        edge["kinds"][kind] = edge["kinds"].get(kind, 0) + 1
        edge["count"] += 1
        edge["k"] = min(
            edge["kinds"], key=KIND_ORDER.index
        )  # the strongest relationship names the edge
        if origin == "extracted":  # one extracted occurrence is enough to call the edge extracted
            edge["origin"] = "extracted"

    def owner(node_id: str) -> str:
        if node_id in files:
            return node_id
        return str(symbols.get(node_id, {}).get("file", ""))

    if level == "symbol":
        nodes = {
            sid: {
                "id": sid,
                "label": s["name"],
                "kind": s["kind"],
                "path": files.get(s["file"], {}).get("path", ""),
            }
            for sid, s in symbols.items()
        }
        for e in model.get("edges", []):
            if e["k"] != "imports" and e["s"] in nodes and e["t"] in nodes:
                add(e["s"], e["t"], e["k"], e.get("o", ""), nodes[e["s"]]["path"], e.get("line", 0))
        return nodes, sorted(merged.values(), key=lambda e: (e["s"], e["t"]))

    def group(file_id: str) -> str:
        return file_id if level == "file" else "package:" + files[file_id]["package"]

    if level == "file":
        nodes = {
            fid: {"id": fid, "label": f["path"], "kind": "file", "path": f["path"]}
            for fid, f in files.items()
        }
    else:
        nodes = {}
        for f in files.values():
            pid = "package:" + f["package"]
            nodes.setdefault(
                pid, {"id": pid, "label": f["package"], "kind": "package", "path": f["package"]}
            )
    for e in model.get("edges", []):
        s, t = owner(e["s"]), owner(e["t"])
        if s in files and t in files:
            kind = "imports" if e["k"] == "imports" else "calls"
            add(group(s), group(t), kind, e.get("o", ""), files[s]["path"], e.get("line", 0))
    return nodes, sorted(merged.values(), key=lambda e: (e["s"], e["t"]))


def edge_label(edge: dict[str, Any]) -> str:
    """``imports``, ``imports · 3 calls``: each kind once, with how many times it occurs when more than once."""
    parts = []
    for kind in KIND_ORDER:
        n = edge["kinds"].get(kind, 0)
        if n:
            parts.append(kind if n == 1 else f"{n} {kind}" if kind == "calls" else f"{kind} x{n}")
    return " · ".join(parts)


def _resolve(focus: str, nodes: dict[str, dict[str, Any]]) -> str:
    if focus in nodes:
        return focus
    for prefix in ("file:", "package:"):
        if prefix + focus in nodes:
            return prefix + focus
    matches = sorted(
        nid
        for nid, n in nodes.items()
        if focus in (n["label"], n["path"]) or n["path"].endswith("/" + focus)
    )
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SubgraphError(f"nothing called {focus!r} at this level")
    shown = ", ".join(matches[:5]) + (" …" if len(matches) > 5 else "")
    raise SubgraphError(f"{focus!r} matches {len(matches)} nodes: {shown}. Use one of these ids")


def select(
    model: dict[str, Any],
    *,
    level: str = "file",
    focus: str | None = None,
    depth: int = 1,
    budget: int = DEFAULT_BUDGET,
) -> dict[str, Any]:
    """The subgraph within ``depth`` steps of ``focus`` (or the best-connected nodes), at most ``budget`` nodes."""
    if level not in LEVELS:
        raise SubgraphError(f"unknown level {level!r}; choose {', '.join(LEVELS)}")
    if not 1 <= budget <= MAX_BUDGET:
        raise SubgraphError(f"budget must be between 1 and {MAX_BUDGET}")
    if depth < 0:
        raise SubgraphError("depth can't be negative")
    nodes, edges = _universe(model, level)
    if not nodes:
        raise SubgraphError(f"the model has no {level} nodes")
    near: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        near[e["s"]].add(e["t"])
        near[e["t"]].add(e["s"])

    def rank(nid: str) -> tuple[int, str]:
        return (-len(near[nid]), nid)

    chosen: list[str] = []
    truncated = False
    centre = _resolve(focus, nodes) if focus else None
    if centre:
        chosen, frontier = [centre], [centre]
        for _ in range(depth):
            layer = sorted({m for n in frontier for m in near[n]} - set(chosen), key=rank)
            room = budget - len(chosen)
            if len(layer) > room:
                truncated = True
                layer = layer[:room]
            chosen += layer
            frontier = layer
            if not layer or truncated:
                break
    else:
        ordered = sorted(nodes, key=rank)
        chosen = ordered[:budget]
        truncated = len(ordered) > budget
    kept = set(chosen)
    out_nodes = []
    for nid in sorted(kept, key=lambda n: (n != centre, n)):
        hidden = len(near[nid] - kept)
        out_nodes.append({**nodes[nid], "hidden": hidden, "focus": nid == centre})
    out_edges = [e for e in edges if e["s"] in kept and e["t"] in kept]
    expand = None
    if any(n["hidden"] for n in out_nodes):
        target = centre or out_nodes[0]["id"]
        expand = (
            f"dev graph --level {level} --focus {target} --depth {depth + 1} --budget {min(MAX_BUDGET, budget * 2)}"
            if centre
            else f"dev graph --level {level} --focus {target} --depth 1"
        )
    return {
        "schema": SCHEMA,
        "project": model.get("project", {}).get("name", ""),
        "level": level,
        "focus": centre,
        "depth": depth,
        "budget": budget,
        "nodes": out_nodes,
        "edges": out_edges,
        "omitted": {"nodes": len(nodes) - len(kept), "truncated_by_budget": truncated},
        "expand": expand,
    }


_SAFE_LABEL = re.compile(r'["<>`|\[\]{}()#;]')


def _mermaid_label(text: str) -> str:
    """Mermaid reads a lot of punctuation as syntax; replace it so a name can never change the diagram."""
    return _SAFE_LABEL.sub(" ", text).strip()[:60] or "?"


def to_mermaid(sub: dict[str, Any]) -> str:
    ids = {n["id"]: f"n{i}" for i, n in enumerate(sub["nodes"])}
    lines = [
        f"%% {SCHEMA} · {sub['project']} · level {sub['level']}"
        + (f" · focus {sub['focus']} · depth {sub['depth']}" if sub["focus"] else "")
        + f" · {len(sub['nodes'])} of {len(sub['nodes']) + sub['omitted']['nodes']} nodes",
        "flowchart LR",
    ]
    for n in sub["nodes"]:
        label = _mermaid_label(n["label"]) + (f" +{n['hidden']}" if n["hidden"] else "")
        shape = f'(["{label}"])' if n["kind"] == "package" else f'["{label}"]'
        lines.append(f"  {ids[n['id']]}{shape}")
    for e in sub["edges"]:
        label = edge_label(e)
        arrow = "-.->" if e["origin"] == "inferred" else "-->"
        lines.append(f"  {ids[e['s']]} {arrow}|{label}| {ids[e['t']]}")
    if sub["focus"]:
        lines.append(f"  classDef focus stroke-width:3px\n  class {ids[sub['focus']]} focus")
    more = [ids[n["id"]] for n in sub["nodes"] if n["hidden"]]
    if more:
        lines.append(f"  classDef more stroke-dasharray:4 3\n  class {','.join(more)} more")
    if sub["expand"]:
        lines.append(f"%% +N: neighbours not drawn. Expand with: {sub['expand']}")
    return "\n".join(lines) + "\n"


def to_svg(sub: dict[str, Any], *, animate: bool = True) -> str:
    from dev_guru import diagram

    doc = {
        "source": sub["project"] or "the code graph",
        "entities": [
            {
                "id": n["id"],
                "label": n["label"].rsplit("/", 1)[-1]
                + (f" +{n['hidden']}" if n["hidden"] else ""),
                "citations": [],
            }
            for n in sub["nodes"]
        ],
        "relations": [
            {
                "from": e["s"],
                "to": e["t"],
                "label": edge_label(e),
                "citation": {"file": e["file"], "line": e["line"]},
                "status": "cited" if e["origin"] != "inferred" else "inferred",
            }
            for e in sub["edges"]
        ],
    }
    focus = f", around {sub['focus']}" if sub["focus"] else ""
    title = f"{sub['project']}: {sub['level']} graph{focus} ({len(sub['nodes'])} of {len(sub['nodes']) + sub['omitted']['nodes']} nodes)"
    return diagram.render(doc, animate=animate, title=title)


__all__ = [
    "FORMATS",
    "LEVELS",
    "SCHEMA",
    "SubgraphError",
    "edge_label",
    "select",
    "to_mermaid",
    "to_svg",
]
