"""Decks and diagrams from a repository's Markdown, on request. Each comes back as a file: nothing is written here."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MAX_BYTES = 2_000_000
MAX_LISTED = 300
_SKIP = {"node_modules", "__pycache__", "venv", "dist", "build", "site-packages"}


class DocumentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def listed(root: Path) -> list[dict[str, Any]]:
    found = []
    for folder, directories, names in os.walk(root):
        directories[:] = sorted(d for d in directories if not d.startswith(".") and d not in _SKIP)
        for name in sorted(names):
            if not name.lower().endswith(".md"):
                continue
            path = Path(folder, name)
            try:
                if path.is_symlink() or path.stat().st_size > MAX_BYTES:
                    continue
                lines = path.read_text(encoding="utf-8", errors="replace").count("\n")
            except OSError:
                continue
            found.append({"path": path.relative_to(root).as_posix(), "lines": lines})
            if len(found) >= MAX_LISTED:
                return found
    return found


def _read(root: Path, path: str) -> tuple[Path, str]:
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, path))
    if not target.startswith(base + os.sep) or not target.lower().endswith(".md"):
        raise DocumentError("PATH_DENIED", f"{path} isn't a Markdown file in this workspace")
    if not os.path.isfile(target) or os.path.getsize(target) > MAX_BYTES:
        raise DocumentError("SOURCE_NOT_FOUND", f"{path} isn't a readable Markdown file here")
    with open(target, encoding="utf-8", errors="replace") as handle:
        return Path(target), handle.read()


def build(root: Path, path: str, what: str) -> dict[str, Any]:
    source, text = _read(root, path)
    if what == "deck":
        from dev_guru import present as deck

        try:
            page = deck.build(text, source.parent)
        except (deck.DeckError, OSError) as exc:
            raise DocumentError("DECK_FAILED", str(exc)) from exc
        return {
            "name": f"{source.stem}.html",
            "media_type": "text/html",
            "content": page,
            "problems": list(deck.check(page)),
            "summary": "Open it in a browser. It works offline.",
        }
    if what == "diagram":
        from dev_guru import diagram as dg

        try:
            model = dg.verify(dg.extract(text, source.name), text)
        except (dg.DiagramError, OSError, ValueError) as exc:
            raise DocumentError("DIAGRAM_FAILED", str(exc)) from exc
        svg = dg.render(model)
        return {
            "name": f"{source.stem}.svg",
            "media_type": "image/svg+xml",
            "content": svg,
            "problems": list(dg.svg_problems(svg)),
            "summary": "It draws what the document states.",
        }
    raise DocumentError("INVALID_REQUEST", "what must be deck or diagram")


__all__ = ["DocumentError", "build", "listed"]
