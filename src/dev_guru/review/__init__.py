"""A review of a change, grounded in the code (``dev review``): what changed, what it reaches, what blocks it,
what to retest, and a draft pull request description.

Everything comes from Git, Ananke's code graph and repository analysis, and the reports already in the repository:

* **Changed:** files and lines from ``git diff`` against the base (committed and uncommitted), the symbols whose
  lines changed, and the commits.
* **Reach:** who calls the changed symbols, and the files that import a changed file, directly or not.
* **Blocking:** findings Ananke ranks *fix now* for this change (scanner findings in changed files, failing tests,
  low coverage on changed files, reachable critical vulnerabilities), and, with a spec, requirements whose code
  changed but that no test mentions.
* **Advisory:** findings ranked *fix soon*, complex functions that changed, changed files in an import cycle,
  requirements only possibly linked.
* **Retest:** the test files that exercise the change, and the gates whose reports the findings came from.

Nothing is run apart from read-only ``git`` commands, and nothing is judged by a model.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from dev_guru.explain import COMPLEX, Facts

SCHEMA = "dev-guru/review@1"
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_TEST = re.compile(
    r"(^|/)(tests?|spec|__tests__)/|(^|/)test_[^/]+\.py$|_test\.py$|\.(test|spec)\.[jt]sx?$"
)


class ReviewError(ValueError):
    pass


def _git(root: Path, *args: str) -> str:
    """A fixed git argv (no shell); git comes from PATH like any developer tool."""
    argv = ["git", "-C", str(root), *args]
    done = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)  # noqa: S603
    if done.returncode != 0:
        raise ReviewError(f"git {' '.join(args[:2])} failed: {done.stderr.strip()[:200]}")
    return done.stdout


def changes(root: Path, base: str) -> dict[str, Any]:
    """Changed files, their changed line ranges (new side), and the commits since ``base``."""
    try:
        _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    except ReviewError as exc:
        raise ReviewError(f"{base!r} isn't a commit here: {exc}") from exc
    committed = _git(root, "diff", "--name-only", f"{base}...HEAD").split()
    working = _git(root, "diff", "--name-only", "HEAD").split()
    files = sorted(set(committed) | set(working))
    ranges: dict[str, list[tuple[int, int]]] = {}
    current = None
    for line in _git(root, "diff", "-U0", "--no-color", base).splitlines():
        if line.startswith("+++ "):
            current = (
                None
                if line.endswith("/dev/null")
                else line[6:]
                if line.startswith("+++ b/")
                else line[4:]
            )
        elif current and (m := _HUNK.match(line)):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            if count:
                ranges.setdefault(current, []).append((start, start + count - 1))
    commits = [
        dict(zip(("sha", "subject"), row.split("\t", 1), strict=False))
        for row in _git(root, "log", "--no-merges", "--format=%h\t%s", f"{base}..HEAD").splitlines()
        if row.strip()
    ]
    return {"files": files, "ranges": ranges, "commits": commits}


def review(
    model: dict[str, Any],
    change: dict[str, Any],
    findings: dict[str, Any] | None = None,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    facts = Facts(model)
    by_path = {f["path"]: fid for fid, f in facts.files.items()}
    changed_files = [p for p in change["files"] if p in by_path]
    changed_symbols = []
    for path in changed_files:
        spans = change["ranges"].get(path, [])
        for sid in facts.files[by_path[path]]["symbols"]:
            s = facts.symbols.get(sid)
            if not s or not s.get("line"):
                continue
            end = s.get("end_line") or s["line"]
            if any(a <= end and b >= s["line"] for a, b in spans):
                changed_symbols.append(sid)
    callers = sorted(
        {
            e["s"]
            for sid in changed_symbols
            for e in facts.callers.get(sid, [])
            if e["s"] not in changed_symbols
        }
    )
    reach: set[str] = set()
    for path in changed_files:
        reach |= facts.reach(by_path[path])
    impacted = sorted(facts.path(f) for f in reach if facts.path(f) not in changed_files)
    touched = set(changed_files) | set(impacted)
    tests = sorted(
        {
            facts.path(fid)
            for fid in facts.files
            if _TEST.search(facts.path(fid))
            and (
                facts.path(fid) in change["files"]
                or any(facts.path(t) in touched for t in facts.imports.get(fid, ()))
            )
        }
    )
    blocking: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    for f in (findings or {}).get("findings", []):
        if not (f.get("changed") or f.get("impacted") or f["kind"] == "test"):
            continue
        item = {
            "kind": f["kind"],
            "what": f.get("message") or f.get("rule"),
            "where": (f"{f['path']}:{f['line']}" if f.get("line") else f.get("path"))
            or f.get("evidence"),
            "fix": f.get("suggestion", ""),
            "basis": "observed",
        }
        if f["tier"] == "fix now":
            blocking.append(item)
        elif f["tier"] == "fix soon":
            advisory.append(item)
    for sid in changed_symbols:
        s = facts.symbols[sid]
        hot = facts.hotspots.get((facts.path(sid), s["name"]))
        if hot and hot[0] >= COMPLEX:
            advisory.append(
                {
                    "kind": "complexity",
                    "what": f"`{s['name']}` changed and has a cyclomatic complexity of {hot[0]}",
                    "where": f"{facts.path(sid)}:{hot[1] or s['line']}",
                    "fix": "keep the change small, and test each branch it touches",
                    "basis": "derived",
                }
            )
    for path in changed_files:
        fid = by_path[path]
        if fid in facts.in_cycle:
            others = [facts.path(o) for o in facts.in_cycle[fid] if o != fid]
            advisory.append(
                {
                    "kind": "cycle",
                    "what": f"{path} is in an import cycle with {', '.join(others)}",
                    "where": path,
                    "fix": "check that the change doesn't need the other files changed at the same time",
                    "basis": "derived",
                }
            )
    requirements = []
    if trace:
        changed_ids = set(changed_symbols) | {by_path[p] for p in changed_files}
        for r in trace.get("requirements", []):
            hits = [c for c in r.get("code", []) if c["id"] in changed_ids]
            if not hits:
                continue
            requirements.append(
                {
                    "id": r["id"],
                    "status": r["status"],
                    "tested": bool(r.get("tested")),
                    "text": r["text"],
                }
            )
            if r["status"] == "linked" and not r.get("tested"):
                blocking.append(
                    {
                        "kind": "requirement",
                        "what": f"{r['id']}'s code changed, and no test mentions {r['id']}",
                        "where": ", ".join(f"{c['path']}:{c['line']}" for c in hits[:3]),
                        "fix": f"add or update a test that names {r['id']}",
                        "basis": "observed",
                    }
                )
            elif r["status"] == "possible":
                advisory.append(
                    {
                        "kind": "requirement",
                        "what": f"{r['id']} may relate to the changed code (inferred from its words)",
                        "where": ", ".join(f"{c['path']}:{c['line']}" for c in hits[:3]),
                        "fix": f"if it does, name the code in {r['id']} so the link is checked",
                        "basis": "inferred",
                    }
                )
    rerun = []
    if tests:
        py = [t for t in tests if t.endswith(".py")]
        js = [t for t in tests if not t.endswith(".py")]
        if py:
            rerun.append({"gate": "tests", "command": "python -m pytest " + " ".join(py)})
        if js:
            rerun.append({"gate": "tests", "command": "npx vitest run " + " ".join(js)})
    rerun += [g for g in (findings or {}).get("rerun", []) if g.get("gate") != "tests"]
    return {
        "schema": SCHEMA,
        "changed": {
            "files": change["files"],
            "symbols": [
                {
                    "id": sid,
                    "name": facts.symbols[sid]["name"],
                    "where": f"{facts.path(sid)}:{facts.symbols[sid]['line']}",
                }
                for sid in changed_symbols
            ],
            "commits": change["commits"],
        },
        "reach": {
            "callers": [
                {"id": c, "where": f"{facts.path(c)}:{facts.symbols[c]['line']}"}
                for c in callers
                if c in facts.symbols
            ],
            "impacted_files": impacted,
        },
        "requirements": requirements,
        "blocking": blocking,
        "advisory": advisory,
        "retest": {"tests": tests, "rerun": rerun},
        "verdict": "blocked" if blocking else "ready for review",
        "limits": [
            "Only what Ananke's graph and the repository's reports show: dynamic calls and runtime behaviour aren't seen.",
            "Findings come from existing reports, which may be older than the change: rerun the listed gates.",
            *(
                []
                if trace
                else ["No spec was given, so requirements weren't checked (use --spec)."]
            ),
        ],
    }


def to_markdown(r: dict[str, Any]) -> str:
    c = r["changed"]
    lines = [
        f"# Review: {r['verdict']}",
        "",
        f"{len(c['files'])} changed file(s), {len(c['symbols'])} changed function(s) or class(es), "
        f"{len(r['reach']['callers'])} caller(s) and {len(r['reach']['impacted_files'])} more file(s) reached through imports.",
        "",
    ]
    for title, items in (("Blocking", r["blocking"]), ("Advisory", r["advisory"])):
        lines += [f"## {title}", ""]
        lines += [
            f"- **{i['kind']}** {i['what']} ({i['where']}). {i['fix']}".rstrip() for i in items
        ] or ["- none"]
        lines.append("")
    lines += ["## Retest", ""]
    lines += [f"- `{g['command']}`" for g in r["retest"]["rerun"]] or [
        "- no test exercises the change: add one"
    ]
    lines += ["", "## Limits", ""] + [f"- {x}" for x in r["limits"]]
    return "\n".join(lines).replace("<", "&lt;") + "\n"


def pr_body(r: dict[str, Any], *, revision: str | None = None, digest: str | None = None) -> str:
    """A draft pull request description: what changed and why (from the commits), requirements, tests, evidence and
    residual risks. Every line comes from the review; edit it before posting."""
    c = r["changed"]
    lines = ["## Summary", ""]
    lines += [f"- {cm.get('subject', '')} ({cm.get('sha', '')})" for cm in c["commits"]] or [
        "- (uncommitted changes)"
    ]
    lines += ["", "## Changes", ""]
    lines += [f"- `{s['name']}` ({s['where']})" for s in c["symbols"][:25]] or [
        f"- {f}" for f in c["files"][:25]
    ]
    if r["requirements"]:
        lines += ["", "## Requirements", ""]
        lines += [
            f"- **{q['id']}** {q['text']} ({q['status']}{', tested' if q['tested'] else ', not tested'})"
            for q in r["requirements"]
        ]
    lines += ["", "## Tests", ""]
    changed_tests = [t for t in r["retest"]["tests"] if t in c["files"]]
    lines += [f"- changed: `{t}`" for t in changed_tests]
    lines += [f"- run: `{g['command']}`" for g in r["retest"]["rerun"]] or [
        "- no test exercises the change"
    ]
    lines += ["", "## Evidence", ""]
    lines.append(
        f"- Reviewed with Dev Guru against {revision or 'the working tree'}"
        + (f", model digest `{digest}`" if digest else "")
    )
    lines.append(
        f"- {len(r['blocking'])} blocking and {len(r['advisory'])} advisory item(s); verdict: {r['verdict']}"
    )
    lines += ["", "## Residual risks", ""]
    risks = [f"- {i['what']} ({i['where']})" for i in r["blocking"] + r["advisory"]]
    lines += risks or ["- none found in the graph and reports"]
    lines += [f"- {x}" for x in r["limits"][:2]]
    return "\n".join(lines).replace("<", "&lt;") + "\n"


__all__ = ["SCHEMA", "ReviewError", "changes", "pr_body", "review", "to_markdown"]
