"""ADV18 (advice from repeated failures) and ADV08 (the learning graph), against real Ananke runs and candidates."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev_guru import mentor, service
from dev_guru.cli import app
from dev_guru.client import connect

SHOP = Path(__file__).resolve().parent.parent / "acceptance" / "fixtures" / "projects" / "shop"


def _lesson(root: Path, name: str, body: str, runs: list[str], *, approve: bool) -> None:
    from ananke.plexus import learning

    folder = learning.capture(
        root,
        name,
        description=f"How to handle {name.replace('-', ' ')} when graph impact runs fail in this project.",
        body=body,
        cases=[
            {"id": "p", "kind": "positive", "command": "python -c pass"},
            {"id": "r", "kind": "regression", "command": "python -c pass"},
        ],
        runs=runs,
    )
    evaluation = json.loads((folder / "evaluation.json").read_text())
    evaluation["finished_at"] = datetime.now(UTC).isoformat()
    for case in evaluation["cases"]:
        case["passed"] = True
    (folder / "evaluation.json").write_text(json.dumps(evaluation))
    if approve:
        learning.review(folder, approve=True, reviewer="tester", reason="checked against the runs")


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[str]]:
    root = tmp_path_factory.mktemp("mentor") / "shop"
    shutil.copytree(SHOP, root)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    client = connect("in-process")
    run_ids = []
    for i in range(3):  # the same mistake three times: graph.impact without changed_files
        run = client.submit_run(root, "graph.impact", {"symbol": f"s{i}"}, f"repeat-{i}")
        run_ids.append(client.drive_run(root, run["run_id"])["run_id"])
    once = client.submit_run(root, "workflow.run", {}, "once")  # a different failure, seen once
    client.drive_run(root, once["run_id"])
    _lesson(
        root,
        "impact-needs-changed-files",
        "Graph impact needs parameters changed_files: pass a non-empty list of paths, such as shop/cart.py.",
        run_ids[:2],
        approve=True,
    )
    _lesson(
        root,
        "changed-files-from-git",
        "Collect changed_files for graph impact from git diff, then pass the paths, such as shop/prices.py.",
        run_ids[2:],
        approve=False,
    )
    return root, run_ids


def test_patterns_mask_what_changes_between_runs() -> None:
    a = mentor.pattern("run-0123abcd9 failed reading 'x.py' at shop/cart.py line 42")
    b = mentor.pattern("run-ffff00001 failed reading 'y.py' at shop/prices.py line 7")
    assert a == b == "run-… failed reading '…' at <path> line N"


def test_advice_only_for_repeated_failures_with_their_runs(workspace) -> None:
    root, run_ids = workspace
    fb = service.mentor_feedback(root)
    assert fb["runs_read"] == 4 and fb["failed_runs"] == 4
    (advice,) = fb["advice"]
    assert advice["code"] == "INVALID_REQUEST" and advice["count"] == 3
    assert advice["runs"] == sorted(run_ids) and advice["basis"] == "observed"
    assert "changed_files" in advice["advice"]
    assert [r["lesson"] for r in advice["related_lessons"]] == [
        "impact-needs-changed-files"
    ]  # only reviewed ones
    assert len(fb["seen_once"]) == 1  # the empty list: a different message, seen once, no advice


def test_levels_change_the_words_not_the_evidence(workspace) -> None:
    root, _ = workspace
    texts = {lvl: service.mentor_feedback(root, level=lvl)["advice"][0] for lvl in mentor.LEVELS}
    assert len({t["advice"] for t in texts.values()}) == 4
    assert len({tuple(t["runs"]) for t in texts.values()}) == 1
    assert "not retryable" in texts["principal"]["advice"]


def test_a_single_failure_is_never_advice(workspace) -> None:
    root, _ = workspace
    fb = service.mentor_feedback(root, min_repeats=4)
    assert fb["advice"] == [] and len(fb["seen_once"]) == 2
    assert "no advice" in mentor.feedback_markdown(fb)
    with pytest.raises(Exception, match="at least twice"):
        service.mentor_feedback(root, min_repeats=1)


def test_the_learning_graph_links_lessons_runs_files_and_shared_terms(workspace) -> None:
    root, run_ids = workspace
    graph = service.learning_map(root)
    lessons = {n["label"]: n for n in graph["nodes"] if n["kind"] == "lesson"}
    assert lessons["impact-needs-changed-files"]["status"] == "reviewed"
    assert lessons["changed-files-from-git"]["status"] == "needs review"
    learned = {(e["s"], e["t"]) for e in graph["edges"] if e["k"] == "learned from"}
    assert ("lesson:impact-needs-changed-files", "run:" + run_ids[0]) in learned
    mentions = {e["t"] for e in graph["edges"] if e["k"] == "mentions"}
    assert mentions == {"file:shop/cart.py", "file:shop/prices.py"}
    related = [e for e in graph["edges"] if e["k"] == "related"]
    assert related and "changed_files" in related[0]["terms"]
    assert any(p["term"] == "changed_files" for p in graph["patterns"])
    text = mentor.graph_mermaid(graph)
    assert text.splitlines()[1] == "flowchart LR" and "shares" in text


def test_cli(workspace) -> None:
    root, _ = workspace
    runner = CliRunner()
    res = runner.invoke(app, ["mentor", str(root), "--level", "novice"])
    assert res.exit_code == 0 and "worth fixing once" in res.output
    res = runner.invoke(app, ["mentor", str(root), "--json"])
    assert json.loads(res.stdout)["schema"] == mentor.FEEDBACK_SCHEMA
    res = runner.invoke(app, ["mentor", str(root), "--level", "guru"])
    assert res.exit_code == 2 and "INVALID_INPUT" in res.output
    res = runner.invoke(app, ["learning", "graph", "-w", str(root), "-f", "json"])
    assert res.exit_code == 0 and json.loads(res.stdout)["lessons"] == 2
