"""Decks and diagrams on request, from inside the workspace only."""

from __future__ import annotations

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
