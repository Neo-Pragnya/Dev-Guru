"""What the offline explorer shows of a repository analysis: every section, small enough to embed."""

from __future__ import annotations

from typing import Any

MAX_ROWS = 200
TOP = 10


def _rows(items: Any, limit: int = MAX_ROWS) -> list[Any]:
    return list(items)[:limit] if isinstance(items, list) else []


def build(report: dict[str, Any]) -> dict[str, Any]:
    """A view of ``repo-intel.json``. Each section keeps its status, so unknown stays apart from zero."""
    sections = report.get("sections", {})
    overview = sections.get("overview", {})
    data = sections.get("data", {})
    api = sections.get("api", {})
    flows = sections.get("flows", {})
    calm = sections.get("calm", {})
    quality = sections.get("quality", {})
    coverage = sections.get("coverage", {})
    deps = sections.get("dependencies", {})
    tests = sections.get("tests", {})
    routes = _rows(api.get("routes"))
    callers: dict[str, list[str]] = {}
    for client in _rows(api.get("clients"), 10_000):
        if client.get("route"):
            callers.setdefault(str(client["route"]), []).append(
                str(client.get("caller")).rsplit(":", 1)[-1]
            )
    tables = _rows(data.get("tables"))
    return {
        "files": overview.get("files"),
        "loc": overview.get("loc"),
        "languages": overview.get("languages") or {},
        "components": [
            [c.get("name"), c.get("kind"), c.get("language"), c.get("files")]
            for c in _rows(overview.get("components"))
        ],
        "links": [
            [r.get("source"), r.get("target"), r.get("type"), r.get("evidence")]
            for r in _rows((calm.get("model") or {}).get("relationships"))
        ],
        "routes": [
            [
                r.get("method"),
                r.get("path"),
                str(r.get("handler")).split(":", 1)[-1],
                ", ".join(callers.get(str(r.get("id")), [])),
            ]
            for r in routes
        ],
        "routes_total": len(api.get("routes") or []),
        "unmatched": [
            [c.get("method"), c.get("path"), c.get("evidence")]
            for c in _rows(api.get("unmatched_clients"))
        ],
        "tables": [
            [
                t.get("name"),
                ", ".join(str(c.get("name")) for c in _rows(t.get("columns"))),
            ]
            for t in tables
        ],
        "tables_total": len(data.get("tables") or []),
        "relationships": [
            [
                f"{r.get('from_table')}.{r.get('from_column')}",
                f"{r.get('to_table')}.{r.get('to_column')}",
            ]
            for r in _rows(data.get("relationships"))
        ],
        "flows": [f.get("name") for f in _rows(flows.get("flows"))],
        "flows_total": len(flows.get("flows") or []),
        "totals": quality.get("totals") or {},
        "hotspots": [
            [
                str(h.get("symbol")).rsplit(":", 1)[-1],
                h.get("complexity"),
                f"{h.get('path')}:{h.get('line')}",
            ]
            for h in _rows(quality.get("hotspots"), TOP)
        ],
        "coverage": {
            "status": coverage.get("status"),
            "line_rate": coverage.get("line_rate"),
            "files": len(coverage.get("files") or []),
        },
        "tests": {
            "status": tests.get("status"),
            "files": tests.get("files"),
            "tests": tests.get("tests"),
            "source_files": tests.get("source_files"),
            "imported_by_tests": tests.get("imported_by_tests"),
            "suites": [
                [
                    s.get("kind"),
                    s.get("framework"),
                    s.get("files"),
                    s.get("tests"),
                    s.get("exercises_count"),
                ]
                for s in _rows(tests.get("suites"))
            ],
            "untested_count": tests.get("untested_count"),
            "untested": _rows(tests.get("untested"), 20),
        },
        "dependencies": {
            "status": deps.get("status"),
            "packages": len(deps.get("packages") or []),
            # None means nobody has checked, which isn't the same as none found
            "vulnerabilities": None
            if deps.get("vulnerabilities") is None
            else [
                [
                    v.get("package"),
                    v.get("version"),
                    v.get("severity"),
                    v.get("id"),
                    v.get("fixed_in"),
                ]
                for v in _rows(deps.get("vulnerabilities"))
            ],
        },
    }


def public(view: dict[str, Any]) -> dict[str, Any]:
    """Counts alone: routes, tables and paths say more about a private system than its structure does."""
    return {
        "files": view.get("files"),
        "loc": view.get("loc"),
        "languages": view.get("languages"),
        "components": [],
        "links": [],
        "routes": [],
        "routes_total": view.get("routes_total"),
        "unmatched": [],
        "tables": [],
        "tables_total": view.get("tables_total"),
        "relationships": [],
        "flows": [],
        "flows_total": view.get("flows_total"),
        "totals": view.get("totals"),
        "hotspots": [],
        "coverage": {"status": (view.get("coverage") or {}).get("status")},
        "tests": {
            k: (view.get("tests") or {}).get(k)
            for k in ("status", "files", "tests", "source_files", "imported_by_tests")
        },
        "dependencies": {"status": "not_shown", "packages": None, "vulnerabilities": None},
        "reduced": True,
    }


__all__ = ["build", "public"]
