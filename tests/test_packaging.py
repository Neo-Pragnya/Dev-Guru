"""Boundaries the architecture promises, checked on the source tree."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from dev_guru.client import negotiation

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "dev_guru"


def test_supported_range_matches_the_declared_dependency() -> None:
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    ananke = next(d for d in deps if d.startswith("ananke-plexus"))
    assert ananke == f"ananke-plexus{negotiation.SUPPORTED_ANANKE}"


def test_dex_is_optional_and_never_imported_by_the_core() -> None:
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    assert not any(d.startswith("dex-trove") for d in deps)
    for py in SRC.rglob("*.py"):
        assert not re.search(r"^\s*(import|from)\s+dex_trove", py.read_text(), re.M), py


def test_no_node_runtime_is_needed_to_install() -> None:
    assert not list(SRC.rglob("package.json")) and not list(SRC.rglob("node_modules"))
