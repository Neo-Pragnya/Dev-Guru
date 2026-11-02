"""The ``dev`` command. CLI and SDK share one service layer (dev_guru.service)."""

from __future__ import annotations

import json
import platform
import webbrowser
from importlib import metadata
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from dev_guru import errors, service
from dev_guru.client import TRANSPORTS, connect
from dev_guru.version import __version__

app = typer.Typer(
    name="dev",
    help="Dev Guru: understand, improve and verify your software, on the Ananke Plexus harness.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err = Console(stderr=True)
TransportOpt = Annotated[str, typer.Option(help=f"Harness transport: {', '.join(TRANSPORTS)}")]
JsonOpt = Annotated[bool, typer.Option("--json", help="Machine-readable output")]


def _version(value: bool) -> None:
    if value:
        console.print(f"dev-guru {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version, is_eager=True, help="Show the version and exit"
        ),
    ] = False,
) -> None:
    """Dev Guru: understand, improve and verify your software, on the Ananke Plexus harness."""


def _fail(exc: errors.GuruError, as_json: bool, code: int) -> None:
    if as_json:
        console.print_json(json.dumps({"ok": False, "error": exc.to_dict()}))
    else:
        err.print(f"[red]✗ {exc.code}: {exc.message}[/red]")
        if exc.hint:
            err.print(f"  [dim]{exc.hint}[/dim]")
    raise typer.Exit(code) from exc


def _optional(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


@app.command()
def doctor(transport: TransportOpt = "in-process", as_json: JsonOpt = False) -> None:
    """Check the Ananke harness: installed version, supported range and the capabilities Dev Guru needs.

    Exits 1 when the harness is missing or incompatible, 2 for an unknown transport.
    """
    try:
        info = connect(transport).info()
    except errors.GuruError as exc:
        _fail(exc, as_json, 2)
        return
    dex = _optional("dex-trove")
    report = {
        "ok": info.compatible,
        "dev_guru": __version__,
        "python": platform.python_version(),
        "harness": info.model_dump(),
        "optional": {"dex-trove": dex},
    }
    if as_json:
        console.print_json(json.dumps(report))
    else:
        mark = "[green]✓[/green]" if info.compatible else "[red]✗[/red]"
        console.print(
            f"dev-guru {__version__} · Python {report['python']} · transport {info.transport}"
        )
        console.print(
            f"{mark} ananke-plexus {info.ananke_version or 'not installed'} (supported {info.supported_range})"
        )
        for cap, present in info.capabilities.items():
            console.print(f"  {'✓' if present else '✗'} {cap}")
        for reason in info.reasons:
            console.print(f"  [red]{reason}[/red]")
        console.print(f"  [dim]dex-trove: {dex or 'not installed (optional)'}[/dim]")
    if not info.compatible:
        raise typer.Exit(1)


@app.command()
def explore(
    workspace: Annotated[Path, typer.Argument(help="Project to explore")] = Path("."),
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Report file (a manifest is written next to it)")
    ] = Path("dev-guru-explorer.html"),
    name: Annotated[str | None, typer.Option(help="Project name shown in the report")] = None,
    open_browser: Annotated[
        bool, typer.Option("--open", help="Open the report when it's written")
    ] = False,
    transport: TransportOpt = "in-process",
    as_json: JsonOpt = False,
) -> None:
    """Explore a codebase: Ananke builds the graph, Dev Guru writes an interactive, offline HTML explorer.

    The report is one file with no network access: architecture constellation, dependency flow, impact rings,
    call graph, hotspots, a guided tour, search and a source inspector.
    """
    try:
        result = service.explore(workspace, client=connect(transport), name=name)
        page, sidecar = service.export_html(result, output)
    except errors.GuruError as exc:
        _fail(exc, as_json, 1)
        return
    project = result.model["project"]
    summary = {
        "ok": True,
        "report": str(page),
        "manifest": str(sidecar),
        "input_digest": result.manifest["input_digest"],
        "project": project,
        "insights": {k: len(v) for k, v in result.model["insights"].items()},
    }
    if as_json:
        console.print_json(json.dumps(summary))
    else:
        console.print(
            f"[green]✓[/green] {project['files']} files · {project['symbols']} symbols · "
            f"{project['imports']} imports · {project['calls']} calls → {page}"
        )
        cycles = len(result.model["insights"]["cycles"])
        if cycles:
            console.print(f"  [yellow]{cycles} import cycle(s) found; see the Flow view[/yellow]")
        console.print(f"  [dim]manifest {sidecar} · {result.manifest['input_digest'][:19]}…[/dim]")
    if open_browser:
        webbrowser.open(page.resolve().as_uri())
