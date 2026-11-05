"""What the offline explorer keeps of a repository analysis."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from dev_guru import service
from dev_guru.reports import profiles, repository

SHOP = Path(__file__).resolve().parent.parent / "acceptance" / "fixtures" / "shop"


def _shop(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    shutil.copytree(SHOP, root)
    for pinned in root.rglob("*.pins"):
        pinned.rename(pinned.with_suffix(""))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def test_every_section_reaches_the_report(tmp_path: Path) -> None:
    view = service.explore(_shop(tmp_path)).model["repository"]
    assert view["routes_total"] == 5 and view["tables_total"] == 4
    assert any(r[1] == "/api/orders" and "createOrder" in r[3] for r in view["routes"])
    assert any(u[1] == "/api/invoices" for u in view["unmatched"])
    assert view["hotspots"][0][0] == "discount"
    assert view["coverage"]["line_rate"] == 0.75


def test_the_file_carries_what_the_pages_ask_for(tmp_path: Path) -> None:
    serve = service.explore(_shop(tmp_path)).model["serve"]
    assert serve["intel"]["sections"]["api"]["routes"]
    assert {f"directory|{d}|" for d in (1, 2, 3, 4)} <= set(serve["code"])
    assert "file|0|" in serve["code"]
    assert any("backend/app/services/orders.py" in p for p in serve["source_text"])
    assert serve["workspace"]["path"] == ""  # no path from this machine
    assert serve["runs"]["runs"]


def test_an_unchecked_repository_isnt_called_clean(tmp_path: Path) -> None:
    result = service.explore(_shop(tmp_path))
    assert result.model["repository"]["dependencies"]["vulnerabilities"] is None
    assert result.model["serve"]["intel"]["sections"]["dependencies"]["status"] == "not_scanned"


def test_a_public_report_keeps_counts_alone(tmp_path: Path) -> None:
    result = service.explore(_shop(tmp_path), profile="public")
    assert "serve" not in result.model
    view = result.model["repository"]
    assert view["reduced"] is True and view["routes_total"] == 5
    text = json.dumps(result.model["repository"])
    for private in ("/api/orders", "audit_log", "createOrder", "docker-compose"):
        assert private not in text


def test_a_public_page_has_no_recording(tmp_path: Path) -> None:
    from dev_guru.reports import render

    result = service.explore(_shop(tmp_path), profile="public")
    page = render.render(result.model, result.manifest)
    assert "createOrder" not in page.split('id="dg-serve"')[1]
    assert "SERVE_SHELL" not in page


def test_a_notebook_folder_with_no_python_files_works(tmp_path: Path) -> None:
    root = tmp_path / "course"
    shutil.copytree(
        Path(__file__).resolve().parent.parent / "acceptance" / "fixtures" / "notebooks", root
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    assert not list(root.rglob("*.py"))
    result = service.explore(root)
    sections = result.model["serve"]["intel"]["sections"]
    assert any(r["path"] == "/churn/{customer_id}" for r in sections["api"]["routes"])
    assert any(t["name"] == "churn_scores" for t in sections["data"]["tables"])
    assert any(p["name"] == "fastapi" for p in sections["dependencies"]["packages"])
    notebooks = sections["notebooks"]
    assert [n["title"][:6] for n in notebooks["notebooks"]] == ["Week 1", "Week 2", "Week 3"]
    assert any(
        k["from"].startswith("week-2") and k["to"].startswith("week-3") for k in notebooks["links"]
    )
    assert any(
        k["from"].startswith("week-1") and k["to"].startswith("week-3") for k in notebooks["links"]
    )
    assert not (root / "week-2" / "churn").exists()


def test_a_failed_analysis_is_named_and_doesnt_stop_the_report(tmp_path: Path, monkeypatch) -> None:
    def broken(*_args: object, **_kwargs: object) -> dict:
        raise ValueError("no analysis today")

    monkeypatch.setattr(repository, "build", broken)
    result = service.explore(_shop(tmp_path))
    assert "repository" not in result.model and "serve" not in result.model
    assert any("no analysis today" in note for note in result.model["limitations"])


def test_public_view_handles_an_empty_report() -> None:
    assert profiles.apply({"symbols": [], "files": []}, {}, "public")[0].get("repository") is None
    assert repository.build({})["dependencies"]["vulnerabilities"] is None
