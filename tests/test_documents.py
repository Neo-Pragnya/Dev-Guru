"""Decks and diagrams on request, from inside the workspace only."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dev_guru.gateway import documents


def test_a_deck_comes_back_and_nothing_is_written(tmp_path: Path) -> None:
    (tmp_path / "talk.md").write_text("# One\n\n---\n\n# Two\n")
    before = sorted(tmp_path.rglob("*"))
    done = documents.build(tmp_path, "talk.md", "deck")
    assert done["name"] == "talk.html" and "<html" in done["content"].lower()
    assert sorted(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("path", ["../outside.md", "/etc/hosts.md", "talk.txt", "missing.md"])
def test_only_markdown_in_the_workspace_is_read(tmp_path: Path, path: str) -> None:
    (tmp_path / "talk.txt").write_text("x")
    (tmp_path.parent / "outside.md").write_text("# secret")
    with pytest.raises(documents.DocumentError):
        documents.build(tmp_path, path, "deck")


def test_a_link_cant_lead_out_of_the_workspace(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.md").write_text("# secret")
    (root / "link.md").symlink_to(tmp_path / "secret.md")
    with pytest.raises(documents.DocumentError):
        documents.build(root, "link.md", "deck")
    assert documents.listed(root) == []


def test_the_list_skips_hidden_folders_and_dependencies(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("# A\n")
    for skipped in (".git", "node_modules"):
        (tmp_path / skipped).mkdir()
        (tmp_path / skipped / "b.md").write_text("# B\n")
    assert [d["path"] for d in documents.listed(tmp_path)] == ["docs/a.md"]


def test_an_unknown_kind_is_refused(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A\n")
    with pytest.raises(documents.DocumentError):
        documents.build(tmp_path, "a.md", "video")


ORDER = "# Orders\n\n1. Sales: Receive it\n2. Finance: Is it good?\n   - Yes: go to step 3\n   - No: end\n3. Warehouse: Ship it\n"


def test_a_process_comes_back_as_an_offline_viewer(tmp_path: Path) -> None:
    from dev_guru.client import connect

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "p.md").write_text(ORDER)
    done = documents.build(tmp_path, "p.md", "process", connect("in-process"))
    assert done["name"] == "p.process.html" and done["problems"] == []
    page = done["content"]
    assert "Warehouse" in page and "bpmn:definitions" in page and "default-src 'none'" in page
    assert 'isExecutable="false"' in page.replace("&quot;", '"')


def test_hostile_process_text_stays_text() -> None:
    from dev_guru import bpmn

    model = {
        "name": "<script>alert(1)</script>",
        "source": "",
        "lanes": ["<b>x</b>"],
        "nodes": [
            {
                "id": 'n"><img>',
                "kind": "task",
                "name": "<img src=x onerror=alert(1)>",
                "lane": "<b>x</b>",
                "evidence": "</title><script>",
            }
        ],
        "flows": [],
        "problems": ["<script>bad</script>"],
    }
    page = bpmn.viewer(model, "<bpmn></script><script>alert(1)</script>")
    assert "<script>alert" not in page and "<img src=x" not in page and "<b>x" not in page
    assert page.count("<script>") == 1


def test_a_process_with_a_gap_says_so(tmp_path: Path) -> None:
    from dev_guru.client import connect

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "p.md").write_text("1. A: Do it. Go to step 9\n")
    done = documents.build(tmp_path, "p.md", "process", connect("in-process"))
    assert any("doesn't exist" in p for p in done["problems"])
    assert 'id="problems"' in done["content"]
