"""What a long command is doing, as it does it. It writes to stderr, so it never mixes with ``--json`` on stdout.

A command reports steps (``with progress.step("Analysing the repository"):``) and, when it has them, details
(``progress.detail("1,204 files")``). How they show depends on who's watching:

- **A terminal:** each step with a spinner and a running clock, then a tick and how long it took.
- **Anything else** (a pipe, a CI log): one plain line when a step starts and one when it ends.
- **Verbose:** details as well.
- **Quiet:** nothing.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from rich.console import Console

from dev_guru.logs import LOGGER


class Progress(Protocol):
    """What the service layer reports to. The default does nothing, so the SDK stays silent."""

    def step(self, title: str) -> Any: ...

    def detail(self, text: str) -> None: ...

    def warn(self, text: str) -> None: ...


class Silent:
    """Reports nothing: for the SDK, tests and ``--quiet``."""

    @contextmanager
    def step(self, title: str) -> Iterator[None]:
        with _logged(title):
            yield

    def detail(self, text: str) -> None:
        LOGGER.debug("  %s", text)

    def warn(self, text: str) -> None:
        LOGGER.warning("%s", text)


class Shown:
    """Steps on stderr with how long each took, and details too when verbose."""

    def __init__(self, *, verbose: bool = False, console: Console | None = None) -> None:
        self.console = console or Console(stderr=True)
        self.verbose = verbose
        self.live = self.console.is_terminal

    @contextmanager
    def step(self, title: str) -> Iterator[None]:
        with _logged(title):
            yield from self._shown(title)

    def _shown(self, title: str) -> Iterator[None]:
        started = time.monotonic()
        if self.live:
            from rich.progress import Progress as Bar
            from rich.progress import SpinnerColumn, TextColumn, TimeElapsedColumn

            bar = Bar(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                TimeElapsedColumn(),
                console=self.console,
                transient=True,
            )
            with bar:
                bar.add_task(f"{title}…", total=None)
                try:
                    yield
                except BaseException:
                    self.console.print(
                        f"[red]✗[/red] {title} stopped after {time.monotonic() - started:.1f}s"
                    )
                    raise
        else:
            self.console.print(f"… {title}", highlight=False)
            try:
                yield
            except BaseException:
                self.console.print(
                    f"✗ {title} stopped after {time.monotonic() - started:.1f}s", highlight=False
                )
                raise
        self.console.print(
            f"[green]✓[/green] {title} [dim]{time.monotonic() - started:.1f}s[/dim]",
            highlight=False,
        )

    def detail(self, text: str) -> None:
        LOGGER.debug("  %s", text)
        if self.verbose:
            self.console.print(f"  [dim]{text}[/dim]", highlight=False)

    def warn(self, text: str) -> None:
        """Shown even without --verbose: it means a result is probably wrong."""
        LOGGER.warning("%s", text)
        self.console.print(f"[yellow]![/yellow] {text}", highlight=False)


@contextmanager
def _logged(title: str) -> Iterator[None]:
    started = time.monotonic()
    LOGGER.info("%s: started", title)
    try:
        yield
    except BaseException:
        LOGGER.exception("%s: failed after %.1fs", title, time.monotonic() - started)
        raise
    LOGGER.info("%s: done in %.1fs", title, time.monotonic() - started)


__all__ = ["Progress", "Shown", "Silent"]
