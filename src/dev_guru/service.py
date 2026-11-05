"""The service layer shared by the ``dev`` CLI and the Python SDK (neither parses the other's output)."""

from __future__ import annotations

import json
import uuid
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
    run_id: str = ""  # the Ananke run that produced the graph, when the transport has runs


def _analyse_repository(
    client: AnankeClient, root: Path, check_vulnerabilities: bool
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """The whole-repository analysis for the report. It reads files and runs nothing. Only a CVE check, asked for
    by name, uses the network."""
    params = {"check_vulnerabilities": True} if check_vulnerabilities else {}
    try:
        run = client.submit_run(root, "repo.analyze", params, uuid.uuid4().hex)
        client.drive_run(root, run["run_id"])
        report = json.loads(client.read_artifact(root, run["run_id"], "repo-intel.json"))
    except (errors.GuruError, OSError, ValueError, KeyError) as exc:
        return None, None, f"The repository analysis isn't included: {exc}"
    report["run_id"] = run["run_id"]
    report["analysed_at"] = client.get_run(root, run["run_id"]).get("created_at")
    return report, run["run_id"], None


def explore(
    workspace: Path,
    *,
    client: AnankeClient | None = None,
    name: str | None = None,
    profile: str = "private",
    check_vulnerabilities: bool = False,
) -> ExploreResult:
    client = client or connect()
    root = workspace.expanduser().resolve()
    graph = client.graph_data(root)
    model = explorer_model.build(graph, root, project_name=name)
    if not model["files"]:
        raise errors.GuruError(
            errors.WORKSPACE_INVALID,
            f"Ananke found no source files in {root}",
            hint="point dev explore at a folder with Python, JavaScript or TypeScript files, or notebooks",
        )
    report, _run_id, problem = _analyse_repository(client, root, check_vulnerabilities)
    if report is not None:
        try:
            from dev_guru.reports import repository, snapshot
            from dev_guru.version import __version__

            model["repository"] = repository.build(report)
            written = [
                str(n.path)
                for n in graph.nodes
                if n.kind == "file" and n.path and not str(n.path).endswith(".ipynb")
            ]
            model["serve"] = snapshot.build(
                client, root, report, sorted(set(written)), name or root.name, __version__
            )
        except (errors.GuruError, OSError, ValueError, KeyError) as exc:
            model.pop("serve", None)
            problem = f"The repository analysis isn't included: {exc}"
    if problem:
        model["limitations"] = [*model.get("limitations", []), problem]
    report_manifest = render.manifest(
        model, workspace=root, ananke_version=graph.ananke_version, snapshot_id=graph.snapshot_id
    )
    report_manifest["transport"] = client.transport
    if graph.run_id:
        report_manifest["ananke_run"] = {"run_id": graph.run_id, "protocol": "ananke-app/1"}
    from dev_guru.reports import profiles

    if profile not in profiles.PROFILES:
        raise errors.GuruError(
            errors.INVALID_INPUT,
            f"unknown profile {profile!r}",
            hint=f"use one of: {', '.join(profiles.PROFILES)}",
        )
    model, report_manifest = profiles.apply(model, report_manifest, profile)
    return ExploreResult(
        workspace=root,
        model=model,
        manifest=report_manifest,
        transport=client.transport,
        run_id=graph.run_id,
    )


def export_html(
    result: ExploreResult,
    output: Path,
    *,
    title: str | None = None,
    client: AnankeClient | None = None,
) -> tuple[Path, Path]:
    """Write the report, then record it in the Ananke run it came from (when the transport has runs)."""
    page, sidecar = render.write(result.model, result.manifest, output, title=title)
    if client is not None and result.run_id:
        client.register_artifact(
            result.workspace,
            result.run_id,
            page.name,
            page.read_bytes(),
            media_type="text/html",
            input_refs=["graph-snapshot.json", str(result.manifest["input_digest"])],
        )
    return page, sidecar


__all__ = ["ExploreResult", "explore", "export_html"]
