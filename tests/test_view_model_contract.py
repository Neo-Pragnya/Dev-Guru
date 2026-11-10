"""DG-VIEW-MODELS: the explorer view model round-trips through the page, keeps stable ids, and invents nothing.

Run against the real harness on the shop fixture, which has routes, tables, quality hotspots and coverage.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from dev_guru import service
from dev_guru.reports import model as view_model
from dev_guru.reports import render

SHOP = Path(__file__).resolve().parent.parent / "acceptance" / "fixtures" / "shop"


def _shop(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    shutil.copytree(SHOP, root)
    for pinned in root.rglob("*.pins"):
        pinned.rename(pinned.with_suffix(""))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _block(page: str, block: str) -> object:
    found = re.search(rf'<script type="application/json" id="{block}">(.*?)</script>', page, re.S)
    assert found, block
    return json.loads(found.group(1))


@pytest.fixture(scope="module")
def shop(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    root = _shop(tmp_path_factory.mktemp("contract"))
    result = service.explore(root)
    return root, {"model": result.model, "manifest": result.manifest}


def test_the_model_round_trips_through_the_page(shop: tuple[Path, dict]) -> None:
    _root, out = shop
    page = render.render(out["model"], out["manifest"])
    expected = {k: v for k, v in out["model"].items() if k != "serve"}
    assert _block(page, "dg-data") == json.loads(json.dumps(expected))
    assert _block(page, "dg-manifest") == json.loads(json.dumps(out["manifest"]))
    assert _block(page, "dg-serve") == json.loads(json.dumps(out["model"]["serve"]))
    assert out["manifest"]["input_digest"] == render.digest(out["model"])


def test_ids_are_stable_across_runs_and_unrelated_edits(
    shop: tuple[Path, dict], tmp_path: Path
) -> None:
    root, out = shop
    again = service.explore(root).model
    assert render.digest(again) == render.digest(out["model"])
    copy = _shop(tmp_path)
    (copy / "backend" / "unrelated_note.py").write_text("NOTE = 1\n")
    edited = service.explore(copy).model
    before = {f["id"] for f in out["model"]["files"]} | {s["id"] for s in out["model"]["symbols"]}
    after = {f["id"] for f in edited["files"]} | {s["id"] for s in edited["symbols"]}
    assert before <= after and after - before == {"file:backend/unrelated_note.py"}


def test_every_reference_points_at_something_real(shop: tuple[Path, dict]) -> None:
    root, out = shop
    m = out["model"]
    files = {f["id"]: f for f in m["files"]}
    symbols = {s["id"]: s for s in m["symbols"]}
    for edge in m["edges"]:
        assert edge["s"] in files or edge["s"] in symbols, edge
        assert edge["t"] in files or edge["t"] in symbols, edge
    for f in m["files"]:
        assert (root / f["path"]).is_file(), f["path"]
        assert set(f["symbols"]) <= set(symbols)
        if f["path"].endswith(".py"):  # a notebook counts its code cells' lines, not its JSON
            assert f["loc"] == len((root / f["path"]).read_text().splitlines())
    for s in m["symbols"]:
        assert s["file"] in files
        if s["source"] and files[s["file"]]["path"].endswith(
            ".py"
        ):  # a snippet is the file's own lines, word for word
            lines = (root / files[s["file"]]["path"]).read_text().splitlines()
            assert s["source"].splitlines()[0] == lines[s["line"] - 1]
    for group in m["insights"].values():
        for item in group:
            for fid in item if isinstance(item, list) else [item]:
                assert fid in files
    for name, _complexity, where in m["repository"]["hotspots"]:
        path, line = where.rsplit(":", 1)
        text = (root / path).read_text().splitlines()
        assert name in text[int(line) - 1], where


def test_findings_keep_unknown_apart_from_none(shop: tuple[Path, dict]) -> None:
    deps = shop[1]["model"]["repository"]["dependencies"]
    assert deps["vulnerabilities"] is None  # not checked, so not "no vulnerabilities"
    assert shop[1]["model"]["repository"]["coverage"]["status"]


def test_a_bounded_model_says_what_it_left_out(
    shop: tuple[Path, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, out = shop
    total = len(out["model"]["symbols"])
    monkeypatch.setattr(view_model, "MAX_SYMBOLS", 2)
    small = service.explore(root).model
    assert len(small["symbols"]) == 2 and small["omitted"]["symbols"] == total - 2
    assert any(f"{total - 2} symbols were omitted" in line for line in small["limitations"])
