"""Spec-driven work: write a spec from an idea (``dev spec new``) and trace each requirement to the code
(``dev spec trace``).

A requirement is a line that starts with an id: ``R1``, ``REQ-12`` or any ``ABC-3``, optionally bold or in a list.
Each one is traced, deterministically:

* **linked**: the requirement names code that exists, in backticks (```Cart.total```, ```shop/cart.py```), so the
  link is observed;
* **possible**: no name, but at least two of its words match a function's or file's name or description; inferred,
  ranked, never more than three;
* **unlinked**: nothing matches, which is worth knowing before it's built.

A requirement is **tested** when a test file mentions its id. The trace says which, with the line. With a level, each
linked or possible requirement gets the explanation ladder's words for its best match, so the trace doubles as a
guide to the code at the reader's level.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dev_guru.explain import LEVELS, Facts, first_sentence

SCHEMA = "dev-guru/spec-trace@1"
REQUIREMENT = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\*\*)?([A-Z][A-Z0-9]*-?\d+)(?:\*\*)?[:.)]?(?:\*\*)?\s+(.+?)\s*$"
)
_STOP = set(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "as",
        "at",
        "is",
        "are",
        "be",
        "it",
        "this",
        "that",
        "system",
        "user",
        "users",
        "must",
        "should",
        "shall",
        "can",
        "will",
        "when",
        "then",
        "each",
        "every",
        "all",
        "any",
        "not",
        "no",
        "new",
        "only",
        "also",
        "its",
        "their",
        "into",
        "out",
        "up",
        "so",
        "if",
        "than",
        "per",
    ]
)


class SpecError(ValueError):
    pass


def template(name: str, idea: str = "") -> str:
    """A spec to fill in. The requirement ids are what ``dev spec trace`` follows."""
    today = datetime.now(UTC).date().isoformat()
    problem = idea.strip() or "What's wrong today, for whom, and how do we know?"
    return f"""---
title: {name}
status: draft
created: {today}
---

# {name}

## Problem

{problem}

## Users

- Who has this problem, and what are they trying to do?

## Outcomes

- What will be measurably different when this is done?

## Requirements

Give each requirement an id. Name the code it touches in backticks when you know it (for example `module.py` or
`function_name`), and mention the id in the tests that check it, so `dev spec trace` can follow both.

- **R1** The first thing it must do.
- **R2** The second thing it must do.
- **R3** What it must never do.

## Acceptance

- R1: how a reviewer can see it works.
- R2: how a reviewer can see it works.
- R3: the test that proves it can't happen.

## Out of scope

- What this deliberately leaves out.

## Open questions

- What has to be decided before building it?
"""


def requirements(text: str) -> list[dict[str, Any]]:
    """Requirement lines in the Requirements section (or anywhere, when there's no such section)."""
    lines = text.splitlines()
    section = [
        i for i, line in enumerate(lines) if re.match(r"^#{1,6}\s+requirements\b", line, re.I)
    ]
    start = section[0] + 1 if section else 0
    end = len(lines)
    if section:
        level = len(lines[section[0]]) - len(lines[section[0]].lstrip("#"))
        for j in range(start, len(lines)):
            m = re.match(r"^(#{1,6})\s", lines[j])
            if m and len(m.group(1)) <= level:
                end = j
                break
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for no in range(start, end):
        m = REQUIREMENT.match(lines[no])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            found.append({"id": m.group(1), "text": m.group(2).strip(), "line": no + 1})
    return found


def _words(text: str) -> set[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    words = re.findall(r"[a-z][a-z0-9]{2,}", spaced.replace("_", " ").lower())
    # "orders" and "order" are the same word here; nothing finer is attempted
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in words if w not in _STOP}


def trace(
    spec_text: str,
    spec_name: str,
    model: dict[str, Any],
    root: Path,
    *,
    level: str | None = None,
) -> dict[str, Any]:
    if level is not None and level not in LEVELS:
        raise SpecError(f"unknown level {level!r}; choose {', '.join(LEVELS)}")
    reqs = requirements(spec_text)
    if not reqs:
        raise SpecError(
            f"{spec_name}: no requirements found. Start a line with an id, such as '- **R1** The cart totals prices'"
        )
    facts = Facts(model)
    by_name: dict[str, list[str]] = {}
    for sid, s in facts.symbols.items():
        by_name.setdefault(s["name"].rsplit(".", 1)[-1], []).append(sid)
        by_name.setdefault(s["name"], []).append(sid)
    for fid, f in facts.files.items():
        by_name.setdefault(f["path"], []).append(fid)
        by_name.setdefault(f["name"], []).append(fid)
    index = []
    for sid, s in facts.symbols.items():
        index.append((sid, _words(s["name"]), _words(s.get("doc", ""))))
    for fid, f in facts.files.items():
        index.append((fid, _words(f["name"].rsplit(".", 1)[0]), _words(f.get("doc", ""))))
    tests = []
    for f in facts.files.values():
        if re.search(r"(^|/)(tests?|spec)(/|_)|(^|/)test_[^/]+$|_test\.py$", f["path"]):
            try:
                tests.append(
                    (
                        f["path"],
                        (root / f["path"])
                        .read_text(encoding="utf-8", errors="replace")
                        .splitlines(),
                    )
                )
            except OSError:
                continue
    from dev_guru.explain import explain

    out = []
    for req in reqs:
        named = sorted(
            {
                target
                for token in re.findall(r"`([^`]+)`", req["text"])
                for target in by_name.get(token.strip().removesuffix("()"), [])
            }
        )
        words = _words(re.sub(r"`[^`]*`", " ", req["text"]))
        scored = []
        if not named and words:
            for nid, name_words, doc_words in index:
                shared = words & (name_words | doc_words)
                if len(shared) >= 2:  # one shared word is a coincidence, not a match
                    scored.append((3 * len(words & name_words) + len(words & doc_words), nid))
            scored.sort(key=lambda x: (-x[0], x[1]))
        matches = named or [nid for _, nid in scored[:3]]
        status = "linked" if named else "possible" if matches else "unlinked"
        tested = [
            {"path": path, "line": i}
            for path, lines in tests
            for i, line in enumerate(lines, start=1)
            if re.search(rf"\b{re.escape(req['id'])}\b", line)
        ][:5]
        code = [
            {
                "id": nid,
                "path": facts.path(nid),
                "line": facts.symbols[nid]["line"] if nid in facts.symbols else 1,
                "name": facts.symbols[nid]["name"]
                if nid in facts.symbols
                else facts.files[nid]["path"],
                "basis": "observed" if named else "inferred",
            }
            for nid in matches[:5]
        ]
        entry: dict[str, Any] = {**req, "status": status, "code": code, "tested": tested}
        if level and code:
            exp = explain(model, code[0]["id"], levels=(level,))
            entry["explanation"] = [st["text"] for st in exp["levels"][level][:3]]
        out.append(entry)
    counts = {
        s: sum(1 for r in out if r["status"] == s) for s in ("linked", "possible", "unlinked")
    }
    return {
        "schema": SCHEMA,
        "spec": spec_name,
        "level": level,
        "requirements": out,
        "summary": {**counts, "tested": sum(1 for r in out if r["tested"]), "total": len(out)},
    }


def trace_markdown(tr: dict[str, Any]) -> str:
    def code_cell(r: dict[str, Any]) -> str:
        if not r["code"]:
            return "—"
        return ", ".join(f"`{c['name']}` ({c['path']}:{c['line']})" for c in r["code"][:3]).replace(
            "|", "\\|"
        )

    s = tr["summary"]
    lines = [
        f"# Trace of {tr['spec']}",
        "",
        f"{s['total']} requirements: {s['linked']} linked to code they name, {s['possible']} with possible matches "
        f"(inferred), {s['unlinked']} unlinked; {s['tested']} mentioned by a test.",
        "",
        "| Requirement | Status | Code | Tested |",
        "|---|---|---|---|",
    ]
    for r in tr["requirements"]:
        text = first_sentence(r["text"]).replace("|", "\\|").replace("<", "&lt;")
        tested = ", ".join(f"{t['path']}:{t['line']}" for t in r["tested"][:2]) or "no"
        lines.append(f"| **{r['id']}** {text} | {r['status']} | {code_cell(r)} | {tested} |")
    lines.append("")
    explained = [r for r in tr["requirements"] if r.get("explanation")]
    if explained:
        lines += [f"## The code behind each requirement ({tr['level']})", ""]
        for r in explained:
            lines += (
                [f"### {r['id']}", ""]
                + [f"- {t.replace('<', '&lt;')}" for t in r["explanation"]]
                + [""]
            )
    return "\n".join(lines)


__all__ = ["SCHEMA", "SpecError", "requirements", "template", "trace", "trace_markdown"]
