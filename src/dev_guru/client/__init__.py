"""The Ananke client port. Use :func:`connect` to get a client for one explicit transport."""

from __future__ import annotations

from dev_guru import errors
from dev_guru.client.inprocess import InProcessAnanke
from dev_guru.client.port import AnankeClient, GraphSummary, HarnessInfo

TRANSPORTS = ("in-process",)  # planned: "process" (isolated executable), "gateway" (local HTTP)


def connect(transport: str = "in-process") -> AnankeClient:
    """A client for exactly ``transport``. An unknown or unavailable transport is an error, not a fallback."""
    if transport == "in-process":
        return InProcessAnanke()
    raise errors.GuruError(
        errors.UNSUPPORTED_TRANSPORT,
        f"transport {transport!r} is not supported; supported: {', '.join(TRANSPORTS)}",
    )


__all__ = ["TRANSPORTS", "AnankeClient", "GraphSummary", "HarnessInfo", "connect"]
