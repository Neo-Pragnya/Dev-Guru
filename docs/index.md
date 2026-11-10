---
title: Dev Guru
description: Understand, improve, verify and learn from your software, locally. A developer product on the Ananke Plexus harness.
---

# Dev Guru

Dev Guru turns your codebase into something you can **see and question**. Point it at a project and it writes one
interactive, offline HTML report: a living map of packages and files, the flow of dependencies, the blast radius of a
change, who calls what, where the hotspots are, and a guided tour, with the source one click away.

```bash
pip install dev-guru
dev explore path/to/project -o explorer.html --open
```

Everything is computed locally by [Ananke Plexus](https://neo-pragnya.github.io/Ananke-Plexus/), the engineering
harness Dev Guru runs on. The report is one file: no server, no network, nothing to install to view it.

Dev Guru is on PyPI as [`dev-guru`](https://pypi.org/project/dev-guru/).

## What you can do today

| Command | What you get |
| --- | --- |
| `dev explore` | The explorer report: constellation, flow, impact rings, calls, hotspots and a tour |
| `dev present` | One offline, accessible HTML deck from Markdown slides |
| `dev diagram` | An animated SVG of what a document states, every edge cited |
| `dev explain` | One file or function explained at four levels, from newcomer to leader, every statement cited |
| `dev docs` | Documentation for one audience and depth, with provenance and checked links |
| `dev graph` | Part of the code graph as Mermaid or SVG: a focus, a depth and a budget, expandable a step at a time |
| `dev sources` | Capabilities from your folders, private Git and Dex Trove |
| `dev serve` | A local web interface: live runs, the code graph and your capabilities. See [The local gateway](guides/gateway.md) |
| `dev learning review` | A review page for what Ananke learned, before it becomes reusable |
| `dev doctor` | Checks that a compatible Ananke is installed and has what Dev Guru needs |
| `GuruClient(...).explore()` | The same, from Python |

## Where to go next

- [Getting started](guides/getting-started.md): install, explore your first project, read the report.
- [The explorer](guides/explorer.md): every view, and what it tells you.
- [Python SDK](guides/sdk.md): use Dev Guru from scripts and notebooks.
- [How it fits together](concepts/architecture.md): Dev Guru, Ananke Plexus and Dex Trove.
- [Report safety](concepts/report-safety.md): why a report can't run code or phone home.
- [Roadmap](roadmap.md): what's released and what's planned.
