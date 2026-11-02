"""In-process transport: calls the installed ``ananke-plexus`` package through its public facade."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import dev_guru.client.negotiation as negotiation
from dev_guru import errors
from dev_guru.client.port import GraphData, GraphEdgeData, GraphNodeData, GraphSummary, HarnessInfo


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

    def graph_data(self, workspace: Path) -> GraphData:
        """Ask Ananke to build the workspace graph and return the snapshot it stored."""
        info = self.require_compatible()
        root = workspace.expanduser().resolve()
        if not root.is_dir():
            raise errors.GuruError(errors.WORKSPACE_INVALID, f"workspace {root} is not a directory")
        from ananke.plexus.api import Ananke
        from ananke.plexus.graph.service import load_graph

        result = Ananke.open(root).graph_build()
        if not result.ok:
            raise errors.GuruError(
                errors.HARNESS_FAILED, f"Ananke could not build the graph: {result.summary}"
            )
        snapshot = load_graph(root)
        if (
            snapshot is None
        ):  # a "successful" build with nothing stored is a harness fault, not an empty graph
            raise errors.GuruError(
                errors.HARNESS_FAILED, "Ananke reported a graph build but stored no snapshot"
            )
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
                    source=e.source,
                    target=e.target,
                    kind=e.kind,
                    origin=e.origin,
                    confidence=e.confidence,
                    location=e.source_location,
                )
                for e in snapshot.edges
            ],
            source=str(result.details.get("path", "")),
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
