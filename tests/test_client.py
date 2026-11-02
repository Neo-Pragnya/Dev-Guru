"""The client port against the real Ananke harness (integration), plus transport selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_guru import errors
from dev_guru.client import AnankeClient, connect


def test_one_explicit_transport_and_no_fallback() -> None:
    client = connect()
    assert isinstance(client, AnankeClient) and client.transport == "in-process"
    with pytest.raises(errors.GuruError) as exc:
        connect("gateway")
    assert exc.value.code == errors.UNSUPPORTED_TRANSPORT


def test_graph_summary_comes_from_the_real_harness(project: Path) -> None:
    summary = connect().graph_summary(project)
    assert summary.nodes_by_kind.get("file") == 3
    assert summary.nodes_by_kind.get("class") == 1 and summary.nodes_by_kind.get("function") == 2
    assert summary.edges_by_kind.get("imports", 0) >= 2
    # Ananke owns the snapshot; Dev Guru only reports where it is.
    assert Path(summary.source).is_file() and ".ananke" in summary.source


def test_graph_summary_rejects_a_missing_workspace(tmp_path: Path) -> None:
    with pytest.raises(errors.GuruError) as exc:
        connect().graph_summary(tmp_path / "nope")
    assert exc.value.code == errors.WORKSPACE_INVALID


def test_a_build_that_stores_nothing_is_an_error_not_an_empty_graph(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ananke.plexus.graph.service as service

    monkeypatch.setattr(service, "load_graph", lambda root: None)
    with pytest.raises(errors.GuruError) as exc:
        connect().graph_summary(project)
    assert exc.value.code == errors.HARNESS_FAILED
