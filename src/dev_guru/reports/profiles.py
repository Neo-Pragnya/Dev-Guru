"""Publication profiles for explorer reports.

``private`` (default): everything the explorer can show, for your own machine or team.
``public``: safe to publish outside the team. It removes code and text written inside the code (symbol source,
docstrings), and the Git revision and dirty flag. It keeps structure: files, sizes, packages, imports, calls and
signatures (with string defaults blanked). The report says what was removed, and the manifest records the profile.
"""

from __future__ import annotations

import copy
import re
from typing import Any

PROFILES = ("private", "public")
_STRING = re.compile(r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"")
PUBLIC_NOTE = (
    "Published with the public profile: source code, docstrings and the Git revision were removed; structure, "
    "sizes and relationships remain."
)


def apply(
    model: dict[str, Any], manifest: dict[str, Any], profile: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Copies of the view model and manifest, reduced to what ``profile`` allows."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; choose {', '.join(PROFILES)}")
    model, manifest = copy.deepcopy(model), copy.deepcopy(manifest)
    manifest["profile"] = profile
    if profile == "private":
        return model, manifest
    for sym in model.get("symbols", []):
        sym["source"] = ""
        sym["doc"] = ""
        # keep the shape of a signature, not literal defaults (a URL, a key, a path)
        sym["signature"] = _STRING.sub("'…'", str(sym.get("signature", "")))
    for f in model.get("files", []):
        f["doc"] = ""
    model["limitations"] = [*model.get("limitations", []), PUBLIC_NOTE]
    manifest["limitations"] = model["limitations"]
    manifest["workspace"] = {"name": manifest.get("workspace", {}).get("name", "")}
    from dev_guru.reports.render import digest

    manifest["input_digest"] = digest(model)  # what the published report actually contains
    return model, manifest


__all__ = ["PROFILES", "PUBLIC_NOTE", "apply"]
