"""Signs that a graph came out wrong, said at once rather than discovered in an empty picture.

Each check is one that has failed for real. On Windows, paths written with backslashes once left the constellation with
no links and the flow with one package, while the command reported success.
"""

from __future__ import annotations

from typing import Any

from dev_guru.client.port import GraphData

MANY = 20  # below this, a repository can honestly have no imports between its own files


def problems(graph: GraphData, model: dict[str, Any]) -> list[str]:
    found: list[str] = []
    files = [n for n in graph.nodes if n.kind == "file"]
    slashed = [n for n in graph.nodes if "\\" in (n.path or "") or "\\" in n.id]
    if slashed:
        found.append(
            f"{len(slashed)} of {len(graph.nodes)} paths are written with backslashes, so imports and folders can't "
            f"be matched (for example {slashed[0].id}). Ananke 0.3.28 or later writes them with forward slashes."
        )
    python = [f for f in files if str(f.path).endswith(".py")]
    resolved = sum(1 for e in graph.edges if e.kind == "imports" and e.resolved_target)
    if len(python) >= MANY and resolved == 0:
        found.append(
            f"No import between this repository's own {len(python)} Python files was found, so the constellation "
            "and flow will have no links. Run again with --logs FILE and share the file."
        )
    nested = [f for f in files if "/" in str(f.path) or "\\" in str(f.path)]
    if len(nested) >= MANY and len(model.get("packages", [])) <= 1:
        found.append(
            f"{len(nested)} files in folders all landed in one package, so the flow has nothing to lay out. "
            "Run again with --logs FILE and share the file."
        )
    return found


__all__ = ["problems"]
