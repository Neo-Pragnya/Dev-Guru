"""The explorer view model (``dev-guru/explorer@1``): a bounded projection of an Ananke graph for presentation.

Everything structural comes from Ananke: files, symbols, imports, calls, bases and their metadata. Dev Guru only
regroups and counts what Ananke found (packages, fan-in, the most-depended-on files, import cycles over the given
edges), adds source snippets for display, and states what the report doesn't cover. Output is sorted and
deterministic, so the same graph always gives the same model.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from dev_guru.client.port import GraphData

SCHEMA = "dev-guru/explorer@1"
MAX_SNIPPET_LINES = 60
MAX_SYMBOLS = 6000
ENTRY_NAMES = {"__main__.py", "main.py", "cli.py", "app.py", "manage.py", "wsgi.py", "asgi.py"}
SYMBOL_KINDS = ("class", "function", "method")


def _module_name(path: str) -> str:
    parts = path.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _package(path: str) -> str:
    parent = path.rsplit("/", 1)[0] if "/" in path else "."
    return parent


def _snippet(root: Path, path: str, line: int, end_line: int) -> str:
    if not line:
        return ""
    try:
        lines = (root / path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    end = min(max(end_line, line), line + MAX_SNIPPET_LINES - 1, len(lines))
    return "\n".join(lines[line - 1 : end])


def _cycles(adjacency: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components with more than one file (Tarjan, iterative, deterministic)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    out: list[list[str]] = []
    counter = 0
    for start in sorted(adjacency):
        if start in index:
            continue
        work: list[tuple[str, list[str]]] = [(start, sorted(adjacency.get(start, ())))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, children = work[-1]
            if children:
                child = children.pop(0)
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, sorted(adjacency.get(child, ()))))
                elif child in on_stack:
                    low[node] = min(low[node], index[child])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    comp = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        comp.append(member)
                        if member == node:
                            break
                    if len(comp) > 1:
                        out.append(sorted(comp))
    return sorted(out)


def build(graph: GraphData, workspace: Path, *, project_name: str | None = None) -> dict[str, Any]:
    root = workspace.expanduser().resolve()
    files_raw = sorted((n for n in graph.nodes if n.kind == "file"), key=lambda n: n.path)
    symbols_raw = sorted((n for n in graph.nodes if n.kind in SYMBOL_KINDS), key=lambda n: n.id)
    omitted_symbols = max(0, len(symbols_raw) - MAX_SYMBOLS)
    symbols_raw = symbols_raw[:MAX_SYMBOLS]
    known_symbols = {s.id for s in symbols_raw}

    file_ids = {f.id for f in files_raw}
    module_to_file: dict[str, str] = {}
    for f in files_raw:
        module = str(
            f.metadata.get("module") or _module_name(f.path)
        )  # older Ananke has no "module"
        if module:
            module_to_file[module] = f.id
            if module.startswith("src."):
                module_to_file.setdefault(module.removeprefix("src."), f.id)

    imports: set[tuple[str, str]] = set()
    external: dict[str, set[str]] = defaultdict(set)
    sym_edges: list[dict[str, Any]] = []
    owner: dict[str, str] = {}
    for e in graph.edges:
        if e.kind == "owns":
            owner[e.target] = e.source
        elif e.kind == "imports" and e.source.startswith("file:"):
            module = e.target.removeprefix("module:")
            # Ananke resolves imports across folders; the module-name lookup covers only what it left unresolved
            resolved = str(getattr(e, "resolved_target", "") or "")
            target = resolved if resolved in file_ids else module_to_file.get(module)
            if target is None:  # `from pkg import mod` resolves to pkg.mod when that file exists
                parts = module.split(".")
                for cut in range(len(parts), 0, -1):
                    candidate = module_to_file.get(".".join(parts[:cut]))
                    if candidate:
                        target = candidate
                        break
            if target and target != e.source:
                imports.add((e.source, target))
            elif target is None:
                external[module.split(".")[0]].add(e.source)
        elif (
            e.kind in ("calls", "inherits")
            and e.source in known_symbols
            and e.target in known_symbols
        ):
            at = e.location.rsplit(":", 1)[-1] if e.location else ""
            sym_edges.append(
                {
                    "s": e.source,
                    "t": e.target,
                    "k": e.kind,
                    "o": e.origin,
                    "line": int(at) if at.isdigit() else 0,
                }
            )

    def file_of(symbol_id: str) -> str:
        cur = symbol_id
        while cur in owner and not cur.startswith("file:"):
            cur = owner[cur]
        return cur if cur.startswith("file:") else ""

    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for importer, imported in imports:
        fan_out[importer] += 1
        fan_in[imported] += 1
        adjacency[importer].add(imported)
    calls_in: dict[str, int] = defaultdict(int)
    calls_out: dict[str, int] = defaultdict(int)
    for sym_edge in sym_edges:
        if sym_edge["k"] == "calls":
            calls_out[sym_edge["s"]] += 1
            calls_in[sym_edge["t"]] += 1

    by_file: dict[str, list[str]] = defaultdict(list)
    symbols: list[dict[str, Any]] = []
    for sym in symbols_raw:
        meta = sym.metadata
        line, end = int(str(meta.get("line") or 0)), int(str(meta.get("end_line") or 0))
        fid = file_of(sym.id)
        by_file[fid].append(sym.id)
        symbols.append(
            {
                "id": sym.id,
                "kind": sym.kind,
                "name": sym.name,
                "file": fid,
                "line": line,
                "end_line": end,
                "signature": str(meta.get("signature") or ""),
                "doc": str(meta.get("doc") or ""),
                "source": _snippet(root, sym.path, line, end),
                "calls_in": calls_in.get(sym.id, 0),
                "calls_out": calls_out.get(sym.id, 0),
            }
        )

    files: list[dict[str, Any]] = []
    packages: dict[str, list[str]] = defaultdict(list)
    for node in files_raw:
        pkg = _package(node.path)
        packages[pkg].append(node.id)
        files.append(
            {
                "id": node.id,
                "path": node.path,
                "name": node.name,
                "package": pkg,
                "module": str(node.metadata.get("module") or _module_name(node.path)),
                "loc": int(str(node.metadata.get("loc") or 0)),
                "doc": str(node.metadata.get("doc") or ""),
                "parse_error": bool(node.metadata.get("parse_error", False)),
                "symbols": sorted(by_file.get(node.id, [])),
                "fan_in": fan_in.get(node.id, 0),
                "fan_out": fan_out.get(node.id, 0),
                "external": sorted(m for m, users in external.items() if node.id in users),
                "entry": node.name in ENTRY_NAMES,
            }
        )

    ranked_in = sorted(files, key=lambda f: (-f["fan_in"], f["path"]))
    ranked_loc = sorted(files, key=lambda f: (-f["loc"], f["path"]))
    connected = {s for s, _ in imports} | {t for _, t in imports}
    limitations = [
        "Static analysis of Python source by Ananke's native graph provider; nothing was executed.",
        "Calls and base classes are inferred through each file's imports: dynamic dispatch, getattr and "
        "re-exports beyond one level are not followed.",
        "Imports of modules outside the workspace are listed as external dependencies, not analysed.",
    ]
    if omitted_symbols:
        limitations.append(f"{omitted_symbols} symbols were omitted to keep the report bounded.")
    parse_errors = [f["path"] for f in files if f["parse_error"]]
    if parse_errors:
        limitations.append(f"{len(parse_errors)} file(s) could not be parsed and show no symbols.")
    return {
        "schema": SCHEMA,
        "project": {
            "name": project_name or root.name,
            "files": len(files),
            "packages": len(packages),
            "symbols": len(symbols),
            "loc": sum(f["loc"] for f in files),
            "imports": len(imports),
            "calls": sum(1 for e in sym_edges if e["k"] == "calls"),
            "external": len(external),
        },
        "packages": [
            {"id": p, "name": p, "files": sorted(ids)} for p, ids in sorted(packages.items())
        ],
        "files": files,
        "symbols": symbols,
        "edges": [
            {"s": s, "t": t, "k": "imports", "o": "extracted", "line": 0}
            for s, t in sorted(imports)
        ]
        + sorted(sym_edges, key=lambda e: (e["s"], e["t"], e["k"])),
        "external": [
            {"name": m, "importers": sorted(users)} for m, users in sorted(external.items())
        ],
        "insights": {
            "most_depended": [f["id"] for f in ranked_in if f["fan_in"]][:8],
            "largest": [f["id"] for f in ranked_loc if f["loc"]][:8],
            "entry_points": [f["id"] for f in files if f["entry"]],
            "cycles": _cycles(adjacency),
            "isolated": [f["id"] for f in files if f["id"] not in connected],
        },
        "limitations": limitations,
        "omitted": {"symbols": omitted_symbols},
    }


__all__ = ["SCHEMA", "build"]
