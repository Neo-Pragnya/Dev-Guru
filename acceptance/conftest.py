"""Acceptance suite: shared harness steps plus repo-specific ones."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Works under any pytest import mode (importlib mode does not put this folder on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import *  # noqa: E402,F403  (steps, sandbox fixture and the release-gate hooks)
from harness import REPO, Sandbox  # noqa: E402
from pytest_bdd import then  # noqa: E402

collect_ignore = [
    "fixtures",
    "site",
]  # fixture projects may carry their own tests; they are data here

VERSION_FILE = "src/dev_guru/version.py"


@then("the output names the package version")
def output_has_version(sandbox: Sandbox) -> None:
    text = (REPO / VERSION_FILE).read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert match, f"no __version__ in {VERSION_FILE}"
    assert match.group(1) in sandbox.last.stdout, sandbox.last.describe()
