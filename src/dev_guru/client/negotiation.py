"""Which Ananke Plexus this Dev Guru supports, and what the installed one can do.

Negotiation is explicit: Dev Guru reads the installed harness version, checks it against ``SUPPORTED_ANANKE`` and
probes the specific interfaces it calls. An out-of-range or incomplete harness is an error with a stable code,
never a silent downgrade.
"""

from __future__ import annotations

import importlib
import re
from importlib import metadata

SUPPORTED_ANANKE = ">=0.3.36,<0.4"  # keep in step with pyproject.toml (tests/test_packaging.py)
APP_PROTOCOL = "ananke-app/1"  # the app facade protocol this Dev Guru speaks

# Capability id -> (module, attribute path). Required ones are what this release of Dev Guru calls.
CAPABILITIES: dict[str, tuple[str, str]] = {
    "graph.build": ("ananke.plexus.api", "Ananke.graph_build"),
    "graph.load": ("ananke.plexus.graph.service", "load_graph"),
    "graph.impact": ("ananke.plexus.api", "Ananke.graph_impact"),
    "run.status": ("ananke.plexus.api", "Ananke.run_status"),
    "spec.create": ("ananke.plexus.api", "Ananke.create_spec"),
    "registry.open": ("ananke.plexus.registry.registry", "Registry.open"),
    "app.facade": ("ananke.plexus.app", "AppFacade.submit_run"),
    "sources.discover": ("ananke.plexus.registry.providers", "from_project"),
    "learning.gate": ("ananke.plexus.learning", "gate"),
}
REQUIRED = ("graph.build", "graph.load", "app.facade")


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", text.strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


_MIN, _BELOW = (
    tuple(int(part) for part in bound.split("."))
    for bound in re.fullmatch(r">=([\d.]+),<([\d.]+)", SUPPORTED_ANANKE).groups()  # type: ignore[union-attr]
)


def supported(version: str) -> bool:
    parsed = parse_version(version)
    return parsed is not None and _MIN <= parsed < _BELOW


def installed_version(distribution: str = "ananke-plexus") -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def probe(capabilities: dict[str, tuple[str, str]] = CAPABILITIES) -> dict[str, bool]:
    """Which capabilities the importable harness exposes (imports only; nothing runs)."""
    found: dict[str, bool] = {}
    for cap, (module, attr_path) in capabilities.items():
        try:
            # False positive: module names come from the fixed CAPABILITIES table above, never from a request or a file.
            # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
            obj: object = importlib.import_module(module)
            for part in attr_path.split("."):
                obj = getattr(obj, part)
            found[cap] = callable(obj)
        except (ImportError, AttributeError):
            found[cap] = False
    return found


__all__ = [
    "CAPABILITIES",
    "REQUIRED",
    "SUPPORTED_ANANKE",
    "installed_version",
    "parse_version",
    "probe",
    "supported",
]
