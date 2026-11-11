"""ADV16: co-designing a process: walk it, see every way through it, edit it and read it back through Ananke."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev_guru import bpmn
from dev_guru.cli import app
from dev_guru.client import connect

ORDER = """# Order handling

1. Sales: Receive the order
2. Finance: Is the credit good?
   - Yes: go to step 3
   - No: go to step 5
3. Warehouse: Pick and pack
4. Warehouse: Ship the order. End.
5. Sales: Tell the customer
"""

LOOP = """# Review

1. Author: Write the draft
2. Reviewer: Is it ready?
   - Yes: go to step 4
   - No: go to step 3
3. Author: Revise it. Go to step 2.
4. Editor: Publish it. End.
"""


def _model(tmp_path: Path, text: str, name: str = "p.md") -> dict:
    return connect("in-process").process_model(tmp_path, text, name)["model"]


def _shape(model: dict) -> tuple:
    nodes = [(n["kind"], n["name"], n["lane"]) for n in model["nodes"]]
    flows = [(f["source"], f["target"], f["label"]) for f in model["flows"]]
    return nodes, flows


@pytest.mark.parametrize("text", [ORDER, LOOP])
def test_markdown_round_trips_through_ananke(tmp_path: Path, text: str) -> None:
    model = _model(tmp_path, text)
    again = _model(tmp_path, bpmn.to_markdown(model), "again.md")
    assert again["problems"] == [] and _shape(again) == _shape(model)


def test_every_way_through_is_listed_and_loops_end(tmp_path: Path) -> None:
    order = bpmn.paths(_model(tmp_path, ORDER))
    assert len(order) == 2 and all(r[0] == "start" and r[-1].startswith("end") for r in order)
    loop = bpmn.paths(_model(tmp_path, LOOP))
    assert len(loop) == 2  # straight through, and the revision loop back to the review
    (back,) = [r for r in loop if r[-1] in r[:-1]]
    assert back[-1] == "step_2" and back[-2] == "step_3"


def test_steps_carry_the_text_that_follows_a_name(tmp_path: Path) -> None:
    numbered = {s["number"]: s for s in bpmn.steps(_model(tmp_path, LOOP))}
    assert numbered[3]["after"] == " Go to step 2."
    assert numbered[2]["branches"] == ["   - Yes: go to step 4", "   - No: go to step 3"]
    assert (
        bpmn.sentence("Ship it", " End.") == "Ship it. End."
        and bpmn.sentence("Done?", " End.") == "Done? End."
    )


def test_the_viewer_carries_the_walk_and_the_editor_without_letting_text_run(
    tmp_path: Path,
) -> None:
    hostile = ORDER.replace("Receive the order", "<img src=x onerror=alert(1)> </script> & co")
    model = _model(tmp_path, hostile)
    page = bpmn.viewer(model, "<definitions/>")
    assert "<img src=x" not in page and "</script> &" not in page
    data = json.loads(re.search(r'id="process-data">(.*?)</script>', page, re.S).group(1))
    assert data["start"] == "start" and data["steps"][0]["number"] == 1
    assert "<img" in data["names"]["step_1"]  # kept as data, read with textContent
    assert 'id="sim-step"' in page and 'id="save-md"' in page and 'id="name-1"' in page


def test_cli_writes_the_markdown(tmp_path: Path) -> None:
    src = tmp_path / "order.md"
    src.write_text(ORDER)
    out = tmp_path / "order.again.md"
    res = CliRunner().invoke(app, ["bpmn", str(src), "-w", str(tmp_path), "--markdown", str(out)])
    assert res.exit_code == 0, res.output
    assert out.read_text().startswith("# Order handling\n\n1. Sales: Receive the order\n")
