"""Documentation for one audience at one depth (``dev docs``), built from the explorer view model.

The four audiences are the explanation ladder's levels. ``detail`` sets how much each section shows: ``brief``,
``standard`` or ``deep``. Each section is a list of statements and an optional table, and every row cites its
evidence, which the Markdown links to the source file and line. The document ends with its provenance (source
revision, versions, the model's digest), and ``check_links`` proves every relative link resolves.

The same input gives the same document. Text from the code (docstrings, names, signatures) is escaped, so it can't
add links, HTML or table cells.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dev_guru.explain import COMPLEX, LEVELS, Facts, _file_ladder, first_sentence
from dev_guru.reports import subgraph

SCHEMA = "dev-guru/documentation@1"
DETAILS = {"brief": 5, "standard": 15, "deep": 50}
GLOSSARY = [
    ("file", "one text file of code, such as `cart.py`"),
    ("folder (package)", "a group of files that belong together"),
    ("import", "one file using code from another; the arrow points from the user to what it uses"),
    ("function", "a named piece of code that does one job and can be used from elsewhere"),
    ("class", "a template for things that hold data together with the functions that work on it"),
    ("call", "one function using another while the program runs"),
    ("entry point", "the file the program starts from"),
    (
        "import cycle",
        "files that import each other in a loop, so none can be understood or tested alone",
    ),
    (
        "complexity",
        "how many paths there are through a function; above 10 it's hard to change safely",
    ),
]


class DocsError(ValueError):
    pass


def _section(
    sid: str,
    title: str,
    statements: list[dict[str, Any]] | None = None,
    table: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {"id": sid, "title": title, "statements": statements or [], "table": table}


def _say(text: str, basis: str, *evidence: tuple[str, int]) -> dict[str, Any]:
    return {
        "text": text,
        "basis": basis,
        "evidence": [{"path": p, "line": n} for p, n in evidence if p],
    }


def _table(
    columns: list[str], rows: list[tuple[list[str], list[tuple[str, int]]]]
) -> dict[str, Any]:
    return {
        "columns": columns,
        "rows": [
            {"cells": cells, "evidence": [{"path": p, "line": n} for p, n in ev if p]}
            for cells, ev in rows
        ],
    }


def _summary(facts: Facts) -> dict[str, Any]:
    p = facts.model["project"]
    repo = facts.model.get("repository") or {}
    langs = repo.get("languages") or {}
    lang = (
        ", ".join(
            f"{k} ({v})" for k, v in sorted(langs.items(), key=lambda kv: (-int(kv[1] or 0), kv[0]))
        )
        if langs
        else ""
    )
    out = [
        _say(
            f"`{p['name']}` has {p['files']} source files in {p['packages']} folders: {p['loc']} lines, "
            f"{p['symbols']} classes and functions, {p['imports']} imports between its own files and {p['calls']} calls.",
            "derived",
        )
    ]
    if lang:
        out.append(_say(f"Languages by file count: {lang}.", "derived"))
    if p.get("external"):
        out.append(_say(f"It uses {p['external']} outside libraries.", "derived"))
    return _section("summary", "Summary", out)


def _risks(facts: Facts, limit: int) -> dict[str, Any]:
    m, total = facts.model, len(facts.files)
    out = []
    cycles = m.get("insights", {}).get("cycles", [])
    out.append(
        _say(
            (
                f"{len(cycles)} import cycle{'s' if len(cycles) != 1 else ''}"
                if cycles
                else "No import cycles"
            )
            + (
                ": "
                + "; ".join(" ↔ ".join(f"`{facts.path(f)}`" for f in c) for c in cycles[:limit])
                if cycles
                else "."
            ),
            "derived",
            *((facts.path(c[0]), 0) for c in cycles[:limit]),
        )
    )
    hard = sorted(
        (
            (c, name, path, line)
            for (path, name), (c, line) in facts.hotspots.items()
            if c >= COMPLEX
        ),
        reverse=True,
    )
    out.append(
        _say(
            f"{len(hard)} function{'s are' if len(hard) != 1 else ' is'} hard to change (complexity {COMPLEX} or more)"
            + (
                ": " + ", ".join(f"`{n}` ({c})" for c, n, _p, _l in hard[:limit]) + "."
                if hard
                else "."
            ),
            "derived",
            *((p, line) for _c, _n, p, line in hard[:limit]),
        )
    )
    central = sorted(((len(facts.reach(fid)), fid) for fid in facts.files), reverse=True)[:3]
    if central and central[0][0]:
        out.append(
            _say(
                "Most of the project depends on "
                + ", ".join(
                    f"`{facts.path(fid)}` ({round(100 * n / total)}% of files)"
                    for n, fid in central
                    if n
                )
                + ": changes there need the most care.",
                "derived",
                *((facts.path(fid), 0) for n, fid in central if n),
            )
        )
    repo = m.get("repository") or {}
    cov = repo.get("coverage") or {}
    if cov.get("line_rate") is not None:
        out.append(
            _say(
                f"Tests cover {round(100 * float(cov['line_rate']))}% of lines, from the coverage report.",
                "observed",
            )
        )
    else:
        out.append(_say("Test coverage is unknown: no coverage report was found.", "derived"))
    deps = repo.get("dependencies") or {}
    vulns = deps.get("vulnerabilities")
    out.append(
        _say(
            "Dependencies weren't checked for known vulnerabilities (run `dev explore --check-vulnerabilities`)."
            if vulns is None
            else f"{len(vulns)} known vulnerabilit{'ies' if len(vulns) != 1 else 'y'} in dependencies."
            if vulns
            else "No known vulnerabilities in the dependencies that were checked.",
            "observed" if vulns is not None else "derived",
        )
    )
    return _section("risks", "Where the risk is", out)


def _limitations(facts: Facts) -> dict[str, Any]:
    return _section(
        "limitations",
        "What this doesn't cover",
        [_say(t, "observed") for t in facts.model.get("limitations", [])],
    )


def _packages(facts: Facts, limit: int) -> dict[str, Any]:
    sub = subgraph.select(facts.model, level="package", budget=subgraph.MAX_BUDGET)
    uses: dict[str, list[str]] = {}
    for e in sub["edges"]:
        if "imports" in e["kinds"]:
            uses.setdefault(e["s"], []).append(e["t"].removeprefix("package:"))
    rows: list[tuple[list[str], list[tuple[str, int]]]] = []
    for pkg in sorted(facts.model.get("packages", []), key=lambda p: (-len(p["files"]), p["name"]))[
        :limit
    ]:
        loc = sum(facts.files[f]["loc"] for f in pkg["files"] if f in facts.files)
        rows.append(
            (
                [
                    f"`{pkg['name']}`",
                    str(len(pkg["files"])),
                    str(loc),
                    ", ".join(f"`{u}`" for u in sorted(uses.get("package:" + pkg["name"], [])))
                    or "—",
                ],
                [],
            )
        )
    return _section(
        "packages",
        "Folders and what they depend on",
        table=_table(["Folder", "Files", "Lines", "Imports from"], rows),
    )


def _central(facts: Facts, limit: int) -> dict[str, Any]:
    total = len(facts.files)
    ranked = sorted(
        ((len(facts.reach(fid)), fid) for fid in facts.files),
        key=lambda x: (-x[0], facts.path(x[1])),
    )
    rows = [
        (
            [
                f"`{facts.path(fid)}`",
                str(facts.files[fid]["fan_in"]),
                f"{round(100 * n / total)}%",
                _cell(first_sentence(facts.files[fid].get("doc", ""))),
            ],
            [(facts.path(fid), 1)],
        )
        for n, fid in ranked[:limit]
        if n
    ]
    return _section(
        "central",
        "Files the rest depends on",
        [
            _say(
                "Reach is the share of files that import a file directly or through others: what a change can affect.",
                "derived",
            )
        ],
        _table(["File", "Imported by", "Reach", "Description"], rows),
    )


def _cell(text: str) -> str:
    return text[:120] + ("…" if len(text) > 120 else "")


def _interfaces(facts: Facts, limit: int) -> list[dict[str, Any]]:
    repo = facts.model.get("repository") or {}
    out = []
    rows: list[tuple[list[str], list[tuple[str, int]]]]
    if repo.get("routes"):
        rows = [
            ([str(r[0]), f"`{r[1]}`", f"`{r[2]}`", str(r[3] or "—")], [])
            for r in repo["routes"][:limit]
        ]
        out.append(
            _section(
                "routes",
                "API routes",
                [
                    _say(
                        f"{repo.get('routes_total', len(repo['routes']))} routes; the first {len(rows)} are listed.",
                        "derived",
                    )
                ],
                _table(["Method", "Path", "Handler", "Called from"], rows),
            )
        )
    if repo.get("tables"):
        rows = [([f"`{t[0]}`", _cell(str(t[1]))], []) for t in repo["tables"][:limit]]
        out.append(
            _section(
                "data",
                "Data tables",
                [
                    _say(
                        f"{repo.get('tables_total', len(repo['tables']))} tables; the first {len(rows)} are listed.",
                        "derived",
                    )
                ],
                _table(["Table", "Columns"], rows),
            )
        )
    return out


def _complexity(facts: Facts, limit: int) -> dict[str, Any]:
    rows = [
        ([f"`{name}`", str(c), f"`{path}`"], [(path, line)])
        for (path, name), (c, line) in sorted(
            facts.hotspots.items(), key=lambda kv: (-kv[1][0], kv[0])
        )[:limit]
    ]
    return _section(
        "complexity",
        "The most complex functions",
        table=_table(["Function", "Complexity", "File"], rows),
    )


def _files(facts: Facts, limit: int, deep: bool) -> list[dict[str, Any]]:
    out = []
    for pkg in sorted(facts.model.get("packages", []), key=lambda p: p["name"])[:limit]:
        rows: list[tuple[list[str], list[tuple[str, int]]]] = []
        for fid in pkg["files"][: limit * 2]:
            f = facts.files[fid]
            names = [
                facts.symbols[s]["name"]
                for s in f["symbols"]
                if s in facts.symbols and facts.symbols[s]["kind"] in ("class", "function")
            ]
            rows.append(
                (
                    [
                        f"`{f['path']}`",
                        _cell(first_sentence(f.get("doc", ""))) or "—",
                        ", ".join(f"`{n}`" for n in names[:8]) + (" …" if len(names) > 8 else "")
                        or "—",
                    ],
                    [(f["path"], 1)],
                )
            )
        statements = []
        if deep:
            for fid in pkg["files"][:limit]:
                statements += _file_ladder(facts, fid)["practitioner"][:6]
        out.append(
            _section(
                "files-" + re.sub(r"[^a-z0-9]+", "-", pkg["name"].lower()).strip("-"),
                f"`{pkg['name']}`",
                statements,
                _table(["File", "Description", "Defines"], rows),
            )
        )
    return out


def _start(facts: Facts, limit: int, *, plain: bool) -> dict[str, Any]:
    out = []
    for fid in facts.reading_path(limit):
        f = facts.files[fid]
        what = first_sentence(f.get("doc", "")) or (
            "the program starts here" if f.get("entry") else "no description in the file"
        )
        out.append(_say(f"`{f['path']}`: {what}", "observed", (f["path"], 1)))
    section = _section("start", "Where to start", out)
    section["ordered"] = True
    section["lead"] = (
        "Read these in order: start where the program starts, then follow what it uses."
        if plain
        else "Entry points first, then what they import, breadth first."
    )
    return section


def build(
    model: dict[str, Any],
    manifest: dict[str, Any],
    *,
    audience: str = "practitioner",
    detail: str = "standard",
) -> dict[str, Any]:
    if audience not in LEVELS:
        raise DocsError(f"unknown audience {audience!r}; choose {', '.join(LEVELS)}")
    if detail not in DETAILS:
        raise DocsError(f"unknown detail {detail!r}; choose {', '.join(DETAILS)}")
    facts = Facts(model)
    n = DETAILS[detail]
    sections: list[dict[str, Any]] = [_summary(facts)]
    if audience == "executive":
        sections += [_risks(facts, min(n, 5))]
    elif audience == "principal":
        sections += [
            _packages(facts, n),
            _central(facts, n),
            _risks(facts, n),
            *_interfaces(facts, n),
            _complexity(facts, n),
        ]
    elif audience == "practitioner":
        sections += [
            _start(facts, n, plain=False),
            *_files(facts, n, detail == "deep"),
            *_interfaces(facts, n),
            _complexity(facts, n),
        ]
    else:
        sections += [
            _section(
                "words",
                "Words used here",
                table=_table(["Word", "Meaning"], [([w, d], []) for w, d in GLOSSARY]),
            ),
            _start(facts, n, plain=True),
        ]
        key = [fid for fid in model.get("insights", {}).get("most_depended", [])[: max(3, n // 3)]]
        for fid in key:
            sections.append(
                _section(
                    "key-" + re.sub(r"[^a-z0-9]+", "-", facts.path(fid).lower()).strip("-"),
                    f"`{facts.path(fid)}`",
                    _file_ladder(facts, fid)["novice"],
                )
            )
    sections.append(_limitations(facts))
    ws = manifest.get("workspace", {})
    return {
        "schema": SCHEMA,
        "project": model["project"]["name"],
        "audience": audience,
        "detail": detail,
        "sections": [s for s in sections if s["statements"] or (s["table"] and s["table"]["rows"])],
        "provenance": {
            "view_model": model.get("schema"),
            "input_digest": manifest.get("input_digest"),
            "dev_guru": manifest.get("dev_guru"),
            "ananke": manifest.get("ananke"),
            "snapshot_id": manifest.get("snapshot_id"),
            "commit": ws.get("commit"),
            "dirty": ws.get("dirty"),
            "generated_at": manifest.get("generated_at"),
        },
    }


# ------------------------------------------------------------------------------------------------ Markdown
_CODE = re.compile(r"(`+)(.+?)\1")


def escape(text: str, *, cell: bool = False) -> str:
    """Escape Markdown and HTML outside code spans; inside them only a table's pipe needs it."""
    out, last = [], 0
    for m in _CODE.finditer(text):
        out.append(_plain(text[last : m.start()], cell))
        out.append(m.group(0).replace("|", "\\|") if cell else m.group(0))
        last = m.end()
    out.append(_plain(text[last:], cell))
    return "".join(out)


def _plain(text: str, cell: bool) -> str:
    text = text.replace("\\", "\\\\").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"([\[\]*_#])", r"\\\1", text)
    text = text.replace("\n", " ")
    return text.replace("|", "\\|") if cell else text


def _link(ev: dict[str, Any], root: Path, out_dir: Path) -> str:
    target = os.path.relpath(root / ev["path"], out_dir).replace(os.sep, "/")
    label = ev["path"] + (f":{ev['line']}" if ev["line"] else "")
    anchor = f"#L{ev['line']}" if ev["line"] else ""
    return f"[{label}]({target}{anchor})"


def to_markdown(doc: dict[str, Any], *, root: Path, out_dir: Path) -> str:
    who = {
        "novice": "someone new to the code",
        "practitioner": "developers working on it",
        "principal": "architects and reviewers",
        "executive": "leaders deciding what to fund",
    }[doc["audience"]]
    lines = [
        "---",
        f"title: {doc['project']}: for {who}",
        f"audience: {doc['audience']}",
        f"detail: {doc['detail']}",
        f"schema: {SCHEMA}",
        f"input_digest: {doc['provenance']['input_digest']}",
        "---",
        "",
        f"# {escape(doc['project'])}",
        "",
        f"Written for {who}, from the code itself. Every statement links to the line it comes from; "
        "*inferred* marks a call found through imports rather than read directly.",
        "",
    ]
    for sec in doc["sections"]:
        lines += [f"## {escape(sec['title'])}", ""]
        if sec.get("lead"):
            lines += [escape(sec["lead"]), ""]
        for i, st in enumerate(sec["statements"], start=1):
            refs = ", ".join(_link(ev, root, out_dir) for ev in st["evidence"][:4])
            tag = " *(inferred)*" if st["basis"] == "inferred" else ""
            bullet = f"{i}." if sec.get("ordered") else "-"
            lines.append(f"{bullet} {escape(st['text'])}{tag}" + (f" ({refs})" if refs else ""))
        if sec["statements"]:
            lines.append("")
        table = sec.get("table")
        if table and table["rows"]:
            cols = table["columns"] + (
                ["Source"] if any(r["evidence"] for r in table["rows"]) else []
            )
            lines += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            for row in table["rows"]:
                cells = [escape(c, cell=True) for c in row["cells"]]
                if len(cols) > len(row["cells"]):
                    cells.append(
                        ", ".join(_link(ev, root, out_dir) for ev in row["evidence"][:2]) or "—"
                    )
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
    prov = doc["provenance"]
    lines += [
        "## Provenance",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Source revision | {('`' + prov['commit'][:12] + '`' + (' (uncommitted changes)' if prov.get('dirty') else '')) if prov.get('commit') else 'not a Git repository'} |",
        f"| Analysed by | Ananke Plexus {prov.get('ananke') or '?'}, Dev Guru {prov.get('dev_guru')} |",
        f"| View model | `{prov.get('view_model')}`, digest `{prov.get('input_digest')}` |",
        f"| Generated | {prov.get('generated_at')} |",
        "",
    ]
    return "\n".join(lines)


def explanation_markdown(exp: dict[str, Any], *, root: Path, out_dir: Path) -> str:
    """The ladder as Markdown: one section per level, every statement linked to its evidence."""
    titles = {
        "novice": "In plain words",
        "practitioner": "For developers",
        "principal": "For architects",
        "executive": "For leaders",
    }
    lines = [
        f"# `{exp['path']}`"
        + ("" if exp["kind"] == "file" else f": `{exp['focus'].rsplit(':', 1)[-1]}`"),
        "",
    ]
    for level, statements in exp["levels"].items():
        lines += [f"## {titles[level]}", ""]
        for st in statements:
            refs = ", ".join(_link(ev, root, out_dir) for ev in st["evidence"][:4])
            tag = " *(inferred)*" if st["basis"] == "inferred" else ""
            lines.append(f"- {escape(st['text'])}{tag}" + (f" ({refs})" if refs else ""))
        lines.append("")
    if exp.get("limitations"):
        lines += ["## Limits", "", *(f"- {escape(t)}" for t in exp["limitations"]), ""]
    return "\n".join(lines)


_MD_LINK = re.compile(r"(?<!\\)\]\(([^)\s]+)\)")  # an escaped \] is text, not a link


def check_links(markdown: str, out_dir: Path) -> list[str]:
    """Relative links that don't resolve to a file, or point past its end (empty when every link holds)."""
    problems = []
    for target in _MD_LINK.findall(markdown):
        if re.match(r"[a-z]+:", target):
            problems.append(f"{target}: external link")
            continue
        path, _, anchor = target.partition("#")
        file = (out_dir / path).resolve()
        if not file.is_file():
            problems.append(f"{target}: no such file")
        elif (
            anchor.startswith("L")
            and anchor[1:].isdigit()
            and file.suffix == ".py"
            and int(anchor[1:])
            > max(1, len(file.read_text(encoding="utf-8", errors="replace").splitlines()))
        ):
            problems.append(f"{target}: past the end of the file")
    return problems


def to_slides(doc: dict[str, Any]) -> str:
    """Markdown slides for ``dev present``: one slide per section, the first few points of each."""
    who = {
        "novice": "Newcomers",
        "practitioner": "Developers",
        "principal": "Architects",
        "executive": "Leaders",
    }[doc["audience"]]
    slides = [
        f"---\ntitle: {doc['project']}\n---\n\n# {escape(doc['project'])}\n\nFor {who.lower()}, from the code itself"
    ]
    for sec in doc["sections"]:
        body = [f"## {escape(sec['title'])}", ""]
        if sec.get("lead"):
            body += [escape(sec["lead"]), ""]
        body += [
            f"{f'{i}.' if sec.get('ordered') else '-'} {escape(st['text'])}"
            for i, st in enumerate(sec["statements"][:6], start=1)
        ]
        table = sec.get("table")
        if table and table["rows"]:
            body += [
                "",
                "| " + " | ".join(table["columns"]) + " |",
                "|" + "---|" * len(table["columns"]),
            ]
            body += [
                "| " + " | ".join(escape(c, cell=True) for c in r["cells"]) + " |"
                for r in table["rows"][:6]
            ]
        slides.append("\n".join(body))
    prov = doc["provenance"]
    slides.append(
        "## Provenance\n\n"
        f"- Revision `{(prov.get('commit') or 'none')[:12]}`, Ananke {prov.get('ananke')}, Dev Guru {prov.get('dev_guru')}\n"
        f"- Model digest `{str(prov.get('input_digest'))[:23]}…`"
    )
    return "\n\n---\n\n".join(slides) + "\n"


__all__ = [
    "DETAILS",
    "SCHEMA",
    "DocsError",
    "build",
    "check_links",
    "escape",
    "explanation_markdown",
    "to_markdown",
    "to_slides",
]
