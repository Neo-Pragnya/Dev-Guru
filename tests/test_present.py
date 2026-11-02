from __future__ import annotations

import base64
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev_guru import present
from dev_guru.cli import app

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
DECK = """---
title: Review
theme: paper
lang: en
---

# Review

---

## Steps

+ one
+ two

Notes: say hello

---

## Layout

::: columns
Left
|||
![A dot](dot.png)
:::

---

```chart
{"type": "bar", "title": "Deploys", "labels": ["W1", "W2"], "values": [3, 5], "unit": "deploys"}
```

<script>alert(1)</script>
"""


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "dot.png").write_bytes(PNG)
    return tmp_path


def test_a_deck_is_offline_accessible_and_safe(folder: Path) -> None:
    page = present.build(DECK, folder)
    assert present.check(page) == []
    assert (
        page.count('class="slide"') == 4
        and 'aria-label="2 of 4"' in page
        and 'data-theme="paper"' in page
    )
    assert (
        '<ul class="steps">' in page
        and '<aside class="notes"' in page
        and 'class="cols" style="--n:2"' in page
    )
    assert 'src="data:image/png;base64,' in page and 'alt="A dot"' in page
    assert (
        'role="img" aria-label="Deploys. W1: 3, W2: 5 deploys"' in page
        and '<table class="sr-only">' in page
    )
    assert (
        "<script>alert(1)</script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    )
    assert present.build(DECK, folder) == page  # deterministic


@pytest.mark.parametrize(
    ("deck", "message"),
    [
        ("# x\n\n![](dot.png)\n", "needs alt text"),
        ("# x\n\n![logo](https://example.com/a.png)\n", "must be local files"),
        ("# x\n\n![logo](../outside.png)\n", "not found inside"),
        (
            '# x\n\n```chart\n{"type": "pie", "labels": ["a"], "values": [1]}\n```\n',
            "support type 'bar'",
        ),
        ("", "no slides"),
    ],
)
def test_authoring_errors_are_specific(folder: Path, deck: str, message: str) -> None:
    with pytest.raises(present.DeckError, match=message):
        present.build(deck, folder)


def test_check_catches_unsafe_decks() -> None:
    bad = '<html><img src="https://x/a.png"><script>localStorage.x=1</script></html>'
    problems = present.check(bad)
    assert any("network" in p for p in problems) and any("remote resource" in p for p in problems)
    assert any("lang" in p for p in problems) and any("alt text" in p for p in problems)
    assert any("store data" in p for p in problems)


def test_cli(folder: Path) -> None:
    (folder / "talk.md").write_text(DECK)
    runner = CliRunner()
    res = runner.invoke(app, ["present", str(folder / "talk.md")])
    assert res.exit_code == 0 and (folder / "talk.html").is_file()
    assert runner.invoke(app, ["present", str(folder / "talk.html"), "--check"]).exit_code == 0
    (folder / "bad.md").write_text("# x\n\n![](dot.png)\n")
    bad = runner.invoke(app, ["present", str(folder / "bad.md")])
    assert bad.exit_code == 2 and "![what it shows](dot.png)" in bad.output
    assert (
        runner.invoke(app, ["present", str(folder / "talk.md"), "--theme", "neon"]).exit_code == 2
    )
