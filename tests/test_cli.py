from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from dev_guru import __version__
from dev_guru.cli import app
from dev_guru.client import negotiation

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0 and __version__ in result.output


def test_doctor_json_reports_the_harness() -> None:
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["ok"] is True and report["harness"]["transport"] == "in-process"
    assert report["harness"]["supported_range"] == negotiation.SUPPORTED_ANANKE
    assert "dex-trove" in report["optional"]


def test_doctor_fails_on_an_incompatible_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(negotiation, "installed_version", lambda *a: "0.2.0")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1 and "outside the supported range" in result.output


def test_doctor_unknown_transport_is_a_clean_error() -> None:
    result = runner.invoke(app, ["doctor", "--transport", "gateway", "--json"])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["code"] == "UNSUPPORTED_TRANSPORT"
