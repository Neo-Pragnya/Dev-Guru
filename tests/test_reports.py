"""The explorer: the view model is a faithful, deterministic projection, and the HTML is offline and safe."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from dev_guru import GuruClient, errors, service
from dev_guru.client.port import GraphData, GraphEdgeData, GraphNodeData
from dev_guru.reports import model, render


def _graph() -> GraphData:
    n = GraphNodeData
    e = GraphEdgeData
    return GraphData(
        snapshot_id="s1",
        provider="native",
        ananke_version="0.3.12",
        nodes=[
            n(
                id="file:a/x.py",
                kind="file",
                name="x.py",
                path="a/x.py",
                metadata={"module": "a.x", "loc": 10},
            ),
            n(
                id="file:a/y.py",
                kind="file",
                name="y.py",
                path="a/y.py",
                metadata={"module": "a.y", "loc": 5},
            ),
            n(id="file:main.py", kind="file", name="main.py", path="main.py", metadata={"loc": 3}),
            n(
                id="function:a/x.py:f",
                kind="function",
                name="f",
                path="a/x.py",
                metadata={"line": 1, "end_line": 2, "signature": "def f()"},
            ),
            n(
                id="function:a/y.py:g",
                kind="function",
                name="g",
                path="a/y.py",
                metadata={"line": 1, "end_line": 1},
            ),
        ],
        edges=[
            e(source="file:a/x.py", target="function:a/x.py:f", kind="owns"),
            e(source="file:a/y.py", target="function:a/y.py:g", kind="owns"),
            e(source="file:a/x.py", target="module:a.y", kind="imports"),
            e(source="file:a/y.py", target="module:a.x", kind="imports"),  # a cycle
            e(source="file:main.py", target="module:a.x", kind="imports"),
            e(source="file:main.py", target="module:requests", kind="imports"),
            e(
                source="function:a/x.py:f",
                target="function:a/y.py:g",
                kind="calls",
                origin="inferred",
                location="a/x.py:2",
            ),
        ],
    )


def test_view_model_projects_the_graph(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.py").write_text("def f():\n    return g()\n")
    m = model.build(_graph(), tmp_path, project_name="demo")
    assert m["schema"] == "dev-guru/explorer@1"
    assert m["project"] == {
        "name": "demo",
        "files": 3,
        "packages": 2,
        "symbols": 2,
        "loc": 18,
        "imports": 3,
        "calls": 1,
        "external": 1,
    }
    x = next(f for f in m["files"] if f["path"] == "a/x.py")
    assert (x["fan_in"], x["fan_out"]) == (2, 1)
    assert m["insights"]["most_depended"][0] == "file:a/x.py"
    assert m["insights"]["entry_points"] == ["file:main.py"]
    assert m["insights"]["cycles"] == [["file:a/x.py", "file:a/y.py"]]
    assert m["external"] == [{"name": "requests", "importers": ["file:main.py"]}]
    f = next(s for s in m["symbols"] if s["name"] == "f")
    assert f["source"] == "def f():\n    return g()" and f["calls_out"] == 1
    assert (
        next(f for f in m["files"] if f["path"] == "main.py")["module"] == "main"
    )  # derived when missing


def test_view_model_is_deterministic(tmp_path: Path) -> None:
    assert render.digest(model.build(_graph(), tmp_path)) == render.digest(
        model.build(_graph(), tmp_path)
    )


def test_embedded_json_can_never_close_the_script() -> None:
    out = render.safe_json({"doc": "</script><script>alert(1)</script> & " + chr(0x2028)})
    assert "<" not in out and ">" not in out and "&" not in out and chr(0x2028) not in out
    assert json.loads(out)["doc"].startswith("</script>")


def test_html_is_offline_and_traceable(tmp_path: Path) -> None:
    m = model.build(_graph(), tmp_path, project_name="demo")
    man = render.manifest(m, workspace=tmp_path, ananke_version="0.3.12", snapshot_id="s1")
    page = render.render(m, man)
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", page), "no external resources"
    assert "connect-src 'none'" in page  # the page itself forbids network access
    assert page.count("</script>") == 3  # only the page's own three script blocks
    assert man["input_digest"] == render.digest(m) and man["renderer"] == render.RENDERER


def test_reproducible_timestamp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    m = model.build(_graph(), tmp_path)
    assert render.manifest(m, workspace=tmp_path, ananke_version=None, snapshot_id="s")[
        "generated_at"
    ].startswith("1970-01-01")


def test_explore_against_the_real_harness(project: Path, tmp_path: Path) -> None:
    with GuruClient(project) as guru:
        result = guru.explore(name="shop")
        page = guru.export(result, output=tmp_path / "out" / "shop.html")
    assert page.is_file() and (tmp_path / "out" / "shop.html.manifest.json").is_file()
    assert result.model["project"]["files"] == 3 and result.manifest["transport"] == "in-process"
    assert "shop" in page.read_text()


def test_an_empty_workspace_is_an_error_not_an_empty_report(tmp_path: Path) -> None:
    with pytest.raises(errors.GuruError) as exc:
        service.explore(tmp_path)
    assert exc.value.code == errors.WORKSPACE_INVALID


def test_only_html_export_is_supported(project: Path, tmp_path: Path) -> None:
    with GuruClient(project) as guru, pytest.raises(ValueError, match="unsupported export format"):
        guru.export(guru.explore(), output=tmp_path / "x.pdf", format="pdf")


def test_placeholders_inside_source_are_not_substituted(tmp_path: Path) -> None:
    """Source code that contains the template's own placeholders must stay data (found by dogfooding)."""
    m = model.build(_graph(), tmp_path)
    m["symbols"][0]["source"] = 'values = {"{{DATA}}": 1, "{{MANIFEST}}": 2, "{{JS}}": 3}'
    page = render.render(m, {"schema": "x"})
    marker = '<script type="application/json" id="dg-data">'
    start = page.index(marker) + len(marker)
    data = json.loads(page[start : page.index("</script>", start)])
    assert data["symbols"][0]["source"].startswith('values = {"{{DATA}}"')


def test_public_profile_strips_code_text_and_revision(tmp_path: Path) -> None:
    from dev_guru.reports import profiles

    model = {
        "schema": "dev-guru/explorer@1",
        "project": {"name": "p"},
        "limitations": [],
        "files": [{"path": "a.py", "doc": "Internal: talk to Bob"}],
        "symbols": [
            {
                "name": "f",
                "source": "SECRET_LOGIC = 1",
                "doc": "uses the private API",
                "signature": "f(x)",
            }
        ],
    }
    manifest = {
        "workspace": {"name": "p", "vcs": "git", "commit": "abc123", "dirty": True},
        "input_digest": "x",
    }
    pub_model, pub_manifest = profiles.apply(model, manifest, "public")
    dumped = json.dumps([pub_model, pub_manifest])
    assert (
        "SECRET_LOGIC" not in dumped and "talk to Bob" not in dumped and "private API" not in dumped
    )
    assert "abc123" not in dumped and pub_manifest["profile"] == "public"
    assert (
        pub_model["symbols"][0]["signature"] == "f(x)"
        and profiles.PUBLIC_NOTE in pub_model["limitations"]
    )
    assert model["symbols"][0]["source"] == "SECRET_LOGIC = 1"  # the caller's copy is untouched
    same_model, same_manifest = profiles.apply(model, manifest, "private")
    assert same_model == model and same_manifest["profile"] == "private"
