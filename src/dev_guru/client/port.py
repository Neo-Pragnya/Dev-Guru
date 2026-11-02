"""The one port between Dev Guru and the Ananke harness.

Dev Guru never analyses code itself: every domain operation goes through an :class:`AnankeClient`. Today there is
one transport (``in-process``: the installed ``ananke-plexus`` package). An isolated executable and a local HTTP
gateway are planned. Exactly one transport is chosen per run and recorded; a failing transport is reported, never
silently swapped for another (docs/concepts/ananke-client.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class HarnessInfo(BaseModel):
    """What negotiation found: the transport, harness version, support verdict and capabilities."""

    transport: str
    ananke_version: str | None
    supported_range: str
    compatible: bool
    capabilities: dict[str, bool] = Field(default_factory=dict)
    missing_required: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class GraphSummary(BaseModel):
    """A bounded projection of an Ananke graph snapshot. Ananke keeps the snapshot itself."""

    snapshot_id: str
    provider: str
    nodes: int
    edges: int
    nodes_by_kind: dict[str, int] = Field(default_factory=dict)
    edges_by_kind: dict[str, int] = Field(default_factory=dict)
    source: str  # where Ananke stored the snapshot (Ananke-owned workspace state)


class GraphNodeData(BaseModel):
    id: str
    kind: str
    name: str
    path: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class GraphEdgeData(BaseModel):
    source: str
    target: str
    kind: str
    origin: str = "extracted"
    confidence: float = 1.0
    location: str = ""


class GraphData(BaseModel):
    """The graph Ananke built, as plain data. Dev Guru projects it; it never adds analysis of its own."""

    snapshot_id: str
    provider: str
    ananke_version: str | None
    nodes: list[GraphNodeData] = Field(default_factory=list)
    edges: list[GraphEdgeData] = Field(default_factory=list)
    source: str = ""
    run_id: str = ""  # the Ananke run that produced this graph (app facade)


class CapabilityInfo(BaseModel):
    """One capability a source offers, as the provider port describes it."""

    identity: str
    kind: str
    version: str
    digest: str
    summary: str = ""
    licence: str = "unknown"
    unknown: list[str] = Field(default_factory=list)


class Destination(BaseModel):
    source: str
    writable: bool
    visibility: str = "internal"
    existing_version: str | None = None
    diff: str = ""


class LearningCandidate(BaseModel):
    """A learning candidate as Ananke's gate sees it, plus how it would change each writable destination."""

    name: str
    skill_md: str
    cases: list[dict[str, object]] = Field(default_factory=list)
    evaluated_at: str | None = None
    review: dict[str, str] | None = None
    provenance: dict[str, object] = Field(default_factory=dict)
    problems: list[str] = Field(default_factory=list)
    destinations: list[Destination] = Field(default_factory=list)


@runtime_checkable
class AnankeClient(Protocol):
    transport: str

    def info(self) -> HarnessInfo: ...

    def graph_summary(self, workspace: Path) -> GraphSummary: ...

    def graph_data(self, workspace: Path) -> GraphData: ...

    def register_artifact(
        self,
        workspace: Path,
        run_id: str,
        name: str,
        data: bytes,
        *,
        media_type: str,
        input_refs: list[str],
    ) -> dict[str, object]: ...

    def discover_capabilities(self, workspace: Path, query: str = "") -> list[CapabilityInfo]: ...

    def learning_candidate(self, workspace: Path, name: str) -> LearningCandidate: ...


__all__ = [
    "AnankeClient",
    "CapabilityInfo",
    "Destination",
    "GraphData",
    "GraphEdgeData",
    "GraphNodeData",
    "GraphSummary",
    "HarnessInfo",
    "LearningCandidate",
]
