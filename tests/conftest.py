from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A tiny Python project for the real harness to analyse."""
    root = tmp_path / "shop"
    (root / "shop").mkdir(parents=True)
    (root / "shop" / "__init__.py").write_text("")
    (root / "shop" / "cart.py").write_text(
        "from shop.prices import price\n\n\nclass Cart:\n    pass\n\n\ndef total(items):\n    return sum(price(i) for i in items)\n"
    )
    (root / "shop" / "prices.py").write_text("import json\n\n\ndef price(item):\n    return 1\n")
    return root
