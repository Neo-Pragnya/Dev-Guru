"""CAP-bdd-tdd-01..04 and CAP-auto-sdd-02/04: plan, failing tests first, verified evidence, lock and drift."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev_guru import service
from dev_guru.cli import app
from dev_guru.spec import plan as planning

SPEC = """# Pricing

## Requirements

- **R1** The cart total comes from `price` for each item.
- **R2** A discount never makes the total negative, after R1.
- **R3** The pricing API returns 404 for an unknown item.
- **R4** Only an admin role can change prices.
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "app").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "app" / "__init__.py").write_text("")
    (root / "app" / "pricing.py").write_text("def price(item):\n    return 1\n")
    (root / "tests" / "test_pricing.py").write_text(
        "from app.pricing import price\n\n\ndef test_R1_price():  # R1\n    assert price('x') == 1\n\n\n"
        "def test_R2_never_negative():  # R2\n    assert price('x') - 5 >= 0\n"
    )
    (root / "SPEC.md").write_text(SPEC)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def test_requirements_are_classified_and_ordered(project: Path) -> None:
    tr, result = service.spec_context(project / "SPEC.md", project)
    p = planning.plan(tr, result.model)
    kinds = {r["id"]: r["kinds"] for r in p["requirements"]}
    assert "invariant" in kinds["R2"] and "interface" in kinds["R3"] and "security" in kinds["R4"]
    risk = {r["id"]: r["risk"] for r in p["requirements"]}
    assert risk["R2"] == "high" and risk["R4"] == "high" and risk["R3"] in ("medium", "high")
    r2 = next(r for r in p["requirements"] if r["id"] == "R2")
    assert r2["after"] == ["R1"] and any("property test" in t for t in r2["tests"])
    order = [t["requirement"] for t in p["tasks"]]
    assert order.index("R1") < order.index("R2")
    assert "write a failing test for R3" in [t["task"] for t in p["tasks"]]
    assert planning.classify("Shows the order") == ["behaviour"]


def test_failing_tests_are_written_first_and_never_overwrite(project: Path) -> None:
    tr, result = service.spec_context(project / "SPEC.md", project)
    p = planning.plan(tr, result.model)
    out = project / "tests" / "spec"
    written = planning.skeletons(p, out)
    assert sorted(w.name for w in written) == [
        "test_r3.py",
        "test_r4.py",
    ]  # R1 and R2 already have tests
    text = (out / "test_r3.py").read_text()
    assert "pytest.fail(\"R3 isn't implemented yet" in text and "# R3:" in text
    (out / "test_r3.py").write_text("# mine\n")
    assert planning.skeletons(p, out) == [] and (out / "test_r3.py").read_text() == "# mine\n"
    feature = planning.skeletons(p, project / "features", style="gherkin")
    assert any(f.read_text().startswith("Feature: R4") for f in feature)


def test_verify_runs_the_named_tests_and_requires_code_tests_and_a_pass(project: Path) -> None:
    tr, _ = service.spec_context(project / "SPEC.md", project)
    out = planning.verify(tr, project)
    status = {r["id"]: r for r in out["requirements"]}
    assert status["R1"]["done"] and status["R1"]["why"] == "linked, tested and passing"
    assert not status["R2"]["done"] and status["R2"]["why"] == "tests fail"
    assert not status["R3"]["done"] and status["R3"]["why"] == "no test names it"
    assert out["done"] == 1 and out["total"] == 4


def test_lock_and_drift(project: Path) -> None:
    tr, _ = service.spec_context(project / "SPEC.md", project)
    locked = planning.lock(tr, project)
    assert (
        set(locked["requirements"]) == {"R1", "R2", "R3", "R4"}
        and "app/pricing.py" in locked["code"]
    )
    assert planning.drift(locked, tr, project)["clean"]
    (project / "app" / "pricing.py").write_text("def price(item):\n    return 2\n")
    (project / "SPEC.md").write_text(
        SPEC.replace("an admin role", "an owner role") + "- **R5** Prices show two decimals.\n"
    )
    tr2, _ = service.spec_context(project / "SPEC.md", project)
    d = planning.drift(locked, tr2, project)
    assert d == {
        "added": ["R5"],
        "removed": [],
        "reworded": ["R4"],
        "code_changed": ["app/pricing.py"],
        "clean": False,
    }


def test_cli(project: Path) -> None:
    runner = CliRunner()
    spec = str(project / "SPEC.md")
    res = runner.invoke(app, ["spec", "plan", spec, "-w", str(project), "--json"])
    assert res.exit_code == 0 and json.loads(res.stdout)["schema"] == planning.PLAN_SCHEMA
    res = runner.invoke(
        app, ["spec", "tests", spec, "-w", str(project), "--out", str(project / "tests" / "spec")]
    )
    assert res.exit_code == 0 and "2 failing test file(s)" in res.output
    res = runner.invoke(app, ["spec", "verify", spec, "-w", str(project)])
    assert res.exit_code == 1 and "done  R1" in res.output
    res = runner.invoke(app, ["spec", "lock", spec, "-w", str(project)])
    assert res.exit_code == 0 and (project / "SPEC.md.lock.json").is_file()
    res = runner.invoke(app, ["spec", "trace", spec, "-w", str(project), "--check-lock"])
    assert res.exit_code == 0 and "No drift." in res.output
    (project / "app" / "pricing.py").write_text("def price(item):\n    return 3\n")
    res = runner.invoke(app, ["spec", "trace", spec, "-w", str(project), "--check-lock"])
    assert res.exit_code == 1 and "code changed: app/pricing.py" in res.output
