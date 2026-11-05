#!/usr/bin/env python3
"""Build the website's demos: a report on the example shop and its notebooks, and one on Dev Guru itself.

    uv run python scripts/build_demo.py website/public/demo

The first checks the example's dependencies at osv.dev, so its CVEs page has something to show. It sends package names
and versions, and nothing else.
"""

# ruff: noqa: S603, S607
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "website/public/demo").resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        shop = Path(scratch) / "shop"
        shutil.copytree(REPOSITORY / "acceptance" / "fixtures" / "shop", shop)
        shutil.copytree(REPOSITORY / "acceptance" / "fixtures" / "notebooks", shop / "course")
        for report in (REPOSITORY / "acceptance" / "fixtures" / "reports").iterdir():
            shutil.copy(report, shop / report.name)
        for pinned in shop.rglob(
            "*.pins"
        ):  # old on purpose, and kept out of this repository as manifests
            pinned.rename(pinned.with_suffix(""))
        subprocess.run(["git", "init", "-q", str(shop)], check=True)
        subprocess.run(
            [
                "dev",
                "explore",
                str(shop),
                "-o",
                str(out / "dev-guru-explorer.html"),
                "--name",
                "Example shop",
                "--check-vulnerabilities",
            ],
            check=True,
        )
    subprocess.run(
        [
            "dev",
            "explore",
            str(REPOSITORY / "src"),
            "-o",
            str(out / "dev-guru-on-itself.html"),
            "--name",
            "Dev Guru",
        ],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
