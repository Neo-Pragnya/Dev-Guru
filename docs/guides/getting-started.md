---
title: Getting started
description: Install Dev Guru, explore your first project and find your way around the report.
---

# Getting started

## Install

Dev Guru needs Python 3.11 or newer. It installs Ananke Plexus, the harness that does the analysis, as a dependency.

```bash
pip install dev-guru          # or: uv tool install dev-guru
dev --version
dev doctor
```

**Behind a package firewall.** Some firewalls block any version published in the last week or two. If a dependency,
such as `pydantic`, has a release that new, installing Dev Guru fails even though Dev Guru is allowed. uv can skip just
those packages' newest releases:

```bash
uv pip install dev-guru --exclude-newer-package pydantic=2026-10-22 --exclude-newer-package pydantic-core=2026-10-22
```

The release's scan report lists which dependencies were days old, with the exact command.

`dev doctor` confirms the Ananke version is in the supported range and that the capabilities Dev Guru calls are
present:

```console
$ dev doctor
dev-guru 0.1.0 · Python 3.12.7 · transport in-process
✓ ananke-plexus 0.3.12 (supported >=0.3.12,<0.4)
  ✓ graph.build
  ✓ graph.load
  ✓ graph.impact
  ✓ run.status
  ✓ spec.create
  ✓ registry.open
  dex-trove: not installed (optional)
```

## Explore a project

```bash
dev explore path/to/project -o explorer.html --open
```

```console
✓ 303 files · 2038 symbols · 564 imports · 2173 calls → explorer.html
  manifest explorer.html.manifest.json · sha256:b9333576596…
```

Ananke parses the project's Python files: files, classes, functions and methods, imports, and calls and base
classes inferred through imports. Dev Guru turns that graph into the report, plus a manifest saying exactly what went
into it.

> [!NOTE]
> Ananke keeps its working state in a `.ananke/` folder inside the project (the graph snapshot and its project
> layout). Add `.ananke/` to your `.gitignore` if it isn't there already.

## Find your way around

- **Top bar:** 25 views (keys `1`–`6` for the first six), search (`/`), the command palette (`Ctrl`/`⌘` `K`), the theme toggle
  (`T`), and *About*, with the limitations and the manifest.
- **Left:** "start here" cards (tour, most depended-on file, import cycles, largest file) and the package tree.
- **Centre:** the current view. Scroll to zoom, drag to pan, `F` to fit.
- **Right:** the inspector for whatever you pick: path, docstring, signature, source with line numbers, and every
  connection, each one clickable.

The URL keeps your view, selection and theme, so you can bookmark or share a view of the report.

Next: [the explorer, view by view](explorer.md).
