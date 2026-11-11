"""Mentoring from evidence: advice on failures that repeat (``dev mentor``), and a map of what has been learned
(``dev learning graph``).

Advice is never a judgement of style. It comes only from failures Ananke recorded in this workspace's runs, and only
when the same failure happened in at least ``min_repeats`` runs. Every piece of advice names those runs, the
failure's code and message, and what that code means. When a reviewed lesson (a learning candidate that passed its
gate) talks about the same thing, it's linked. A failure seen once is listed, with no advice: one occurrence isn't a
pattern.

The learning graph reads the learning candidates: which runs each was learned from, which files of the project it
mentions, and which terms more than one lesson shares, which is how a lesson that transfers shows. It only reads:
promoting a lesson stays ``ananke learning promote``, after review.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

FEEDBACK_SCHEMA = "dev-guru/mentor-feedback@1"
GRAPH_SCHEMA = "dev-guru/learning-graph@1"
LEVELS = ("novice", "practitioner", "principal", "executive")
MIN_REPEATS = 2

# What each failure code means, and what to check, at two depths. Codes not listed get the neutral fallback.
MEANINGS: dict[str, tuple[str, str]] = {
    "INVALID_REQUEST": (
        "The run was asked for something without everything it needs.",
        "The run's parameters didn't satisfy its contract; the message names the missing or invalid one.",
    ),
    "HARNESS_FAILED": (
        "Ananke hit an unexpected error while running.",
        "An exception escaped a run kind; it isn't retryable, so retrying won't help until the cause is fixed.",
    ),
    "ARTIFACT_FAILED": (
        "Something that should have been produced wasn't.",
        "A producer registered a failure, so the run is incomplete; this one is retryable.",
    ),
    "STALE_PLAN": (
        "The code changed between planning and running.",
        "The workspace's source snapshot moved after the plan was prepared; prepare the plan again before running.",
    ),
    "IDEMPOTENCY_CONFLICT": (
        "The same request key was reused for a different request.",
        "An idempotency key was reused with different parameters; use a new key per distinct request.",
    ),
    "UNKNOWN_RUN_KIND": (
        "The run asked for a kind of work this Ananke doesn't offer.",
        "The run kind isn't registered in this Ananke version; check `dev doctor` for the kinds it offers.",
    ),
    "SIMULATED_BACKEND": (
        "Part of the run used a stand-in rather than the real system.",
        "A backend was simulated, so the result is incomplete evidence, not a verified outcome.",
    ),
}
_STOP = set(
    ["a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does", "for", "from", "has", "have", "how", "if", "in", "into", "is", "it", "its", "not", "of", "on", "or", "so", "than", "that", "the", "their", "then", "there", "these", "this", "to", "use", "used", "uses", "using", "was", "what", "when", "where", "which", "while", "with", "you", "your", "it's", "don't", "only", "also", "more", "most", "one", "two"]
)


def pattern(message: str) -> str:
    """A failure message with what changes between runs masked: ids, hashes, numbers, quoted text and paths."""
    text = re.sub(r"run-[0-9a-f]{6,}", "run-…", message)
    text = re.sub(r"\b[0-9a-f]{8,}\b", "…", text)
    text = re.sub(r"'[^']*'|\"[^\"]*\"", "'…'", text)
    text = re.sub(r"(?:[\w.-]+/)+[\w.-]+", "<path>", text)
    return re.sub(r"\b\d+\b", "N", text).strip()


def terms(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9_]{2,}", text.lower())
    return {w for w in words if w not in _STOP}


def _lesson_terms(candidate: dict[str, Any]) -> set[str]:
    body = re.sub(r"^---.*?---", "", candidate.get("skill_md", ""), count=1, flags=re.S)
    return terms(body)


def reviewed(candidate: dict[str, Any]) -> bool:
    """Passed its gate: evaluated, approved after evaluation, nothing outstanding."""
    review = candidate.get("review") or {}
    return not candidate.get("problems") and str(review.get("decision", "")).lower() in (
        "approve",
        "approved",
    )


def feedback(
    runs: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    level: str = "practitioner",
    min_repeats: int = MIN_REPEATS,
) -> dict[str, Any]:
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; choose {', '.join(LEVELS)}")
    if min_repeats < 2:
        raise ValueError("advice needs a failure seen at least twice (min_repeats >= 2)")
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for run in runs:
        for w in run.get("warnings") or []:
            key = (str(run.get("kind")), str(w.get("code")), pattern(str(w.get("message", ""))))
            entry = seen.setdefault(
                key,
                {
                    "kind": key[0],
                    "code": key[1],
                    "pattern": key[2],
                    "runs": [],
                    "examples": [],
                    "retryable": bool(w.get("retryable")),
                    "first_seen": run.get("created_at"),
                    "last_seen": run.get("created_at"),
                },
            )
            if run["run_id"] not in entry["runs"]:
                entry["runs"].append(run["run_id"])
            if w.get("message") not in entry["examples"] and len(entry["examples"]) < 3:
                entry["examples"].append(w.get("message"))
            when = run.get("created_at") or ""
            entry["first_seen"] = min(entry["first_seen"] or when, when)
            entry["last_seen"] = max(entry["last_seen"] or when, when)
    lessons = [(c["name"], _lesson_terms(c)) for c in candidates if reviewed(c)]
    advice, once = [], []
    for entry in sorted(seen.values(), key=lambda e: (-len(e["runs"]), e["code"], e["pattern"])):
        entry["runs"].sort()
        if len(entry["runs"]) < min_repeats:
            once.append(entry)
            continue
        plain, detailed = MEANINGS.get(
            entry["code"],
            (
                f"Ananke reported {entry['code']}.",
                f"Ananke reported {entry['code']}; the message says what failed.",
            ),
        )
        failure_terms = terms(entry["pattern"] + " " + entry["kind"])
        related = sorted(
            (
                {"lesson": name, "shared": sorted(failure_terms & t)}
                for name, t in lessons
                if len(failure_terms & t) >= 2
            ),
            key=lambda r: (-len(r["shared"]), r["lesson"]),
        )
        n = len(entry["runs"])
        if level == "novice":
            text = (
                f"{plain} It happened in {n} runs, so it's worth fixing once rather than retrying."
            )
        elif level == "practitioner":
            text = f"{detailed} Seen in {n} {entry['kind']} runs: “{entry['examples'][0]}”"
        elif level == "principal":
            text = (
                f"{entry['code']} in {n} {entry['kind']} runs between {entry['first_seen']} and {entry['last_seen']}: "
                + (
                    "retryable, so it may be transient."
                    if entry["retryable"]
                    else "not retryable: a fix is needed, not a retry."
                )
            )
        else:
            text = f"One failure has repeated {n} times; {'retrying may clear it' if entry['retryable'] else 'it needs a fix, not a retry'}."
        advice.append(
            {**entry, "count": n, "advice": text, "related_lessons": related, "basis": "observed"}
        )
    return {
        "schema": FEEDBACK_SCHEMA,
        "level": level,
        "min_repeats": min_repeats,
        "runs_read": len(runs),
        "failed_runs": sum(1 for r in runs if r.get("state") == "failed"),
        "advice": advice,
        "seen_once": once,
        "lessons_considered": [name for name, _ in lessons],
    }


def feedback_markdown(fb: dict[str, Any]) -> str:
    lines = [
        "# Feedback from your runs",
        "",
        f"Read {fb['runs_read']} runs ({fb['failed_runs']} failed). Advice is given only for a failure seen in at "
        f"least {fb['min_repeats']} runs.",
        "",
    ]
    if not fb["advice"]:
        lines += [
            "Nothing has repeated, so there's no advice. That's evidence, not praise: it says only what the runs show.",
            "",
        ]
    for i, a in enumerate(fb["advice"], start=1):
        lines += [f"## {i}. `{a['code']}` in {a['kind']} ({a['count']} runs)", "", a["advice"], ""]
        lines.append("Runs: " + ", ".join(f"`{r}`" for r in a["runs"]))
        if a["related_lessons"]:
            lines.append(
                "Reviewed lessons on the same thing: "
                + "; ".join(
                    f"`{r['lesson']}` ({', '.join(r['shared'][:5])})"
                    for r in a["related_lessons"][:3]
                )
            )
        lines.append("")
    if fb["seen_once"]:
        lines += ["## Seen once (no advice yet)", ""]
        lines += [
            f"- `{e['code']}` in {e['kind']}: {e['examples'][0]} (`{e['runs'][0]}`)"
            for e in fb["seen_once"]
        ]
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------- learning graph
def learning_graph(
    candidates: list[dict[str, Any]], *, files: list[str], min_shared: int = 2
) -> dict[str, Any]:
    """Lessons, the runs they came from, the project files they mention, and terms more than one lesson shares."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    vocab: dict[str, set[str]] = {}
    file_set = set(files)
    for c in sorted(candidates, key=lambda c: c["name"]):
        lid = "lesson:" + c["name"]
        status = (
            "reviewed"
            if reviewed(c)
            else "needs review"
            if not (c.get("review") or {})
            else "blocked"
        )
        published = (c.get("provenance") or {}).get("published") or []
        nodes[lid] = {
            "id": lid,
            "kind": "lesson",
            "label": c["name"],
            "status": "published" if published else status,
            "problems": list(c.get("problems") or []),
        }
        for run in sorted((c.get("provenance") or {}).get("runs") or []):
            rid = "run:" + str(run)
            nodes.setdefault(rid, {"id": rid, "kind": "run", "label": str(run)})
            edges.append({"s": lid, "t": rid, "k": "learned from"})
        body = c.get("skill_md", "")
        for path in sorted({p for p in re.findall(r"[\w./-]+\.\w+", body) if p in file_set}):
            fid = "file:" + path
            nodes.setdefault(fid, {"id": fid, "kind": "file", "label": path})
            edges.append({"s": lid, "t": fid, "k": "mentions"})
        vocab[lid] = _lesson_terms(c)
    by_term: dict[str, list[str]] = defaultdict(list)
    for lid, words in vocab.items():
        for w in words:
            by_term[w].append(lid)
    shared_terms = {w: sorted(ls) for w, ls in by_term.items() if len(ls) >= 2}
    lesson_ids = sorted(vocab)
    for i, a in enumerate(lesson_ids):
        for b in lesson_ids[i + 1 :]:
            common = sorted(vocab[a] & vocab[b])
            if len(common) >= min_shared:
                edges.append({"s": a, "t": b, "k": "related", "terms": common[:12]})
    patterns = sorted(
        ({"term": w, "lessons": ls} for w, ls in shared_terms.items()),
        key=lambda p: (-len(p["lessons"]), p["term"]),
    )[:20]
    return {
        "schema": GRAPH_SCHEMA,
        "nodes": sorted(nodes.values(), key=lambda n: (n["kind"], n["id"])),
        "edges": edges,
        "patterns": patterns,
        "lessons": len(vocab),
        "note": "Read-only: promote a reviewed lesson with `ananke learning promote`.",
    }


def graph_mermaid(graph: dict[str, Any]) -> str:
    ids = {n["id"]: f"n{i}" for i, n in enumerate(graph["nodes"])}
    safe = re.compile(r'["<>`|\[\]{}()#;]')
    lines = [f"%% {GRAPH_SCHEMA} · {graph['lessons']} lessons", "flowchart LR"]
    for n in graph["nodes"]:
        label = safe.sub(" ", n["label"])[:60] + (
            f" · {n['status']}" if n["kind"] == "lesson" else ""
        )
        shape = {"lesson": f'(["{label}"])', "run": f'[/"{label}"/]', "file": f'["{label}"]'}[
            n["kind"]
        ]
        lines.append(f"  {ids[n['id']]}{shape}")
    for e in graph["edges"]:
        arrow = "-.-" if e["k"] == "related" else "-->"
        label = e["k"] if e["k"] != "related" else "shares " + ", ".join(e["terms"][:3])
        lines.append(f"  {ids[e['s']]} {arrow}|{safe.sub(' ', label)}| {ids[e['t']]}")
    return "\n".join(lines) + "\n"


__all__ = [
    "FEEDBACK_SCHEMA",
    "GRAPH_SCHEMA",
    "LEVELS",
    "MEANINGS",
    "feedback",
    "feedback_markdown",
    "graph_mermaid",
    "learning_graph",
    "pattern",
    "reviewed",
    "terms",
]
