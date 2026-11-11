"""CAP-code-knowledge-graph-04: bounded, expandable subgraphs exported as Mermaid and SVG."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev_guru import GuruClient
from dev_guru.cli import app
from dev_guru.diagram import svg_problems
from dev_guru.reports import subgraph


def _model() -> dict:
    """A hub file imported by eight others, a chain off one of them, and a symbol call."""
    files = [{"id": "file:hub.py", "path": "hub.py", "package": "."}]
    edges = []
    for i in range(8):
        files.append({"id": f"file:pkg/m{i}.py", "path": f"pkg/m{i}.py", "package": "pkg"})
        edges.append(
            {"s": f"file:pkg/m{i}.py", "t": "file:hub.py", "k": "imports", "o": "extracted"}
        )
    files.append({"id": "file:pkg/deep.py", "path": "pkg/deep.py", "package": "pkg"})
    edges.append({"s": "file:pkg/deep.py", "t": "file:pkg/m0.py", "k": "imports", "o": "extracted"})
    symbols = [
        {"id": "function:hub.py:run", "name": "run", "kind": "function", "file": "file:hub.py"},
        {"id": "function:pkg/m0.py:go", "name": "go", "kind": "function", "file": "file:pkg/m0.py"},
    ]
    edges.append(
        {
            "s": "function:pkg/m0.py:go",
            "t": "function:hub.py:run",
            "k": "calls",
            "o": "inferred",
            "line": 3,
        }
    )
    return {"project": {"name": "demo"}, "files": files, "symbols": symbols, "edges": edges}


def test_focus_depth_and_budget_bound_the_drawing() -> None:
    sub = subgraph.select(_model(), focus="hub.py", depth=1, budget=4)
    assert sub["nodes"][0]["id"] == "file:hub.py" and sub["nodes"][0]["focus"]
    assert len(sub["nodes"]) == 4 and sub["omitted"]["truncated_by_budget"]
    assert sub["nodes"][0]["hidden"] == 5  # eight neighbours, three drawn
    assert sub["expand"] == "dev graph --level file --focus file:hub.py --depth 2 --budget 8"


def test_expanding_reaches_the_next_ring() -> None:
    one = subgraph.select(_model(), focus="hub.py", depth=1, budget=40)
    two = subgraph.select(_model(), focus="hub.py", depth=2, budget=40)
    assert "file:pkg/deep.py" not in {n["id"] for n in one["nodes"]}
    assert "file:pkg/deep.py" in {n["id"] for n in two["nodes"]}
    assert not two["expand"] and two["omitted"]["nodes"] == 0


def test_levels_merge_and_count_edges() -> None:
    pkg = subgraph.select(_model(), level="package")
    (edge,) = pkg["edges"]
    assert (edge["s"], edge["t"], edge["kinds"]) == (
        "package:pkg",
        "package:.",
        {"imports": 8, "calls": 1},
    )
    assert subgraph.edge_label(edge) == "imports x8 · calls" and edge["origin"] == "extracted"
    sym = subgraph.select(_model(), level="symbol")
    assert sym["edges"][0]["origin"] == "inferred"


def test_a_focus_must_be_unambiguous() -> None:
    model = _model()
    model["files"].append({"id": "file:x/m0.py", "path": "x/m0.py", "package": "x"})
    assert subgraph.select(model, focus="hub.py")["focus"] == "file:hub.py"  # an exact path wins
    with pytest.raises(subgraph.SubgraphError, match="matches 2 nodes"):
        subgraph.select(model, focus="m0.py")
    with pytest.raises(subgraph.SubgraphError, match="nothing called"):
        subgraph.select(model, focus="missing.py")
    with pytest.raises(subgraph.SubgraphError, match="budget"):
        subgraph.select(model, budget=0)


def test_mermaid_is_deterministic_and_names_cannot_inject_syntax() -> None:
    model = _model()
    model["files"][1]["path"] = 'pkg/evil"] --> X[pwned'
    text = subgraph.to_mermaid(subgraph.select(model, focus="hub.py"))
    assert text == subgraph.to_mermaid(subgraph.select(model, focus="hub.py"))
    assert text.splitlines()[1] == "flowchart LR"
    assert "pwned" in text and '"]' not in text.replace('"])', "").replace(
        '"]\n', "\n"
    )  # label stays one label
    assert "-->|imports|" in text


def test_svg_is_safe_and_marks_inferred_edges() -> None:
    model = _model()
    model["symbols"][0]["name"] = "<script>alert(1)</script>"
    svg = subgraph.to_svg(subgraph.select(model, level="symbol"))
    assert svg_problems(svg) == [] and "<script>alert" not in svg
    assert 'class="edge hyp"' in svg and "inferred through imports" in svg


def test_cli_and_sdk_draw_the_real_graph(project: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out = runner.invoke(app, ["graph", str(project), "--focus", "cart.py"])
    assert out.exit_code == 0, out.output
    assert "flowchart LR" in out.stdout and "shop/prices.py" in out.stdout
    svg = tmp_path / "g.svg"
    out = runner.invoke(app, ["graph", str(project), "-f", "svg", "-o", str(svg), "--static"])
    assert out.exit_code == 0 and svg_problems(svg.read_text()) == []
    out = runner.invoke(app, ["graph", str(project), "-f", "json", "--level", "symbol"])
    assert json.loads(out.stdout)["schema"] == subgraph.SCHEMA
    bad = runner.invoke(app, ["graph", str(project), "--focus", "nope.py"])
    assert bad.exit_code == 2 and "INVALID_INPUT" in bad.output
    with GuruClient(project) as guru:
        path = guru.export(
            guru.explore(), output=tmp_path / "g.mmd", format="mermaid", focus="cart.py"
        )
    assert path.read_text().startswith("%% dev-guru/subgraph@1")
