"""ADV05, CAP-rich-documentation-01, DG-DOCS-RENDERERS: explanations and documentation grounded in the code."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev_guru import present, service
from dev_guru.cli import app
from dev_guru.explain import LEVELS, ExplainError, check_evidence, docs, explain, parameters

SHOP = Path(__file__).resolve().parent.parent / "acceptance" / "fixtures" / "shop"


@pytest.fixture(scope="module")
def shop(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, service.ExploreResult]:
    root = tmp_path_factory.mktemp("explain") / "shop"
    shutil.copytree(SHOP, root)
    for pinned in root.rglob("*.pins"):
        pinned.rename(pinned.with_suffix(""))
    (root / "backend" / "hostile.py").write_text(
        '"""Says <script>alert(1)</script> and [click](https://evil.example) | pipes."""\n\n'
        "from backend.app.services import orders\n\n\n"
        "def use(order_id, *, retries: dict[str, int] = {}):\n"
        '    """Uses [a link](https://evil.example)."""\n'
        "    return orders\n"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root, service.explore(root)


def test_parameters_respect_brackets() -> None:
    signature = "def f(a: dict[str, int], *, b: tuple[int, int] = (1, 2), **kw) -> X"
    assert parameters(signature) == ["a", "b", "kw"]
    assert parameters("def m(self, x)") == ["x"] and parameters("class C") == []


def test_every_level_explains_a_file_with_sound_evidence(shop) -> None:
    _root, result = shop
    target = next(
        f["path"] for f in result.model["files"] if f["fan_in"] and f["path"].endswith(".py")
    )
    exp = explain(result.model, target)
    assert list(exp["levels"]) == list(LEVELS)
    assert all(exp["levels"][lvl] for lvl in LEVELS)
    assert check_evidence(exp, result.model) == []
    bases = {st["basis"] for sts in exp["levels"].values() for st in sts}
    assert bases <= {"observed", "derived", "inferred"}
    assert explain(result.model, target) == exp  # the same code, the same words


def test_a_symbol_is_explained_with_its_inputs(shop) -> None:
    _root, result = shop
    exp = explain(result.model, "hostile.py:use")
    novice = " ".join(st["text"] for st in exp["levels"]["novice"])
    assert "`order_id`, `retries`" in novice and "line 6" in novice
    assert exp["kind"] == "function" and exp["path"] == "backend/hostile.py"
    assert check_evidence(exp, result.model) == []


def test_one_level_can_be_asked_for() -> None:
    file = {
        "id": "file:a.py",
        "path": "a.py",
        "name": "a.py",
        "package": ".",
        "loc": 1,
        "symbols": [],
        "fan_in": 0,
        "fan_out": 0,
    }
    exp = explain({"files": [file], "symbols": [], "edges": []}, "a.py", levels=("executive",))
    assert list(exp["levels"]) == ["executive"]
    assert "leaf" in exp["levels"]["executive"][0]["text"]


def test_unknown_and_ambiguous_focus_are_refused(shop) -> None:
    _root, result = shop
    with pytest.raises(ExplainError, match="nothing called"):
        explain(result.model, "no_such_thing")
    with pytest.raises(ExplainError, match="matches"):
        explain(result.model, "__init__.py")
    with pytest.raises(ExplainError, match="unknown level"):
        explain(result.model, "hostile.py", levels=("guru",))


@pytest.mark.parametrize("audience", LEVELS)
@pytest.mark.parametrize("detail", list(docs.DETAILS))
def test_documents_for_every_audience_and_depth_link_to_real_lines(
    shop, audience: str, detail: str
) -> None:
    root, result = shop
    doc = docs.build(result.model, result.manifest, audience=audience, detail=detail)
    assert doc["sections"][0]["id"] == "summary" and doc["sections"][-1]["id"] == "limitations"
    out = root / "docs"
    out.mkdir(exist_ok=True)
    text = docs.to_markdown(doc, root=root, out_dir=out)
    assert docs.check_links(text, out) == []
    assert "## Provenance" in text and result.manifest["input_digest"] in text


def _size(doc: dict) -> int:
    return sum(
        len(s["statements"]) + len((s["table"] or {}).get("rows", [])) for s in doc["sections"]
    )


def test_audiences_differ_in_what_they_show(shop) -> None:
    _root, result = shop
    ids = {
        a: {s["id"] for s in docs.build(result.model, result.manifest, audience=a)["sections"]}
        for a in LEVELS
    }
    assert "words" in ids["novice"] and "words" not in ids["principal"]
    assert "packages" in ids["principal"] and "risks" in ids["executive"]
    assert "routes" in ids["practitioner"] and len(ids["executive"]) < len(ids["practitioner"])
    brief = docs.build(result.model, result.manifest, audience="practitioner", detail="brief")
    deep = docs.build(result.model, result.manifest, audience="practitioner", detail="deep")
    assert _size(brief) < _size(deep)


def test_text_from_the_code_cannot_add_links_html_or_cells(shop) -> None:
    root, result = shop
    doc = docs.build(result.model, result.manifest, audience="practitioner", detail="deep")
    text = docs.to_markdown(doc, root=root, out_dir=root)
    assert "<script>" not in text and "&lt;script&gt;" in text
    assert not re.search(r"(?<!\\)\]\(https://evil", text)  # escaped, so it renders as text
    assert docs.check_links(text, root) == []
    row = next(line for line in text.splitlines() if line.startswith("| `backend/hostile.py`"))
    assert row.count(" | ") == 3  # four cells: the docstring's pipe stays inside its cell
    assert docs.escape("`a|b` x|y", cell=True) == "`a\\|b` x\\|y"


def test_slides_become_a_deck_that_passes_its_checks(shop) -> None:
    root, result = shop
    doc = docs.build(result.model, result.manifest, audience="executive")
    page = present.build(docs.to_slides(doc), root)
    assert present.check(page) == [] and "Where the risk is" in page


def test_cli_writes_a_document_with_a_receipt(shop) -> None:
    root, _result = shop
    runner = CliRunner()
    out = root / "notes" / "for-leaders.md"
    res = runner.invoke(app, ["docs", str(root), "--audience", "executive", "-o", str(out)])
    assert res.exit_code == 0, res.output
    receipt = json.loads((out.parent / "for-leaders.md.manifest.json").read_text())
    assert receipt["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert receipt["audience"] == "executive" and receipt["input_digest"].startswith("sha256:")
    res = runner.invoke(app, ["explain", "hostile.py", "-w", str(root), "--json", "-l", "novice"])
    assert res.exit_code == 0 and list(json.loads(res.stdout)["levels"]) == ["novice"]
    res = runner.invoke(app, ["explain", "nothing_here", "-w", str(root)])
    assert res.exit_code == 2 and "INVALID_INPUT" in res.output
    res = runner.invoke(app, ["docs", str(root), "--audience", "guru"])
    assert res.exit_code == 2 and "INVALID_INPUT" in res.output


def test_the_ladder_says_more_than_the_docstring_and_cites_all_of_it(shop) -> None:
    """The measured comparison: a docstring-only baseline says one thing per file; the ladder says more, all cited."""
    _root, result = shop
    files = [f for f in result.model["files"] if f["path"].endswith(".py") and f["doc"]]
    assert files
    for f in files:
        exp = explain(result.model, f["path"])
        statements = [st for sts in exp["levels"].values() for st in sts]
        assert len(statements) > 1
        assert all(st["evidence"] for st in statements)
        assert check_evidence(exp, result.model) == []
