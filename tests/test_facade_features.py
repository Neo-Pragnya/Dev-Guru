"""Dev Guru over the Ananke app facade: run-linked reports, source discovery, learning review, Dex-free path."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from dev_guru import service
from dev_guru.cli import app
from dev_guru.client import connect

runner = CliRunner()


def test_the_report_is_registered_in_the_ananke_run(project: Path, tmp_path: Path) -> None:
    client = connect()
    result = service.explore(project, client=client)
    assert (
        result.run_id.startswith("run-")
        and result.manifest["ananke_run"]["run_id"] == result.run_id
    )
    page, _ = service.export_html(result, tmp_path / "explorer.html", client=client)
    from ananke.plexus.app import AppFacade

    refs = {a["name"]: a for a in AppFacade(project).list_artifacts(result.run_id)}
    assert refs["explorer.html"]["producer"] == "dev-guru/explorer-html@1"
    assert refs["explorer.html"]["input_refs"][0] == "graph-snapshot.json"
    assert AppFacade(project).read_artifact(result.run_id, "explorer.html") == page.read_bytes()


def _sources(project: Path) -> None:
    skills = project / "team-skills" / "deploy-check"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\nname: deploy-check\ndescription: Check a deploy before release\nversion: 1.0.0\n---\nSteps.\n"
    )
    (project / ".ananke").mkdir(exist_ok=True)
    (project / ".ananke" / "config.toml").write_text(
        '[capability_sources.team]\nroot = "team-skills"\nnamespace = "acme"\nwritable = true\n'
    )


def test_sources_are_discovered_through_the_provider_port(project: Path, tmp_path: Path) -> None:
    _sources(project)
    res = runner.invoke(
        app,
        [
            "sources",
            "deploy",
            "-w",
            str(project),
            "--json",
            "--html",
            str(tmp_path / "picker.html"),
        ],
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert [r["identity"] for r in rows] == ["team:acme/deploy-check"] and rows[0][
        "version"
    ] == "1.0.0"
    page = (tmp_path / "picker.html").read_text()
    assert "connect-src 'none'" in page and "team:acme/deploy-check" in page


def test_learning_review_shows_gate_evaluation_and_diff(project: Path, tmp_path: Path) -> None:
    from ananke.plexus.learning import capture

    _sources(project)
    capture(
        project,
        "deploy-check",
        description="Check a deploy before release, with a rollback plan. Use before every release.",
        body="Steps, plus a rollback plan. <script>alert(1)</script>",
        cases=[
            {"id": "p", "kind": "positive", "command": "true"},
            {"id": "r", "kind": "regression", "command": "true"},
        ],
    )
    out = tmp_path / "review.html"
    res = runner.invoke(
        app, ["learning", "review", "deploy-check", "-w", str(project), "-o", str(out), "--json"]
    )
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert "not evaluated yet" in data["problems"] and "not reviewed" in data["problems"]
    [dest] = data["destinations"]
    assert dest["source"] == "team" and dest["writable"] and dest["existing_version"] == "1.0.0"
    assert "+Steps, plus a rollback plan." in dest["diff"] and "-Steps." in dest["diff"]
    page = out.read_text()
    assert "<script>alert(1)</script>" not in page and "connect-src 'none'" in page
    missing = runner.invoke(app, ["learning", "review", "nope", "-w", str(project)])
    assert missing.exit_code == 1


def test_explore_without_troves_never_imports_dex(project: Path) -> None:
    code = (
        "import sys; from pathlib import Path; from dev_guru import service; from dev_guru.client import connect; "
        f"r = service.explore(Path({str(project)!r}), client=connect()); "
        "print(bool(r.run_id), any(m.startswith('dex_trove') for m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.split()
    assert out == ["True", "False"]
