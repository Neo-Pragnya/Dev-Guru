"""DG-LIFECYCLE-MENTOR: a spec from an idea, each requirement traced to the code and its tests, kept in Ananke."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev_guru import service, spec
from dev_guru.cli import app
from dev_guru.client import connect

SHOP = Path(__file__).resolve().parent.parent / "acceptance" / "fixtures" / "shop"

SPEC = """# Order discounts

## Requirements

- **R1** Orders apply the discount in `discount` before the total is charged.
- **R2** An order item keeps its quantity and price | even <b>here</b>.
- REQ-3: Invoices are emailed to the customer in their own language.

## Acceptance

- R4 isn't a requirement: it's outside the Requirements section.
"""


@pytest.fixture(scope="module")
def shop(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("spec") / "shop"
    shutil.copytree(SHOP, root)
    for pinned in root.rglob("*.pins"):
        pinned.rename(pinned.with_suffix(""))
    (root / "tests" / "test_discount.py").write_text(
        "def test_discount():  # R1: the gold tier pays less\n    assert True\n"
    )
    (root / "SPEC.md").write_text(SPEC)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def test_requirements_come_from_their_section_only() -> None:
    found = spec.requirements(SPEC)
    assert [r["id"] for r in found] == ["R1", "R2", "REQ-3"]
    assert found[0]["line"] == 5 and found[2]["text"].startswith("Invoices")
    assert [
        r["id"]
        for r in spec.requirements("1. nothing\n- **AB-7** Anywhere works without a section\n")
    ] == ["AB-7"]


def test_the_template_traces_once_filled(tmp_path: Path) -> None:
    text = spec.template("Order discounts", "Customers abandon carts.")
    assert "Customers abandon carts." in text
    assert [r["id"] for r in spec.requirements(text)] == ["R1", "R2", "R3"]


def test_each_requirement_is_linked_possible_or_unlinked(shop: Path) -> None:
    tr = service.spec_trace(shop / "SPEC.md", shop)
    by_id = {r["id"]: r for r in tr["requirements"]}
    assert by_id["R1"]["status"] == "linked" and by_id["R1"]["code"][0]["basis"] == "observed"
    assert by_id["R1"]["code"][0]["path"] == "backend/app/services/orders.py"
    assert by_id["R2"]["status"] == "possible" and by_id["R2"]["code"][0]["basis"] == "inferred"
    assert by_id["REQ-3"]["status"] == "unlinked" and by_id["REQ-3"]["code"] == []
    assert by_id["R1"]["tested"] == [{"path": "tests/test_discount.py", "line": 1}]
    assert tr["summary"] == {"linked": 1, "possible": 1, "unlinked": 1, "tested": 1, "total": 3}


def test_the_trace_is_kept_in_the_ananke_run(shop: Path) -> None:
    tr = service.spec_trace(shop / "SPEC.md", shop)
    assert tr["run_id"] and tr["input_digest"].startswith("sha256:")
    names = [a["name"] for a in connect("in-process").run_artifacts(shop, tr["run_id"])]
    assert "spec-trace.json" in names
    kept = json.loads(connect("in-process").read_artifact(shop, tr["run_id"], "spec-trace.json"))
    assert kept["requirements"] == tr["requirements"]


def test_a_level_explains_the_code_behind_each_requirement(shop: Path) -> None:
    tr = service.spec_trace(shop / "SPEC.md", shop, level="novice")
    r1 = next(r for r in tr["requirements"] if r["id"] == "R1")
    assert r1["explanation"][0].startswith("`discount` is a function")
    text = spec.trace_markdown(tr)
    assert "## The code behind each requirement (novice)" in text
    assert (
        "<b>" not in text and "price \\| even" in text
    )  # a requirement's text can't break the table


def test_cli(shop: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "specs" / "x.md"
    res = runner.invoke(
        app, ["spec", "new", "Order discounts", "--idea", "Make it clear.", "-o", str(out)]
    )
    assert res.exit_code == 0 and "Make it clear." in out.read_text()
    res = runner.invoke(app, ["spec", "new", "Order discounts", "-o", str(out)])
    assert res.exit_code == 2 and "already exists" in res.output  # never overwrites
    res = runner.invoke(app, ["spec", "trace", str(shop / "SPEC.md"), "-w", str(shop), "--json"])
    assert res.exit_code == 0 and json.loads(res.stdout)["schema"] == spec.SCHEMA
    empty = tmp_path / "empty.md"
    empty.write_text("# Nothing here\n")
    res = runner.invoke(app, ["spec", "trace", str(empty), "-w", str(shop)])
    assert res.exit_code == 2 and "no requirements" in res.output
