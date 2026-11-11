"""The Dev Guru Python SDK.

from dev_guru import GuruClient

with GuruClient(workspace="./my-project") as guru:
    result = guru.explore()
    guru.export(result, output="reports/explorer.html")
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any

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
        **graph: Any,
    ) -> Path:
        """Write the explorer (``html``), or the code graph as ``mermaid``, ``svg`` or ``json``.

        Graph formats take ``level``, ``focus``, ``depth`` and ``budget`` (see ``dev graph``)."""
        from dev_guru.reports import subgraph

        path = Path(output)
        if format == "html":
            page, _ = service.export_html(result, path, title=title, client=self.client)
            return page
        if format not in subgraph.FORMATS:
            raise ValueError(
                f"unsupported export format {format!r}; supported: html, {', '.join(subgraph.FORMATS)}"
            )
        sub = subgraph.select(result.model, **graph)
        if format == "json":
            path.write_text(json.dumps(sub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif format == "svg":
            path.write_text(subgraph.to_svg(sub), encoding="utf-8")
        else:
            path.write_text(subgraph.to_mermaid(sub), encoding="utf-8")
        return path


__all__ = ["GuruClient"]
