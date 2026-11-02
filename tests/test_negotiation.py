"""Version and capability negotiation: explicit verdicts, stable error codes, no silent downgrade."""

from __future__ import annotations

import pytest

from dev_guru import errors
from dev_guru.client import inprocess, negotiation


@pytest.mark.parametrize(
    ("version", "ok"),
    [
        ("0.3.11", True),
        ("0.3.99", True),
        ("0.3.10", False),
        ("0.4.0", False),
        ("1.0.0", False),
        ("junk", False),
    ],
)
def test_supported_range_boundaries(version: str, ok: bool) -> None:
    assert negotiation.supported(version) is ok


def test_probe_reports_present_and_missing_capabilities() -> None:
    caps = negotiation.probe(
        {
            "present": ("ananke.plexus.api", "Ananke.graph_build"),
            "absent": ("ananke.plexus.api", "Ananke.no_such"),
        }
    )
    assert caps == {"present": True, "absent": False}
    assert negotiation.probe({"nomod": ("no.such.module", "x")}) == {"nomod": False}


def test_missing_harness_is_reported_and_raises_harness_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(negotiation, "installed_version", lambda *a: None)
    client = inprocess.InProcessAnanke()
    info = client.info()
    assert not info.compatible and info.ananke_version is None
    with pytest.raises(errors.GuruError) as exc:
        client.require_compatible()
    assert exc.value.code == errors.HARNESS_MISSING and "ananke-plexus" in exc.value.hint


def test_out_of_range_harness_is_incompatible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(negotiation, "installed_version", lambda *a: "0.4.2")
    with pytest.raises(errors.GuruError) as exc:
        inprocess.InProcessAnanke().require_compatible()
    assert exc.value.code == errors.HARNESS_INCOMPATIBLE
    assert "0.4.2" in exc.value.message


def test_missing_required_capability_is_its_own_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(negotiation, "probe", lambda *a: {"graph.build": True, "graph.load": False})
    info = inprocess.InProcessAnanke().info()
    assert info.missing_required == ["graph.load"] and not info.compatible
    with pytest.raises(errors.GuruError) as exc:
        inprocess.InProcessAnanke().require_compatible()
    assert exc.value.code == errors.CAPABILITY_MISSING


def test_the_installed_harness_is_compatible() -> None:
    info = inprocess.InProcessAnanke().info()
    assert info.compatible, info.reasons
    assert all(info.capabilities[c] for c in negotiation.REQUIRED)


def test_error_codes_are_closed() -> None:
    with pytest.raises(ValueError, match="unknown error code"):
        errors.GuruError("SOMETHING_ELSE", "x")
    assert errors.GuruError(errors.HARNESS_FAILED, "m", run_id="r1").to_dict()["run_id"] == "r1"
