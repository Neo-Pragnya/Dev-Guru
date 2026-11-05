"""What dev explore draws must be the same on every operating system. CI runs this on Linux, macOS and Windows.

On Windows, paths once came back with backslashes: the constellation had no links and the flow one package, and the
command said it had succeeded. These check the report itself, and the warning that would have said so.
"""

from __future__ import annotations

import itertools
import shutil
import subprocess
from pathlib import Path

import pytest

from dev_guru import health, service
from dev_guru.client.port import GraphData, GraphEdgeData, GraphNodeData

SHOP = Path(__file__).resolve().parents[1] / "acceptance" / "fixtures" / "shop"


@pytest.fixture
def shop(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    shutil.copytree(
        SHOP, root, ignore=shutil.ignore_patterns(".ananke", "__pycache__", "node_modules")
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def test_the_report_links_files_and_finds_packages_on_every_platform(shop: Path) -> None:
    result = service.explore(shop)
    model = result.model
    assert not [f["id"] for f in model["files"] if "\\" in f["id"] or "\\" in f["path"]]
    imports = [e for e in model["edges"] if e["k"] == "imports"]
    assert len(imports) >= 5, "the constellation would have no links"
    assert len(model["packages"]) >= 4, "the flow would have one package"
    assert "file:backend/app/services/orders.py" in {f["id"] for f in model["files"]}


def _graph(paths: list[str], *, resolved: bool) -> GraphData:
    nodes = [
        GraphNodeData(id=f"file:{p}", kind="file", name=p.rsplit("/", 1)[-1], path=p) for p in paths
    ]
    edges = [
        GraphEdgeData(
            source=f"file:{a}",
            target=f"module:{b}",
            kind="imports",
            resolved_target=f"file:{b}" if resolved else "",
        )
        for a, b in itertools.pairwise(paths)
    ]
    return GraphData(snapshot_id="s", provider="t", ananke_version=None, nodes=nodes, edges=edges)


def test_backslashes_say_why_the_picture_is_empty() -> None:
    paths = [f"pkg\\m{i}.py" for i in range(25)]
    said = health.problems(_graph(paths, resolved=False), {"packages": [{"id": "."}]})
    assert any("backslashes" in s for s in said)
    assert any("No import" in s for s in said)
    assert any("one package" in s for s in said)


def test_a_healthy_graph_says_nothing() -> None:
    paths = [f"pkg{i % 5}/m{i}.py" for i in range(25)]
    assert (
        health.problems(
            _graph(paths, resolved=True), {"packages": [{"id": str(i)} for i in range(5)]}
        )
        == []
    )
