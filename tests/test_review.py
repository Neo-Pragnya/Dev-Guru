"""CAP-code-review-01..04 and CAP-pr-release-01/02: a change reviewed from Git, the graph, reports and the spec."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev_guru import review, service
from dev_guru.cli import app

SARIF = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "Semgrep"}},
            "results": [
                {
                    "ruleId": "unsafe-eval",
                    "level": "error",
                    "message": {"text": "eval of input"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "app/pricing.py"},
                                "region": {"startLine": 2},
                            }
                        }
                    ],
                }
            ],
        }
    ],
}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
        check=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "app").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "app" / "__init__.py").write_text("")
    (root / "app" / "pricing.py").write_text(
        "def price(item):\n    return 1\n\n\ndef tax(x):\n    return x\n"
    )
    (root / "app" / "cart.py").write_text(
        "from app.pricing import price\n\n\ndef total(items):\n    return sum(price(i) for i in items)\n"
    )
    (root / "tests" / "test_cart.py").write_text(
        "from app.cart import total\n\n\ndef test_total():\n    assert total([1]) == 1\n"
    )
    (root / "SPEC.md").write_text(
        "# Pricing\n\n## Requirements\n\n- **R1** Each item's `price` is what the cart totals.\n"
        "- **R2** Prices include tax when the item is taxable.\n"
    )
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    (root / "app" / "pricing.py").write_text(
        "def price(item):\n    return 2  # new pricing\n\n\ndef tax(x):\n    return x\n"
    )
    (root / "semgrep.sarif").write_text(json.dumps(SARIF))
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "Raise the base price")
    return root


def test_changes_come_from_git(repo: Path) -> None:
    ch = review.changes(repo, "main~1")
    assert ch["files"] == ["app/pricing.py", "semgrep.sarif"]
    assert ch["ranges"]["app/pricing.py"] == [(2, 2)]
    assert ch["commits"] == [{"sha": ch["commits"][0]["sha"], "subject": "Raise the base price"}]
    (repo / "app" / "cart.py").write_text((repo / "app" / "cart.py").read_text() + "\n# note\n")
    assert "app/cart.py" in review.changes(repo, "main~1")["files"]  # uncommitted work counts too
    with pytest.raises(review.ReviewError, match="isn't a commit"):
        review.changes(repo, "no-such-branch")


def test_a_review_finds_reach_tests_blocking_and_advice(repo: Path) -> None:
    rv, _result = service.code_review(repo, "main~1", spec=repo / "SPEC.md")
    assert [s["name"] for s in rv["changed"]["symbols"]] == ["price"]  # tax didn't change
    assert [c["id"] for c in rv["reach"]["callers"]] == ["function:app/cart.py:total"]
    assert "app/cart.py" in rv["reach"]["impacted_files"]
    assert rv["retest"]["tests"] == ["tests/test_cart.py"]  # imports a file the change reaches
    assert rv["retest"]["rerun"][0]["command"] == "python -m pytest tests/test_cart.py"
    kinds = [b["kind"] for b in rv["blocking"]]
    assert "code" in kinds  # Semgrep's finding sits on the changed line
    assert any(b["kind"] == "requirement" and "R1" in b["what"] for b in rv["blocking"])
    assert {q["id"] for q in rv["requirements"]} == {"R1"}
    assert rv["verdict"] == "blocked"


def test_a_test_that_names_the_requirement_unblocks_it(repo: Path) -> None:
    (repo / "tests" / "test_cart.py").write_text(
        (repo / "tests" / "test_cart.py").read_text() + "# R1: totals use price\n"
    )
    rv, _ = service.code_review(repo, "main~1", spec=repo / "SPEC.md")
    assert not any(b["kind"] == "requirement" for b in rv["blocking"])
    assert rv["requirements"][0]["tested"]


def test_the_pr_body_is_grounded_in_the_review(repo: Path) -> None:
    rv, _result = service.code_review(repo, "main~1", spec=repo / "SPEC.md")
    body = review.pr_body(rv, revision="abc123", digest="sha256:x")
    assert "- Raise the base price (" in body and "`price` (app/pricing.py:1)" in body
    assert (
        "**R1**" in body and "not tested" in body and "python -m pytest tests/test_cart.py" in body
    )
    assert "## Residual risks" in body and "eval of input" in body


def test_cli_exit_codes(repo: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    pr = tmp_path / "PR.md"
    res = runner.invoke(app, ["review", str(repo), "--base", "main~1", "--pr-body", str(pr)])
    assert (
        res.exit_code == 1
        and "# Review: blocked" in res.output
        and pr.read_text().startswith("## Summary")
    )
    res = runner.invoke(app, ["review", str(repo), "--base", "main~1", "--json"])
    assert json.loads(res.stdout)["schema"] == review.SCHEMA
    res = runner.invoke(app, ["review", str(repo), "--base", "nope"])
    assert res.exit_code == 2 and "INVALID_INPUT" in res.output
    (repo / "semgrep.sarif").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "drop report")
    res = runner.invoke(app, ["review", str(repo), "--base", "main~2"])
    assert res.exit_code == 0 and "ready for review" in res.output
