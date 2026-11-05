"""A recording of what the web interface asks for, so the one offline file can show the same pages.

The pages in ``gateway/static`` are the product. A report carries them with this recording behind them, so the file and
``dev serve`` can't drift apart. Nothing here reaches a network, and it's left out of a public report.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from dev_guru import errors
from dev_guru.client import AnankeClient

MAX_DEPTH = 4
MAX_SYMBOLS = 20_000
MAX_VIEW_BYTES = 12_000_000
MAX_SOURCE_BYTES = 20_000_000
MAX_RUNS = 12
_EVIDENCE = re.compile(r"^([^\s:#]+(?: [^\s:#]+)*?)(?:#cell=\d+)?:\d+(?:-\d+)?$")


def _evidence_paths(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _evidence_paths(item, found)
    elif isinstance(value, list):
        for item in value:
            _evidence_paths(item, found)
    elif isinstance(value, str) and len(value) < 500 and (match := _EVIDENCE.match(value)):
        found.add(match[1])


def _sized(value: Any) -> int:
    return len(json.dumps(value))


def build(
    client: AnankeClient,
    root: Path,
    report: dict[str, Any],
    files: list[str],
    name: str,
    version: str,
) -> dict[str, Any]:
    info = client.info()
    context: dict[str, Any] = {}
    try:
        context = {**client.context_map(root, budget=1500), **client.context_status(root)}
    except (errors.GuruError, OSError, ValueError):
        context = {}
    code: dict[str, Any] = {}
    spent = 0

    def view(collapse: str, depth: int, path: str = "", budget: int = 2000) -> None:
        nonlocal spent
        if spent > MAX_VIEW_BYTES:
            return
        try:
            found = client.code_view(
                root,
                path_prefix=path,
                query="",
                kinds=[],
                budget=budget,
                collapse=collapse,
                depth=depth,
            )
        except (errors.GuruError, OSError, ValueError):
            return
        spent += _sized(found)
        code[f"{collapse}|{depth if collapse == 'directory' else 0}|{path}"] = found

    for depth in range(1, MAX_DEPTH + 1):
        view("directory", depth)
    view("file", 1)
    view("none", 1, budget=MAX_SYMBOLS)  # a page wanting one file narrows this, in static_host.js

    wanted: set[str] = set(files)
    _evidence_paths(report, wanted)
    sources: dict[str, list[str]] = {}
    spent_source = 0
    for path in sorted(wanted):
        if spent_source > MAX_SOURCE_BYTES:
            break
        try:
            lines = client.read_source(root, path, 1, None).get("lines", [])
        except (errors.GuruError, OSError, ValueError):
            continue
        spent_source += sum(len(line) for line in lines)
        sources[path] = list(lines)

    history = client.run_history(root)
    rows = history.get("runs", [])[:MAX_RUNS]
    details = {}
    for run in rows:
        run_id = run["run_id"]
        try:
            details[run_id] = {
                "run": client.get_run(root, run_id),
                "events": client.run_events(root, run_id, 0),
                "artifacts": {"artifacts": client.run_artifacts(root, run_id)},
            }
        except (errors.GuruError, OSError, ValueError):
            continue
    try:
        capabilities = client.harness_capabilities(root)
    except (errors.GuruError, OSError, ValueError):
        capabilities = {"run_kinds": []}
    try:
        offered = [c.model_dump() for c in client.discover_capabilities(root, "")][:500]
    except (errors.GuruError, OSError, ValueError):
        offered = []
    from dev_guru.gateway import documents

    learning: dict[str, Any] = {}
    try:
        for candidate in client.learning_candidates(root)[:50]:
            learning[candidate] = client.learning_candidate(root, candidate).model_dump()
    except (errors.GuruError, OSError, ValueError):
        learning = {}
    return {
        "learning": learning,
        "documents": documents.listed(root),
        "workspace": {"id": "report", "name": name, "path": ""},
        "health": {"ok": info.compatible, "gateway": version, "harness": info.model_dump()},
        "capabilities": capabilities,
        "sources": {"capabilities": offered},
        "runs": {"runs": rows, "total": history.get("total", len(rows))},
        "details": details,
        "intel": report,
        "context": context,
        "code": code,
        "source_text": sources,
    }


__all__ = ["build"]
