"""``dev diagram``: an animated SVG of the relationships an approved document states, each one cited.

Extraction is deterministic and reads only explicit statements, so text in a document can't talk it into
inventing a relationship (no model is involved):

* arrow lines: ``API -> Queue: enqueues jobs``, ``Worker --> Store``, ``A → B``;
* Mermaid flowcharts: ``A[API] -->|calls| B[Queue]``;
* Markdown tables with ``From`` and ``To`` columns (and an optional ``Relation`` column).

Every relationship carries a citation (file, line, quote). The model can be edited and re-rendered; an edited
relationship whose citation doesn't hold up (the cited line must exist and name both ends) is drawn as a
*hypothesis* (dashed, with a "?"), never as a fact. The SVG has no scripts, event handlers or external references,
and its animation stops under reduced motion or with ``--static``.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from typing import Any

MODEL_SCHEMA = "dev-guru/doc-graph@1"
_ARROW = re.compile(
    r"^\s*[-*]?\s*`?([A-Za-z0-9][\w .()/&+-]{0,60}?)`?\s*(?:-->|->|→|=>)\s*`?([A-Za-z0-9][\w .()/&+-]{0,60}?)`?\s*(?::\s*(.{1,80}))?\s*$"
)
_MERMAID_NODE = r"([A-Za-z0-9_]+)(?:\[([^\]]{1,60})\]|\(([^)]{1,60})\))?"
# Mermaid edges: A --> B, A -->|label| B and A --- B
_MERMAID_EDGE = re.compile(
    _MERMAID_NODE + r"\s*-{2,3}>?\s*(?:\|([^|]{1,60})\|)?\s*" + _MERMAID_NODE
)


class DiagramError(ValueError):
    pass


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    label: str
    line: int
    quote: str


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "node"


def extract(text: str, file: str) -> dict[str, Any]:
    """The cited relationships ``text`` states explicitly, as an editable model."""
    rels: list[Relation] = []
    lines = text.splitlines()
    fence = ""
    header: list[str] | None = None
    for no, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            fence = "" if fence else (stripped[3:].strip() or "code")
            continue
        if fence == "mermaid":
            aliases: dict[str, str] = {}
            for m in _MERMAID_EDGE.finditer(stripped):
                a, a1, a2, label, b, b1, b2 = m.groups()
                aliases.setdefault(a, (a1 or a2 or a).strip())
                aliases.setdefault(b, (b1 or b2 or b).strip())
                rels.append(Relation(aliases[a], aliases[b], (label or "").strip(), no, stripped))
            continue
        if fence:
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if header is None:
                low = [c.lower() for c in cells]
                header = low if "from" in low and "to" in low else []
            elif header and not all(set(c) <= set("-: ") for c in cells):
                row = dict(zip(header, cells, strict=False))
                if row.get("from") and row.get("to"):
                    rels.append(
                        Relation(
                            row["from"],
                            row["to"],
                            row.get("relation") or row.get("relationship") or "",
                            no,
                            stripped,
                        )
                    )
            continue
        header = None
        arrow = _ARROW.match(line)
        if arrow:
            rels.append(
                Relation(
                    arrow.group(1).strip(),
                    arrow.group(2).strip(),
                    (arrow.group(3) or "").strip(),
                    no,
                    stripped,
                )
            )
    if not rels:
        raise DiagramError(
            f"{file}: no explicit relationships found. Write them as 'A -> B: label', a Mermaid flowchart, or a table with From and To columns"
        )
    entities: dict[str, dict[str, Any]] = {}
    for r in rels:
        for label in (r.source, r.target):
            e = entities.setdefault(
                _slug(label), {"id": _slug(label), "label": label, "citations": []}
            )
            if r.line not in e["citations"]:
                e["citations"].append(r.line)
    relations = []
    seen = set()
    for r in rels:
        key = (_slug(r.source), _slug(r.target), r.label)
        if key in seen:
            continue
        seen.add(key)
        relations.append(
            {
                "from": key[0],
                "to": key[1],
                "label": r.label,
                "citation": {"file": file, "line": r.line, "quote": r.quote},
                "status": "cited",
            }
        )
    return {
        "schema": MODEL_SCHEMA,
        "source": file,
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "entities": sorted(entities.values(), key=lambda e: e["id"]),
        "relations": relations,
    }


def verify(model: dict[str, Any], text: str) -> dict[str, Any]:
    """Re-check an (edited) model against its document: a relation is cited only if its cited line holds up."""
    if model.get("schema") != MODEL_SCHEMA:
        raise DiagramError(f"not a document graph model (schema {model.get('schema')!r})")
    ids = {e["id"]: e["label"] for e in model.get("entities", [])}
    lines = text.splitlines()
    out = []
    for r in model.get("relations", []):
        if r.get("from") not in ids or r.get("to") not in ids:
            raise DiagramError(
                f"relation {r.get('from')} → {r.get('to')} names an entity that isn't in the model"
            )
        c = r.get("citation") or {}
        line_no = c.get("line")
        ok = isinstance(line_no, int) and 1 <= line_no <= len(lines)
        if ok and isinstance(line_no, int):
            cited = lines[line_no - 1].lower()
            ok = ids[r["from"]].lower() in cited and ids[r["to"]].lower() in cited
        out.append({**r, "status": "cited" if ok else "hypothesis"})
    return {**model, "relations": out}


def _layers(model: dict[str, Any]) -> dict[str, int]:
    ids = [e["id"] for e in model["entities"]]
    out: dict[str, set[str]] = {i: set() for i in ids}
    for r in model["relations"]:
        if r["from"] != r["to"]:
            out[r["from"]].add(r["to"])
    depth = dict.fromkeys(ids, 0)
    for _ in range(len(ids)):  # longest-path layering; cycles stop growing after len(ids) passes
        changed = False
        for a in ids:
            for b in out[a]:
                if depth[b] < depth[a] + 1 and depth[a] + 1 < len(ids):
                    depth[b] = depth[a] + 1
                    changed = True
        if not changed:
            break
    return depth


def render(model: dict[str, Any], *, animate: bool = True, title: str = "") -> str:
    """A self-contained SVG. Deterministic: the same model gives the same bytes."""
    depth = _layers(model)
    cols: dict[int, list[str]] = {}
    for e in model["entities"]:
        cols.setdefault(depth[e["id"]], []).append(e["id"])
    nw, nh, gx, gy, pad = 180, 48, 110, 34, 32
    pos = {}
    # order each column by the mean position of its neighbours, which removes most crossings
    rank = {nid: i for members in cols.values() for i, nid in enumerate(members)}
    neighbours: dict[str, list[str]] = {}
    for r in model["relations"]:
        neighbours.setdefault(r["from"], []).append(r["to"])
        neighbours.setdefault(r["to"], []).append(r["from"])
    for _ in range(4):
        for members in cols.values():
            members.sort(
                key=lambda n: (
                    sum(rank[m] for m in neighbours.get(n, []))
                    / max(1, len(neighbours.get(n, []))),
                    n,
                )
            )
            rank.update({nid: i for i, nid in enumerate(members)})
    tallest = max(len(v) for v in cols.values())
    for c, members in sorted(cols.items()):
        offset = (tallest - len(members)) * (nh + gy) / 2
        for i, nid in enumerate(members):
            pos[nid] = (pad + c * (nw + gx), pad + 28 + offset + i * (nh + gy))
    width = pad * 2 + (max(cols) + 1) * nw + max(cols) * gx
    height = pad * 2 + 28 + tallest * nh + (tallest - 1) * gy
    labels = {e["id"]: e["label"] for e in model["entities"]}
    edges, nodes = [], []
    # labels never sit on a node or on another label: move down until the spot is free
    taken: list[tuple[float, float, float, float]] = [
        (x, y, x + nw, y + nh) for x, y in pos.values()
    ]

    def place(cx: float, cy: float, text: str) -> float:
        half = len(text) * 3.4 + 4
        y = cy
        for _ in range(40):
            box = (cx - half, y - 12, cx + half, y + 4)
            if not any(
                box[0] < t[2] and box[2] > t[0] and box[1] < t[3] and box[3] > t[1] for t in taken
            ):
                break
            y += 15
        taken.append((cx - half, y - 12, cx + half, y + 4))
        return y

    for k, r in enumerate(model["relations"]):
        (x1, y1), (x2, y2) = pos[r["from"]], pos[r["to"]]
        a = (x1 + nw, y1 + nh / 2) if x2 > x1 else (x1 + nw / 2, y1 + nh)
        b = (x2, y2 + nh / 2) if x2 > x1 else (x2 + nw / 2, y2)
        mx = (a[0] + b[0]) / 2
        d = f"M{a[0]:.1f},{a[1]:.1f} C{mx:.1f},{a[1]:.1f} {mx:.1f},{b[1]:.1f} {b[0]:.1f},{b[1]:.1f}"
        hyp = r.get("status") != "cited"
        inferred = r.get("status") == "inferred"  # code graphs: found through imports, not stated
        label_text = r["label"] + (" ?" if hyp and not inferred else "")
        cite = r.get("citation") or {}
        tip = (
            f"{labels[r['from']]} → {labels[r['to']]}"
            + (f": {r['label']}" if r["label"] else "")
            + (
                f" — {cite.get('file')}:{cite.get('line')}"
                if not hyp
                else f" — inferred through imports, {cite.get('file')}:{cite.get('line')}"
                if inferred
                else " — hypothesis: no citation holds up"
            )
        )
        edges.append(
            f'<g class="edge{" hyp" if hyp else ""}"><title>{html.escape(tip)}</title>'
            f'<path d="{d}" marker-end="url(#arrow)" style="--k:{k}"/>'
            + (
                f'<text x="{mx:.1f}" y="{place(mx, (a[1] + b[1]) / 2 - 6, label_text):.1f}">{html.escape(label_text)}</text>'
                if label_text
                else ""
            )
            + "</g>"
        )
    for e in model["entities"]:
        x, y = pos[e["id"]]
        lines = ", ".join(str(n) for n in e.get("citations", [])[:4])
        tip = e["label"] + (f" (lines {lines})" if lines else "")
        nodes.append(
            f'<g class="node"><title>{html.escape(tip)}</title>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{nw}" height="{nh}" rx="12"/>'
            f'<text x="{x + nw / 2:.1f}" y="{y + nh / 2 + 5:.1f}">{html.escape(e["label"][:24])}</text></g>'
        )
    # a label moved down to stay clear of the others can end below the last node: make room for it
    height = max(height, max(box[3] for box in taken) + pad)
    anim = (
        ".edge path{stroke-dasharray:6 8;animation:flow 1.6s linear infinite;animation-delay:calc(var(--k)*-.2s)}"
        "@keyframes flow{to{stroke-dashoffset:-28}}"
        "@media (prefers-reduced-motion:reduce){.edge path{animation:none;stroke-dasharray:none}}"
        if animate
        else ""
    )
    heading = html.escape(title or f"Relationships stated in {model['source']}")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-labelledby="t d" font-family="Inter, system-ui, sans-serif">'
        f'<title id="t">{heading}</title><desc id="d">{len(model["relations"])} relationships between {len(model["entities"])} entities; '
        f"{sum(1 for r in model['relations'] if r.get('status') == 'hypothesis')} marked as hypotheses, "
        f"{sum(1 for r in model['relations'] if r.get('status') == 'inferred')} inferred.</desc>"
        "<style>"
        ".node rect{fill:#15172f;stroke:#ffb347;stroke-width:1.5}.node text{fill:#efedf9;font-size:14px;text-anchor:middle}"
        ".edge path{fill:none;stroke:#3dd6c6;stroke-width:2}.edge text{fill:#c9cbe6;font-size:12px;text-anchor:middle;paint-order:stroke;stroke:#0d0e1c;stroke-width:4px}"
        ".edge.hyp path{stroke:#a4a6c9;stroke-dasharray:3 5;animation:none}.heading{fill:#a4a6c9;font-size:13px}"
        f"{anim}</style>"
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#3dd6c6"/></marker></defs>'
        f'<rect width="100%" height="100%" fill="#0d0e1c"/><text class="heading" x="{pad}" y="{pad}">{heading}</text>'
        + "".join(edges)
        + "".join(nodes)
        + "</svg>\n"
    )


def svg_problems(svg: str) -> list[str]:
    """Why an SVG isn't safe to embed (empty when it is)."""
    problems = []
    if re.search(r"<script|<foreignObject", svg, re.I):
        problems.append("contains a script or foreignObject")
    tags = re.findall(r"<[^>]*>", svg)  # attributes live inside tags; escaped text can't open one
    if any(re.search(r"\son[a-z]+\s*=", t, re.I) for t in tags):
        problems.append("contains an event handler attribute")
    if any(re.search(r"(?:href|src)\s*=\s*[\"'](?!#)", t, re.I) for t in tags) or "url(http" in svg:
        problems.append("references an external resource")
    return problems


__all__ = ["MODEL_SCHEMA", "DiagramError", "extract", "render", "svg_problems", "verify"]
