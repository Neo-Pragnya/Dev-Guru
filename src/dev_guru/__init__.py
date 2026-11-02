"""Dev Guru: a local-first developer product on the Ananke Plexus harness."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dev_guru.version import __version__

if TYPE_CHECKING:
    from dev_guru.sdk import GuruClient

__all__ = ["GuruClient", "__version__"]


def __getattr__(name: str) -> Any:
    # Lazy, so `import dev_guru` stays cheap and submodules never import the package's SDK back (no cycle).
    if name == "GuruClient":
        from dev_guru.sdk import GuruClient

        return GuruClient
    raise AttributeError(f"module 'dev_guru' has no attribute {name!r}")
