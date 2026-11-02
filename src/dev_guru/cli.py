"""The ``devguru`` command. CLI and SDK share one service layer: commands never parse each other's text."""

from __future__ import annotations

import json
import platform
from importlib import metadata
from typing import Annotated

import typer
from rich.console import Console

from dev_guru import __version__, errors
from dev_guru.client import TRANSPORTS, connect

app = typer.Typer(
    name="devguru",
    help="Dev Guru: understand, improve and verify your software, on the Ananke Plexus harness.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err = Console(stderr=True)


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


def _optional(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


@app.command()
def doctor(
    transport: Annotated[
        str, typer.Option(help=f"Harness transport: {', '.join(TRANSPORTS)}")
    ] = "in-process",
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
) -> None:
    """Check the Ananke harness: installed version, supported range and the capabilities Dev Guru needs.

    Exits 1 when the harness is missing or incompatible, 2 for an unknown transport.
    """
    try:
        info = connect(transport).info()
    except errors.GuruError as exc:
        if as_json:
            console.print_json(json.dumps({"ok": False, "error": exc.to_dict()}))
        else:
            err.print(f"[red]✗ {exc.code}: {exc.message}[/red]")
        raise typer.Exit(2) from exc
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
