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
from rich.markup import escape

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
    profile: Annotated[
        str,
        typer.Option(
            help="private (everything) or public (no source, docstrings or Git revision: safe to publish)"
        ),
    ] = "private",
    as_json: JsonOpt = False,
) -> None:
    """Explore a codebase: Ananke builds the graph, Dev Guru writes an interactive, offline HTML explorer.

    The report is one file with no network access: architecture constellation, dependency flow, impact rings,
    call graph, hotspots, a guided tour, search and a source inspector.
    """
    try:
        result = service.explore(workspace, client=connect(transport), name=name, profile=profile)
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


@app.command()
def present(
    slides: Annotated[
        Path, typer.Argument(help="Markdown slides (separate slides with a line of ---)")
    ],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Deck file")] = None,
    theme: Annotated[
        str | None, typer.Option(help="lantern (dark) or paper (light); default from front matter")
    ] = None,
    check_only: Annotated[
        bool, typer.Option("--check", help="Check an existing HTML deck instead of building")
    ] = False,
    open_browser: Annotated[
        bool, typer.Option("--open", help="Open the deck when it's written")
    ] = False,
) -> None:
    """Turn Markdown slides into one offline, accessible HTML deck (arrow keys, N for notes, print to PDF).

    Raw HTML is shown as text, images must be local with alt text, charts come from ```chart JSON blocks, and the
    page can't make network requests. --check verifies a built deck.
    """
    from dev_guru import present as deck

    if check_only:
        problems = deck.check(slides.read_text(encoding="utf-8"))
        for p in problems:
            err.print(f"[red]✗[/red] {p}")
        if problems:
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] {slides}: offline and accessible checks pass")
        return
    try:
        page = deck.build(slides.read_text(encoding="utf-8"), slides.parent, theme=theme)
    except (deck.DeckError, OSError) as exc:
        err.print(
            f"[red]✗ {escape(str(exc))}[/red]"
        )  # the message quotes Markdown like ![alt](src)
        raise typer.Exit(2) from exc
    problems = deck.check(page)
    if (
        problems
    ):  # a bug in the renderer, not the author's input: never write a deck that fails its own check
        err.print("[red]✗ built deck failed its checks: " + "; ".join(problems) + "[/red]")
        raise typer.Exit(1)
    out = output or slides.with_suffix(".html")
    out.write_text(page, encoding="utf-8")
    n = page.count('class="slide"')
    console.print(f"[green]✓[/green] {n} slides → {out}")
    if open_browser:
        webbrowser.open(out.resolve().as_uri())


@app.command()
def diagram(
    document: Annotated[Path, typer.Argument(help="An approved Markdown document")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="SVG file (default <document>.svg)")
    ] = None,
    model_out: Annotated[
        Path | None, typer.Option("--model", help="Also write the editable model (JSON)")
    ] = None,
    from_model: Annotated[
        Path | None, typer.Option("--from-model", help="Render an edited model instead")
    ] = None,
    static: Annotated[bool, typer.Option("--static", help="No animation")] = False,
    as_json: JsonOpt = False,
) -> None:
    """An animated SVG of the relationships a document states, every one cited (file and line).

    Reads arrow lines (A -> B: label), Mermaid flowcharts and From/To tables, never prose, so nothing is invented.
    Edited relationships whose citation doesn't hold up are drawn as hypotheses (dashed, "?").
    """
    from dev_guru import diagram as dg

    try:
        text = document.read_text(encoding="utf-8")
        model = (
            json.loads(from_model.read_text(encoding="utf-8"))
            if from_model
            else dg.extract(text, document.name)
        )
        model = dg.verify(model, text)
    except (dg.DiagramError, OSError, ValueError) as exc:
        err.print(f"[red]✗ {escape(str(exc))}[/red]")
        raise typer.Exit(2) from exc
    svg = dg.render(model, animate=not static)
    problems = dg.svg_problems(svg)
    if problems:  # never write an unsafe SVG, whatever the input
        err.print("[red]✗ " + "; ".join(problems) + "[/red]")
        raise typer.Exit(1)
    out = output or document.with_suffix(".svg")
    out.write_text(svg, encoding="utf-8")
    if model_out:
        model_out.write_text(
            json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    hyp = sum(1 for r in model["relations"] if r["status"] != "cited")
    summary = {
        "svg": str(out),
        "entities": len(model["entities"]),
        "relations": len(model["relations"]),
        "hypotheses": hyp,
    }
    if as_json:
        console.print_json(json.dumps(summary))
    else:
        console.print(
            f"[green]✓[/green] {summary['relations']} cited relationships, {summary['entities']} entities"
            + (f", [yellow]{hyp} hypotheses[/yellow]" if hyp else "")
            + f" → {out}"
        )
