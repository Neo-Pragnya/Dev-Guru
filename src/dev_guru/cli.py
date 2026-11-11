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
LogsOpt = Annotated[
    Path | None,
    typer.Option(
        "--logs",
        help="Write what happened, with versions, timings and any error in full, to this file. No secrets or file contents",
    ),
]


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
    check_vulnerabilities: Annotated[
        bool,
        typer.Option(
            "--check-vulnerabilities",
            help="Also look up dependencies at osv.dev. Sends package names and versions, and nothing else",
        ),
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Also say what each step found, as it goes")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Say nothing until it's done")
    ] = False,
    logs: LogsOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """Explore a codebase: Ananke builds the graph, Dev Guru writes an interactive, offline HTML explorer.

    The report is one file with no network access: architecture constellation, dependency flow, impact rings,
    call graph, hotspots, a guided tour, search and a source inspector.
    """
    if logs is not None:
        from dev_guru import logs as log_file

        err.print(f"[dim]Writing a log to {log_file.start(logs, 'explore')}[/dim]")
    try:
        client = connect(transport)
        from dev_guru.progress import Shown, Silent

        # steps go to stderr, so --json on stdout stays clean
        # --json is for scripts, so it says nothing else unless asked to with --verbose
        shown = Silent() if quiet or (as_json and not verbose) else Shown(verbose=verbose)
        result = service.explore(
            workspace,
            client=client,
            name=name,
            profile=profile,
            check_vulnerabilities=check_vulnerabilities,
            progress=shown,
        )
        page, sidecar = service.export_html(result, output, client=client, progress=shown)
    except errors.GuruError as exc:
        from dev_guru.logs import LOGGER

        LOGGER.error("%s: %s", exc.code, exc)
        _fail(exc, as_json, 1)
        return
    except Exception:
        from dev_guru.logs import LOGGER

        LOGGER.exception("dev explore stopped on an unexpected error")
        raise
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
def sources(
    query: Annotated[str, typer.Argument(help="Words to match (optional)")] = "",
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help="Project whose sources to read")
    ] = Path("."),
    html_out: Annotated[
        Path | None, typer.Option("--html", help="Also write an offline picker page")
    ] = None,
    transport: TransportOpt = "in-process",
    as_json: JsonOpt = False,
) -> None:
    """Browse capabilities from every source the project configures (internal folders, private Git, troves).

    Source-neutral: Dev Guru asks Ananke's provider port; Dex Trove is just one optional source.
    """
    from dev_guru.reports import pages

    try:
        found = connect(transport).discover_capabilities(workspace, query)
    except errors.GuruError as exc:
        _fail(exc, as_json, 1)
        return
    rows = [c.model_dump() for c in found]
    if html_out is not None:
        html_out.write_text(pages.sources_page(rows), encoding="utf-8")
    if as_json:
        console.print_json(json.dumps(rows))
        return
    for c in found:
        console.print(f"{c.identity}@{c.version}  [dim]{escape(c.summary[:80])}[/dim]")
    console.print(f"{len(found)} capabilities" + (f" · picker: {html_out}" if html_out else ""))


learning_app = typer.Typer(
    help="Review what Ananke learned before it becomes reusable memory.", no_args_is_help=True
)
app.add_typer(learning_app, name="learning")


@learning_app.command("review")
def learning_review(
    name: Annotated[str, typer.Argument(help="Candidate name (see `ananke learning list`)")],
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("."),
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Review page (default <name>-review.html)")
    ] = None,
    open_browser: Annotated[bool, typer.Option("--open")] = False,
    transport: TransportOpt = "in-process",
    as_json: JsonOpt = False,
) -> None:
    """A review page for a learning candidate: gate status, evaluation, review, provenance and per-destination diff.

    Reviewing changes nothing: approve with `ananke learning review` and promote with `ananke learning promote`.
    """
    from dev_guru.reports import pages

    try:
        cand = connect(transport).learning_candidate(workspace, name)
    except errors.GuruError as exc:
        _fail(exc, as_json, 1)
        return
    out = output or Path(f"{name}-review.html")
    out.write_text(pages.review_page(cand.model_dump()), encoding="utf-8")
    if as_json:
        console.print_json(json.dumps(cand.model_dump() | {"page": str(out)}))
    else:
        state = (
            "[green]ready to promote[/green]"
            if not cand.problems
            else "[yellow]" + escape("; ".join(cand.problems)) + "[/yellow]"
        )
        console.print(f"{name}: {state} → {out}")
    if open_browser:
        webbrowser.open(out.resolve().as_uri())


@learning_app.command("graph")
def learning_graph(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("."),
    fmt: Annotated[str, typer.Option("--format", "-f", help="mermaid or json")] = "mermaid",
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write here instead of printing")
    ] = None,
    transport: TransportOpt = "in-process",
) -> None:
    """A map of what has been learned: each lesson, the runs it came from, the files it mentions, and the terms
    lessons share. It only reads; promote a reviewed lesson with `ananke learning promote`."""
    from dev_guru import mentor

    if fmt not in ("mermaid", "json"):
        typer.echo(
            f"error: unknown format {fmt!r}; choose mermaid or json ({errors.INVALID_INPUT})",
            err=True,
        )
        raise typer.Exit(2)
    try:
        graph = service.learning_map(workspace, client=connect(transport))
    except errors.GuruError as exc:
        typer.echo(f"error: {exc.message} ({exc.code})", err=True)
        raise typer.Exit(2) from exc
    text = (
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n"
        if fmt == "json"
        else mentor.graph_mermaid(graph)
    )
    if output:
        output.write_text(text, encoding="utf-8")
        typer.echo(
            f"Wrote {output}: {graph['lessons']} lessons, {len(graph['patterns'])} shared terms",
            err=True,
        )
    else:
        typer.echo(text, nl=False)


@app.command()
def serve(
    workspaces: Annotated[
        list[Path] | None, typer.Argument(help="Projects the browser may reach (default: here)")
    ] = None,
    port: Annotated[int, typer.Option(help="Local port (default: any free one)")] = 0,
    open_browser: Annotated[bool, typer.Option("--open/--no-open", help="Open the browser")] = True,
    transport: TransportOpt = "in-process",
    logs: LogsOpt = None,
) -> None:
    """Start the local web gateway. It only listens on this computer, and only the printed link gets in."""
    from dev_guru.gateway import Gateway

    if logs is not None:
        from dev_guru import logs as log_file

        err.print(f"[dim]Writing a log to {log_file.start(logs, 'serve')}[/dim]")

    try:
        client = connect(transport)
        client.require_compatible()  # type: ignore[attr-defined]
        gateway = Gateway(workspaces or [Path.cwd()], client, port=port)
    except errors.GuruError as exc:
        _fail(exc, False, 2)
    except OSError as exc:
        _fail(
            errors.GuruError(errors.INVALID_INPUT, f"can't listen on port {port}: {exc}"), False, 2
        )
    # printed plainly: rich would wrap a long link, and this link is the way in
    print(
        f"Dev Guru is listening on this computer only. Open this link, which works once:\n{gateway.login_url}",
        flush=True,
    )
    if open_browser:
        webbrowser.open(gateway.login_url)
    try:
        gateway.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        gateway.shutdown()


@app.command()
def context(
    workspace: Annotated[Path, typer.Argument(help="The repository")] = Path("."),
    budget: Annotated[int, typer.Option("--budget", help="Most tokens the map may use")] = 1500,
    tools: Annotated[
        bool, typer.Option("--tools", help="Which tools are ready, not the map")
    ] = False,
    transport: TransportOpt = "in-process",
    as_json: JsonOpt = False,
) -> None:
    """A small map of a repository for an AI assistant, and which tool to use next."""
    try:
        client = connect(transport)
        result = (
            client.context_status(workspace)
            if tools
            else client.context_map(workspace, budget=budget)
        )
    except errors.GuruError as exc:
        _fail(exc, as_json, 1)
        return
    if as_json or tools:
        typer.echo(json.dumps(result, indent=1))
    else:
        typer.echo(result["map"])


@app.command()
def bpmn(
    document: Annotated[
        Path, typer.Argument(help="A Markdown process, or a .bpmn file to read back")
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Viewer page (default <document>.process.html)"),
    ] = None,
    xml: Annotated[Path | None, typer.Option("--xml", help="Also write BPMN 2.0 XML here")] = None,
    svg: Annotated[
        Path | None, typer.Option("--svg", help="Also write the swimlane drawing here")
    ] = None,
    markdown: Annotated[
        Path | None,
        typer.Option(
            "--markdown",
            help="Also write the process as Markdown dev bpmn reads (to edit it as text)",
        ),
    ] = None,
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("."),
    transport: TransportOpt = "in-process",
) -> None:
    """Swimlanes and BPMN from a reviewed process. Ananke reads it, nothing is guessed, and nothing runs.

    The viewer walks through the process (you choose at each decision), lists every way through it, and lets you
    rename steps and lanes and download the result as Markdown to run through dev bpmn again.
    """
    from dev_guru import bpmn as drawing

    try:
        text = document.read_text(encoding="utf-8")
        client = connect(transport)
        if document.suffix.lower() == ".bpmn":
            answer = client.process_model(workspace, "", document.name, text)
        else:
            answer = client.process_model(workspace, text, document.name)
    except (errors.GuruError, OSError, UnicodeDecodeError) as exc:
        code = getattr(exc, "code", errors.INVALID_INPUT)
        typer.echo(f"error: {getattr(exc, 'message', exc)} ({code})", err=True)
        raise typer.Exit(2) from exc
    model = answer["model"]
    page = output or document.with_suffix(".process.html")
    page.write_text(drawing.viewer(model, answer["bpmn"]), encoding="utf-8")
    if xml:
        xml.write_text(answer["bpmn"], encoding="utf-8")
    if svg:
        svg.write_text(drawing.render(model), encoding="utf-8")
    if markdown:
        markdown.write_text(drawing.to_markdown(model), encoding="utf-8")
    typer.echo(f"Wrote {page}: {len(model['lanes'])} lanes and {len(model['nodes'])} steps")
    for problem in model["problems"]:
        typer.echo(f"problem: {problem}", err=True)
    if model["problems"]:
        raise typer.Exit(1)


@app.command()
def mentor(
    workspace: Annotated[Path, typer.Argument(help="Project whose Ananke runs to read")] = Path(
        "."
    ),
    level: Annotated[
        str, typer.Option(help="novice, practitioner, principal or executive")
    ] = "practitioner",
    min_repeats: Annotated[
        int,
        typer.Option(help="Advise only on failures seen in at least this many runs (2 or more)"),
    ] = 2,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write Markdown here")
    ] = None,
    transport: TransportOpt = "in-process",
    as_json: JsonOpt = False,
) -> None:
    """Advice from evidence: failures that repeat across this workspace's Ananke runs, what they mean, and any
    reviewed lesson on the same thing. Nothing is a judgement of style, and a failure seen once gets no advice."""
    from dev_guru import mentor as mentoring

    try:
        fb = service.mentor_feedback(
            workspace, client=connect(transport), level=level, min_repeats=min_repeats
        )
    except errors.GuruError as exc:
        typer.echo(f"error: {exc.message} ({exc.code})", err=True)
        raise typer.Exit(2) from exc
    if as_json:
        typer.echo(json.dumps(fb, indent=2, ensure_ascii=False))
        return
    text = mentoring.feedback_markdown(fb)
    if output:
        output.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {output}: {len(fb['advice'])} pieces of advice", err=True)
    else:
        typer.echo(text)


@app.command()
def docs(
    workspace: Annotated[Path, typer.Argument(help="Project to document")] = Path("."),
    audience: Annotated[
        str, typer.Option(help="novice, practitioner, principal or executive")
    ] = "practitioner",
    detail: Annotated[str, typer.Option(help="brief, standard or deep")] = "standard",
    fmt: Annotated[
        str,
        typer.Option(
            "--format", "-f", help="md, slides (Markdown for dev present), deck (HTML) or json"
        ),
    ] = "md",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="File to write (default dev-guru-<audience>.<ext>)"),
    ] = None,
    name: Annotated[str | None, typer.Option(help="Project name shown in the document")] = None,
    transport: TransportOpt = "in-process",
) -> None:
    """Documentation for one audience at one depth, written from the code, every statement linked to its line.

    It ends with its provenance (revision, versions, the model's digest), and a manifest with the file's sha256 is
    written next to it. Every link is checked before the file is kept.
    """
    import hashlib

    from dev_guru import present as deck
    from dev_guru.explain import docs as writer

    ext = {"md": "md", "slides": "slides.md", "deck": "html", "json": "json"}
    if fmt not in ext:
        typer.echo(
            f"error: unknown format {fmt!r}; choose {', '.join(ext)} ({errors.INVALID_INPUT})",
            err=True,
        )
        raise typer.Exit(2)
    try:
        doc, result = service.documentation(
            workspace, client=connect(transport), audience=audience, detail=detail, name=name
        )
    except errors.GuruError as exc:
        typer.echo(f"error: {exc.message} ({exc.code})", err=True)
        raise typer.Exit(2) from exc
    out = output or Path(f"dev-guru-{audience}.{ext[fmt]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    elif fmt == "md":
        text = writer.to_markdown(doc, root=result.workspace, out_dir=out.parent.resolve())
        broken = writer.check_links(text, out.parent.resolve())
        if broken:  # a renderer bug, not the user's input: never keep a document with broken links
            typer.echo("error: broken links: " + "; ".join(broken[:5]), err=True)
            raise typer.Exit(1)
    else:
        text = writer.to_slides(doc)
        if fmt == "deck":
            text = deck.build(text, out.parent)
            problems = deck.check(text)
            if problems:
                typer.echo("error: " + "; ".join(problems), err=True)
                raise typer.Exit(1)
    out.write_text(text, encoding="utf-8")
    receipt = {
        "schema": "dev-guru/document-manifest@1",
        "document": out.name,
        "format": fmt,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "audience": audience,
        "detail": detail,
        **doc["provenance"],
    }
    sidecar = out.with_name(out.name + ".manifest.json")
    sidecar.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    statements = sum(len(s["statements"]) for s in doc["sections"])
    typer.echo(
        f"Wrote {out}: {len(doc['sections'])} sections, {statements} statements · manifest {sidecar.name}"
    )


@app.command()
def explain(
    focus: Annotated[str, typer.Argument(help="A file, a symbol, path:name or an id")],
    workspace: Annotated[Path, typer.Option("--workspace", "-w", help="Project")] = Path("."),
    level: Annotated[
        list[str] | None,
        typer.Option(
            "--level",
            "-l",
            help="novice, practitioner, principal or executive (repeat; default all)",
        ),
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write Markdown here")
    ] = None,
    transport: TransportOpt = "in-process",
    as_json: JsonOpt = False,
) -> None:
    """Explain one file or symbol from novice to executive, every statement tied to the lines it comes from.

    Nothing is generated by a model: the same code gives the same explanation. Calls found through imports are
    marked inferred.
    """
    from dev_guru.explain import docs as writer

    try:
        exp, result = service.explanation(
            workspace, focus, client=connect(transport), levels=tuple(level) if level else None
        )
    except errors.GuruError as exc:
        typer.echo(f"error: {exc.message} ({exc.code})", err=True)
        raise typer.Exit(2) from exc
    if as_json:
        typer.echo(json.dumps(exp, indent=2, ensure_ascii=False))
        return
    out_dir = (output.parent if output else Path(".")).resolve()
    text = writer.explanation_markdown(exp, root=result.workspace, out_dir=out_dir)
    if output:
        output.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(text)


@app.command()
def graph(
    workspace: Annotated[Path, typer.Argument(help="Project to draw")] = Path("."),
    level: Annotated[str, typer.Option(help="package, file or symbol")] = "file",
    focus: Annotated[
        str | None,
        typer.Option(help="Start here: an id, a path, a file name or a symbol name"),
    ] = None,
    depth: Annotated[int, typer.Option(help="How many steps out from --focus")] = 1,
    budget: Annotated[int, typer.Option(help="The most nodes to draw (1 to 400)")] = 40,
    fmt: Annotated[str, typer.Option("--format", "-f", help="mermaid, svg or json")] = "mermaid",
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write here instead of printing")
    ] = None,
    static: Annotated[bool, typer.Option("--static", help="SVG without animation")] = False,
    name: Annotated[str | None, typer.Option(help="Project name shown in the drawing")] = None,
    transport: TransportOpt = "in-process",
) -> None:
    """Draw part of the code graph as Mermaid or SVG, small enough to read and expand a step at a time.

    Nodes marked +N have N neighbours that weren't drawn; the output names the command that shows them.
    Inferred calls are dashed.
    """
    from dev_guru.diagram import svg_problems
    from dev_guru.reports import subgraph

    if fmt not in subgraph.FORMATS:
        typer.echo(
            f"error: unknown format {fmt!r}; choose {', '.join(subgraph.FORMATS)} ({errors.INVALID_INPUT})",
            err=True,
        )
        raise typer.Exit(2)
    try:
        sub = service.graph_export(
            workspace,
            client=connect(transport),
            level=level,
            focus=focus,
            depth=depth,
            budget=budget,
            name=name,
        )
    except errors.GuruError as exc:
        typer.echo(f"error: {exc.message} ({exc.code})", err=True)
        raise typer.Exit(2) from exc
    if fmt == "json":
        text = json.dumps(sub, indent=2, ensure_ascii=False) + "\n"
    elif fmt == "svg":
        text = subgraph.to_svg(sub, animate=not static)
        problems = svg_problems(text)
        if problems:  # never write an unsafe SVG, whatever the names in the code
            typer.echo("error: " + "; ".join(problems), err=True)
            raise typer.Exit(1)
    else:
        text = subgraph.to_mermaid(sub)
    if output:
        output.write_text(text, encoding="utf-8")
        typer.echo(
            f"Wrote {output}: {len(sub['nodes'])} nodes, {len(sub['edges'])} edges"
            + (f", {sub['omitted']['nodes']} not drawn" if sub["omitted"]["nodes"] else ""),
            err=True,
        )
    else:
        typer.echo(text, nl=False)
    if sub["expand"]:
        typer.echo(f"more: {sub['expand']}", err=True)


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
            f"[green]✓[/green] {len(model['relations']) - hyp} cited relationships, {summary['entities']} entities"
            + (f", [yellow]{hyp} hypotheses[/yellow]" if hyp else "")
            + f" → {out}"
        )
