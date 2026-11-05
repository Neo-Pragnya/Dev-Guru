"""In-process transport: calls the installed ``ananke-plexus`` package through its public facade."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import dev_guru.client.negotiation as negotiation
from dev_guru import errors
from dev_guru.client.port import (
    CapabilityInfo,
    Destination,
    GraphData,
    GraphEdgeData,
    GraphNodeData,
    GraphSummary,
    HarnessInfo,
    LearningCandidate,
)


class InProcessAnanke:
    transport = "in-process"

    def info(self) -> HarnessInfo:
        version = negotiation.installed_version()
        if version is None:
            return HarnessInfo(
                transport=self.transport,
                ananke_version=None,
                supported_range=negotiation.SUPPORTED_ANANKE,
                compatible=False,
                reasons=["ananke-plexus is not installed in this environment"],
            )
        caps = negotiation.probe()
        missing = [c for c in negotiation.REQUIRED if not caps.get(c)]
        reasons: list[str] = []
        if not negotiation.supported(version):
            reasons.append(
                f"ananke-plexus {version} is outside the supported range {negotiation.SUPPORTED_ANANKE}"
            )
        if missing:
            reasons.append(f"required harness capabilities are missing: {', '.join(missing)}")
        return HarnessInfo(
            transport=self.transport,
            ananke_version=version,
            supported_range=negotiation.SUPPORTED_ANANKE,
            compatible=not reasons,
            capabilities=caps,
            missing_required=missing,
            reasons=reasons,
        )

    def require_compatible(self) -> HarnessInfo:
        info = self.info()
        if info.ananke_version is None:
            raise errors.GuruError(
                errors.HARNESS_MISSING,
                "Ananke Plexus is not installed",
                hint="pip install 'ananke-plexus" + negotiation.SUPPORTED_ANANKE + "'",
            )
        if info.missing_required:
            raise errors.GuruError(errors.CAPABILITY_MISSING, "; ".join(info.reasons))
        if not info.compatible:
            raise errors.GuruError(
                errors.HARNESS_INCOMPATIBLE,
                "; ".join(info.reasons),
                hint=f"install ananke-plexus{negotiation.SUPPORTED_ANANKE}",
            )
        return info

    def _root(self, workspace: Path) -> Path:
        root = workspace.expanduser().resolve()
        if not root.is_dir():
            raise errors.GuruError(errors.WORKSPACE_INVALID, f"workspace {root} is not a directory")
        return root

    def _facade(self, root: Path):  # type: ignore[no-untyped-def]
        """The Ananke app facade for a workspace, after protocol negotiation (never a silent downgrade)."""
        from ananke.plexus.app import AppError, AppFacade

        facade = AppFacade(root)
        try:
            facade.negotiate([negotiation.APP_PROTOCOL])
        except AppError as exc:
            raise errors.GuruError(errors.HARNESS_INCOMPATIBLE, exc.message) from exc
        return facade

    def _call(self, workspace: Path, work: Callable[[Any], Any]) -> Any:
        """Run one facade call, turning what Ananke refuses into a typed error that keeps its code."""
        from ananke.plexus.app import AppError

        facade = self._facade(self._root(workspace))
        try:
            return work(facade)
        except AppError as exc:
            raise errors.HarnessRefused(exc.code, exc.message, retryable=exc.retryable) from exc

    def harness_capabilities(self, workspace: Path) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.capabilities()))

    def context_map(
        self, workspace: Path, budget: int = 1500, refresh: bool = False
    ) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.context_map(budget=budget, refresh=refresh)))

    def context_status(self, workspace: Path) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.context_status()))

    def read_source(
        self, workspace: Path, path: str, start: int = 1, end: int | None = None
    ) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.read_source(path, start=start, end=end)))

    def code_view(self, workspace: Path, **filters: Any) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.code_view(**filters)))

    def prepare_plan(self, workspace: Path, draft: dict[str, Any]) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.preview_workflow(draft)))

    def submit_run(
        self, workspace: Path, kind: str, parameters: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        return dict(
            self._call(
                workspace,
                lambda f: f.submit_run(
                    f.prepare_run(kind, parameters), idempotency_key, start=False
                ),
            )
        )

    def drive_run(self, workspace: Path, run_id: str) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.drive(run_id)))

    def get_run(self, workspace: Path, run_id: str) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.get_run(run_id)))

    def run_history(self, workspace: Path) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.evidence_view()))

    def run_events(self, workspace: Path, run_id: str, after: int = 0) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.stream_events(run_id, after)))

    def cancel_run(self, workspace: Path, run_id: str) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.cancel_run(run_id)))

    def run_artifacts(self, workspace: Path, run_id: str) -> list[dict[str, Any]]:
        return list(self._call(workspace, lambda f: f.list_artifacts(run_id)))

    def read_artifact(self, workspace: Path, run_id: str, name: str) -> bytes:
        return bytes(self._call(workspace, lambda f: f.read_artifact(run_id, name)))

    def graph_data(self, workspace: Path) -> GraphData:
        """Run Ananke's graph build through the app facade and read the snapshot artifact it produced."""
        info = self.require_compatible()
        root = self._root(workspace)
        from ananke.plexus.app import AppError
        from ananke.plexus.graph.models import GraphSnapshot

        facade = self._facade(root)
        run_id = None
        try:
            prepared = facade.prepare_run("graph.build")
            # the same workspace state is the same request: re-exploring unchanged code reuses the run
            run = facade.submit_run(
                prepared, "dev-guru-explore-" + prepared.locked_plan_digest[:24]
            )
            run_id = run["run_id"]
            if run["state"] != "succeeded":
                reasons = (
                    "; ".join(str(w.get("message")) for w in run.get("warnings", []))
                    or run["state"]
                )
                raise errors.GuruError(
                    errors.HARNESS_FAILED,
                    f"Ananke's graph run {run['state']}: {reasons}",
                    run_id=run_id,
                )
            snapshot = GraphSnapshot.model_validate_json(
                facade.read_artifact(run_id, "graph-snapshot.json")
            )
        except AppError as exc:
            raise errors.GuruError(errors.HARNESS_FAILED, exc.message, run_id=run_id) from exc
        return GraphData(
            snapshot_id=snapshot.snapshot_id,
            provider=snapshot.provider,
            ananke_version=info.ananke_version,
            nodes=[
                GraphNodeData(
                    id=n.node_id, kind=n.kind, name=n.name, path=n.path, metadata=dict(n.metadata)
                )
                for n in snapshot.nodes
            ],
            edges=[
                GraphEdgeData(
                    resolved_target=str(getattr(e, "resolved_target", "") or ""),
                    source=e.source,
                    target=e.target,
                    kind=e.kind,
                    origin=e.origin,
                    confidence=e.confidence,
                    location=e.source_location,
                )
                for e in snapshot.edges
            ],
            source=f"ananke run {run_id}",
            run_id=run_id,
        )

    def register_artifact(
        self,
        workspace: Path,
        run_id: str,
        name: str,
        data: bytes,
        *,
        media_type: str,
        input_refs: list[str],
    ) -> dict[str, object]:
        """Record a rendered report in the Ananke run it came from (Dev Guru is the external renderer)."""
        from ananke.plexus.app import AppError

        try:
            ref: dict[str, object] = self._facade(self._root(workspace)).register_artifact(
                run_id,
                name,
                data,
                media_type=media_type,
                producer="dev-guru/explorer-html@1",
                input_refs=input_refs,
            )
        except AppError as exc:
            raise errors.GuruError(errors.HARNESS_FAILED, exc.message, run_id=run_id) from exc
        return ref

    def discover_capabilities(self, workspace: Path, query: str = "") -> list[CapabilityInfo]:
        """Capabilities from every configured source, through Ananke's provider port."""
        self.require_compatible()
        from ananke.plexus.registry.providers import SourceError, from_project

        try:
            found = from_project(self._root(workspace)).discover(query, 100000)
        except SourceError as exc:
            raise errors.GuruError(errors.HARNESS_FAILED, exc.message) from exc
        return [
            CapabilityInfo(
                identity=d.identity,
                kind=d.kind,
                version=d.version,
                digest=d.digest,
                summary=d.summary,
                licence=d.licence,
                unknown=list(d.unknown),
            )
            for d in found
        ]

    def process_model(
        self, workspace: Path, text: str, source: str = "", bpmn: str = ""
    ) -> dict[str, Any]:
        return dict(self._call(workspace, lambda f: f.process_model(text, source, bpmn)))

    def learning_candidates(self, workspace: Path) -> list[str]:
        """Names of the candidates waiting for review."""
        self.require_compatible()
        from ananke.plexus.learning import candidates_dir

        folder = candidates_dir(self._root(workspace))
        return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []

    def learning_candidate(self, workspace: Path, name: str) -> LearningCandidate:
        """Ananke's view of a learning candidate, and a diff against each writable destination."""
        import difflib
        import json

        self.require_compatible()
        from ananke.plexus.learning import candidates_dir, gate
        from ananke.plexus.registry.providers import CapabilityRef, SourceError, from_project

        root = self._root(workspace)
        folder = candidates_dir(root) / name
        if not folder.is_dir():
            raise errors.GuruError(
                errors.INVALID_INPUT,
                f"no learning candidate {name!r}",
                hint="list them with `ananke learning list`",
            )

        def read(file: str) -> Any:
            path = folder / file
            return json.loads(path.read_text()) if path.is_file() else None

        evaluation, review, provenance = (
            read("evaluation.json") or {},
            read("review.json"),
            read("provenance.json") or {},
        )
        skill = (folder / "SKILL.md").read_text(encoding="utf-8")
        destinations = []
        try:
            providers = from_project(root)
        except SourceError as exc:
            raise errors.GuruError(errors.HARNESS_FAILED, exc.message) from exc
        for sid, p in providers.providers.items():
            dest = Destination(
                source=sid,
                writable=bool(p.writable),
                visibility=str(getattr(p, "visibility", "internal")),
            )
            try:
                current = p.resolve(CapabilityRef(name))
                old = p.fetch(current).files.get("SKILL.md", b"").decode("utf-8", "replace")
                dest.existing_version = current.version
                dest.diff = "".join(
                    difflib.unified_diff(
                        old.splitlines(True),
                        skill.splitlines(True),
                        f"{sid}:{name}@{current.version}",
                        f"candidate:{name}",
                    )
                )
            except SourceError:
                dest.diff = "".join(
                    difflib.unified_diff(
                        [], skill.splitlines(True), "/dev/null", f"candidate:{name}"
                    )
                )
            destinations.append(dest)
        return LearningCandidate(
            name=name,
            skill_md=skill,
            cases=list(evaluation.get("cases", [])),
            evaluated_at=evaluation.get("finished_at"),
            review=review,
            provenance=provenance,
            problems=gate(folder),
            destinations=destinations,
        )

    def graph_summary(self, workspace: Path) -> GraphSummary:
        """Ask Ananke to build the workspace graph, then summarise the snapshot it stored."""
        data = self.graph_data(workspace)
        return GraphSummary(
            snapshot_id=data.snapshot_id,
            provider=data.provider,
            nodes=len(data.nodes),
            edges=len(data.edges),
            nodes_by_kind=dict(sorted(Counter(n.kind for n in data.nodes).items())),
            edges_by_kind=dict(sorted(Counter(e.kind for e in data.edges).items())),
            source=data.source,
        )


__all__ = ["InProcessAnanke"]
