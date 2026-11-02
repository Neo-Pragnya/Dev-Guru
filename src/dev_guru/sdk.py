"""The Dev Guru Python SDK.

from dev_guru import GuruClient

with GuruClient(workspace="./my-project") as guru:
    result = guru.explore()
    guru.export(result, output="reports/explorer.html")
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

from dev_guru import service
from dev_guru.client import AnankeClient, HarnessInfo, connect
from dev_guru.service import ExploreResult


class GuruClient:
    def __init__(self, workspace: str | Path = ".", *, transport: str = "in-process") -> None:
        self.workspace = Path(workspace)
        self.client: AnankeClient = connect(transport)

    def __enter__(self) -> GuruClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def doctor(self) -> HarnessInfo:
        return self.client.info()

    def explore(self, *, name: str | None = None) -> ExploreResult:
        return service.explore(self.workspace, client=self.client, name=name)

    def export(
        self,
        result: ExploreResult,
        *,
        output: str | Path,
        format: str = "html",
        title: str | None = None,
    ) -> Path:
        if format != "html":
            raise ValueError(f"unsupported export format {format!r}; supported: html")
        page, _ = service.export_html(result, Path(output), title=title)
        return page


__all__ = ["GuruClient"]
