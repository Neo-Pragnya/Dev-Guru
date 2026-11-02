"""The service layer shared by the ``dev`` CLI and the Python SDK (neither parses the other's output)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dev_guru import errors
from dev_guru.client import AnankeClient, connect
from dev_guru.reports import model as explorer_model
from dev_guru.reports import render


@dataclass(frozen=True)
class ExploreResult:
    """What ``explore`` produced: the view model and its manifest, before or after export."""

    workspace: Path
    model: dict[str, Any]
    manifest: dict[str, Any]
    transport: str


def explore(
    workspace: Path,
    *,
    client: AnankeClient | None = None,
    name: str | None = None,
    profile: str = "private",
) -> ExploreResult:
    client = client or connect()
    root = workspace.expanduser().resolve()
    graph = client.graph_data(root)
    model = explorer_model.build(graph, root, project_name=name)
    if not model["files"]:
        raise errors.GuruError(
            errors.WORKSPACE_INVALID,
            f"Ananke found no Python files in {root}",
            hint="point dev explore at a project directory that contains .py files",
        )
    report_manifest = render.manifest(
        model, workspace=root, ananke_version=graph.ananke_version, snapshot_id=graph.snapshot_id
    )
    report_manifest["transport"] = client.transport
    from dev_guru.reports import profiles

    if profile not in profiles.PROFILES:
        raise errors.GuruError(
            errors.INVALID_INPUT,
            f"unknown profile {profile!r}",
            hint=f"use one of: {', '.join(profiles.PROFILES)}",
        )
    model, report_manifest = profiles.apply(model, report_manifest, profile)
    return ExploreResult(
        workspace=root, model=model, manifest=report_manifest, transport=client.transport
    )


def export_html(
    result: ExploreResult, output: Path, *, title: str | None = None
) -> tuple[Path, Path]:
    return render.write(result.model, result.manifest, output, title=title)


__all__ = ["ExploreResult", "explore", "export_html"]
