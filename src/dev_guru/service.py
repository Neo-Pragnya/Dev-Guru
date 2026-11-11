"""The service layer shared by the ``dev`` CLI and the Python SDK (neither parses the other's output)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dev_guru import errors
from dev_guru.client import AnankeClient, connect
from dev_guru.progress import Progress, Silent
from dev_guru.reports import model as view_model
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
    progress: Progress | None = None,
) -> ExploreResult:
    progress = progress or Silent()
    client = client or connect()
    root = workspace.expanduser().resolve()
    with progress.step("Building the code graph"):
        graph = client.graph_data(root)
    files = sum(1 for n in graph.nodes if n.kind == "file")
    progress.detail(
        f"{files} files, {len(graph.nodes) - files} other nodes, {len(graph.edges)} links"
    )
    with progress.step("Laying out the explorer's views"):
        model = view_model.build(graph, root, project_name=name)
    from dev_guru import health

    resolved = sum(1 for e in graph.edges if e.kind == "imports" and e.resolved_target)
    progress.detail(
        f"{resolved} imports between this repository's files, {len(model['packages'])} packages"
    )
    for warning in health.problems(graph, model):
        progress.warn(warning)
    if not model["files"]:
        raise errors.GuruError(
            errors.WORKSPACE_INVALID,
            f"Ananke found no source files in {root}",
            hint="point dev explore at a folder with Python, JavaScript or TypeScript files, or notebooks",
        )
    title = "Analysing the repository" + (
        ", and checking dependencies at osv.dev" if check_vulnerabilities else ""
    )
    with progress.step(title):
        report, _run_id, problem = _analyse_repository(client, root, check_vulnerabilities)
    if report is not None:
        for section, found in report.get("sections", {}).items():
            progress.detail(f"{section}: {found.get('status', 'unknown')}")
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
            with progress.step("Collecting every page for the report"):
                model["serve"] = snapshot.build(
                    client,
                    root,
                    report,
                    sorted(set(written)),
                    name or root.name,
                    __version__,
                    progress=progress,
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


def explorer_model(
    workspace: Path, *, client: AnankeClient, name: str | None = None
) -> dict[str, Any]:
    """The explorer's own views for ``dev serve``: the code graph laid out, and its manifest. The other pages ask
    the gateway for what they need, so there's no repository analysis or recording here."""
    root = workspace.expanduser().resolve()
    # Reading a page never starts a run, so this uses the graph Ananke already has
    graph = client.latest_graph(root)
    if graph is None:
        raise errors.GuruError(
            errors.GRAPH_MISSING,
            "There's no code graph for this workspace yet",
            hint="build it from the explorer, or run dev explore once",
        )
    model = view_model.build(graph, root, project_name=name)
    report_manifest = render.manifest(
        model, workspace=root, ananke_version=graph.ananke_version, snapshot_id=graph.snapshot_id
    )
    report_manifest["transport"] = client.transport
    report_manifest["publication"] = "dev-serve"
    return {"model": model, "manifest": report_manifest}


def export_html(
    result: ExploreResult,
    output: Path,
    *,
    title: str | None = None,
    client: AnankeClient | None = None,
    progress: Progress | None = None,
) -> tuple[Path, Path]:
    """Write the report, then record it in the Ananke run it came from (when the transport has runs)."""
    progress = progress or Silent()
    with progress.step("Writing the report"):
        page, sidecar = render.write(result.model, result.manifest, output, title=title)
    progress.detail(f"{page.stat().st_size / 1_000_000:.1f} MB")
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


def graph_export(
    workspace: Path,
    *,
    client: AnankeClient | None = None,
    level: str = "file",
    focus: str | None = None,
    depth: int = 1,
    budget: int = 40,
    name: str | None = None,
) -> dict[str, Any]:
    """A bounded piece of the code graph (``dev-guru/subgraph@1``), ready for Mermaid or SVG.

    It builds the graph and nothing else: no repository analysis and no run record, so it's quick to call again
    with a bigger depth or budget.
    """
    from dev_guru.reports import subgraph

    client = client or connect()
    root = workspace.expanduser().resolve()
    graph = client.graph_data(root)
    model = view_model.build(graph, root, project_name=name)
    if not model["files"]:
        raise errors.GuruError(
            errors.WORKSPACE_INVALID,
            f"Ananke found no source files in {root}",
            hint="point dev graph at a folder with Python, JavaScript or TypeScript files, or notebooks",
        )
    try:
        return subgraph.select(model, level=level, focus=focus, depth=depth, budget=budget)
    except subgraph.SubgraphError as exc:
        raise errors.GuruError(errors.INVALID_INPUT, str(exc)) from exc


def explanation(
    workspace: Path,
    focus: str,
    *,
    client: AnankeClient | None = None,
    levels: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], ExploreResult]:
    """One file or symbol explained at each level of the ladder (``dev-guru/explanation@1``)."""
    from dev_guru import explain as ladder

    result = explore(workspace, client=client)
    try:
        return ladder.explain(result.model, focus, levels=levels or ladder.LEVELS), result
    except ladder.ExplainError as exc:
        raise errors.GuruError(errors.INVALID_INPUT, str(exc)) from exc


def documentation(
    workspace: Path,
    *,
    client: AnankeClient | None = None,
    audience: str = "practitioner",
    detail: str = "standard",
    name: str | None = None,
) -> tuple[dict[str, Any], ExploreResult]:
    """Documentation for one audience at one depth (``dev-guru/documentation@1``)."""
    from dev_guru.explain import docs

    result = explore(workspace, client=client, name=name)
    try:
        return docs.build(result.model, result.manifest, audience=audience, detail=detail), result
    except docs.DocsError as exc:
        raise errors.GuruError(errors.INVALID_INPUT, str(exc)) from exc


def _candidates(client: AnankeClient, root: Path) -> list[dict[str, Any]]:
    return [
        client.learning_candidate(root, n).model_dump() for n in client.learning_candidates(root)
    ]


def mentor_feedback(
    workspace: Path,
    *,
    client: AnankeClient | None = None,
    level: str = "practitioner",
    min_repeats: int = 2,
) -> dict[str, Any]:
    """Advice on failures that repeat across this workspace's Ananke runs (``dev-guru/mentor-feedback@1``)."""
    from dev_guru import mentor

    client = client or connect()
    root = workspace.expanduser().resolve()
    runs = client.run_history(root).get("runs", [])
    try:
        return mentor.feedback(
            runs, _candidates(client, root), level=level, min_repeats=min_repeats
        )
    except ValueError as exc:
        raise errors.GuruError(errors.INVALID_INPUT, str(exc)) from exc


def learning_map(workspace: Path, *, client: AnankeClient | None = None) -> dict[str, Any]:
    """The learning candidates, the runs they came from and the files they mention (``dev-guru/learning-graph@1``)."""
    from dev_guru import mentor

    client = client or connect()
    root = workspace.expanduser().resolve()
    files = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or not path.is_file():
            continue
        files.append(rel.as_posix())
        if len(files) >= 20_000:
            break
    return mentor.learning_graph(_candidates(client, root), files=files)


__all__ = [
    "ExploreResult",
    "documentation",
    "explanation",
    "explore",
    "explorer_model",
    "export_html",
    "graph_export",
    "learning_map",
    "mentor_feedback",
]
