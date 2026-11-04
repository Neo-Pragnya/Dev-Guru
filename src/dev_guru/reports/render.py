"""Render an explorer view model into one self-contained, offline HTML file.

Guarantees (tests/test_reports.py):

- **Offline.** CSS and JavaScript are inlined; no CDN, font, telemetry or network URL is referenced.
- **Safe.** The data is embedded as JSON in a ``<script type="application/json">`` block with ``<``, ``>``, ``&``
  and the U+2028/U+2029 separators escaped, so source text can never close the script or run as HTML. The page
  shows all untrusted text through ``textContent``.
- **View-only.** Opening the file runs no command and contacts no server. Requests for deeper analysis download a
  request file for Dev Guru or Ananke to run explicitly.
- **Traceable.** A manifest records the renderer version, the harness version, the input digest and the workspace
  revision. It is embedded in the page and written next to it as ``<name>.manifest.json``.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
from datetime import UTC, datetime

# False positive: this package needs Python 3.11 or newer (requires-python), where importlib.resources always exists.
# nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2
from importlib import resources
from pathlib import Path
from typing import Any

from dev_guru.version import __version__

RENDERER = "dev-guru/explorer-html@1"
PLACEHOLDER = re.compile(r"\{\{(TITLE|CSS|JS|DATA|MANIFEST)\}\}")
LS, PS = (
    chr(0x2028),
    chr(0x2029),
)  # line/paragraph separators: legal in JSON, not in older JS string literals
MANIFEST_SCHEMA = "dev-guru/report-manifest@1"


def safe_json(data: Any) -> str:
    """JSON that is safe inside an HTML ``<script>`` element."""
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace(LS, "\\u2028")
        .replace(PS, "\\u2029")
    )


def digest(data: Any) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _git(root: Path, *args: str, timeout: int = 5) -> subprocess.CompletedProcess[str]:
    """A fixed git argv (no shell); git comes from PATH like any developer tool."""
    argv = ["git", "-C", str(root), *args]
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603


def _revision(root: Path) -> dict[str, Any]:
    try:
        head = _git(root, "rev-parse", "HEAD")
        if head.returncode != 0:
            return {"vcs": None}
        dirty = _git(root, "status", "--porcelain", "--untracked-files=no", timeout=10)
        return {"vcs": "git", "commit": head.stdout.strip(), "dirty": bool(dirty.stdout.strip())}
    except (OSError, subprocess.TimeoutExpired):
        return {"vcs": None}


def _generated_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")  # reproducible builds
    moment = (
        datetime.fromtimestamp(int(epoch), UTC) if epoch and epoch.isdigit() else datetime.now(UTC)
    )
    return moment.replace(microsecond=0).isoformat()


def manifest(
    model: dict[str, Any], *, workspace: Path, ananke_version: str | None, snapshot_id: str
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "renderer": RENDERER,
        "dev_guru": __version__,
        "ananke": ananke_version,
        "view_model": model["schema"],
        "snapshot_id": snapshot_id,
        "input_digest": digest(model),
        "workspace": {"name": model["project"]["name"], **_revision(workspace)},
        "publication": "offline-single-file",
        "generated_at": _generated_at(),
        "limitations": model["limitations"],
    }


def _asset(name: str) -> str:
    return resources.files("dev_guru.reports").joinpath("assets", name).read_text(encoding="utf-8")


def render(
    model: dict[str, Any], report_manifest: dict[str, Any], *, title: str | None = None
) -> str:
    page = _asset("explorer.html")
    name = title or f"{model['project']['name']} · Dev Guru explorer"
    values = {
        "TITLE": html.escape(name),
        "CSS": _asset("explorer.css"),
        "JS": _asset("explorer.js"),
        "DATA": safe_json(model),
        "MANIFEST": safe_json(report_manifest),
    }
    # One pass over the template only: inserted content (source code may itself contain "{{MANIFEST}}")
    # is never scanned again.
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], page)


def write(
    model: dict[str, Any],
    report_manifest: dict[str, Any],
    output: Path,
    *,
    title: str | None = None,
) -> tuple[Path, Path]:
    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(model, report_manifest, title=title), encoding="utf-8")
    sidecar = output.with_name(output.name + ".manifest.json")
    sidecar.write_text(
        json.dumps(report_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output, sidecar


__all__ = ["MANIFEST_SCHEMA", "RENDERER", "digest", "manifest", "render", "safe_json", "write"]
