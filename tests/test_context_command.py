"""dev context: a small map, through the real harness."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from dev_guru.cli import app

runner = CliRunner()


def project(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "core.py").write_text("def add(a, b):\n    return a + b\n")
    return tmp_path


def test_the_map_is_small_and_names_what_to_do_next(tmp_path: Path) -> None:
    result = runner.invoke(app, ["context", str(project(tmp_path)), "--budget", "400"])
    assert result.exit_code == 0, result.output
    assert "repository map" in result.output and "Next:" in result.output
    assert len(result.output) // 4 < 500


def test_tools_says_what_is_ready_and_keeps_serena_apart(tmp_path: Path) -> None:
    result = runner.invoke(app, ["context", str(project(tmp_path)), "--tools"])
    assert result.exit_code == 0, result.output
    tools = json.loads(result.output)["tools"]
    assert tools["map"]["ready"] is True and "GPL" in tools["serena"]["licence"]


def test_a_silly_budget_is_a_clean_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["context", str(project(tmp_path)), "--budget", "1"])
    assert result.exit_code != 0 and "Traceback" not in result.output
