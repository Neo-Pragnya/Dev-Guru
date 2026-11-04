# Dev Guru

[![PyPI](https://img.shields.io/pypi/v/dev-guru)](https://pypi.org/project/dev-guru/)
[![Python](https://img.shields.io/pypi/pyversions/dev-guru)](https://pypi.org/project/dev-guru/)

**See your code. Understand it. Change it with confidence.**

Point Dev Guru at a Python project and get **one offline HTML explorer**:
- a 3D constellation of files you can orbit, where imports pull and packages cluster;
- the flow of dependencies;
- the blast radius of a change;
- who calls what, and where the hotspots are;
- a guided tour, with the source one click away.

Everything is computed locally by [Ananke Plexus](https://neo-pragnya.github.io/Ananke-Plexus/), and the report is
a single file you can share like a PDF.

```bash
pip install dev-guru
dev explore path/to/project -o explorer.html --open
```

![Dev Guru running dev doctor and dev explore](docs/assets/dev-explore.svg)

**[Documentation and a live demo →](https://neo-pragnya.github.io/Dev-Guru/)** · **[Dev Guru on PyPI →](https://pypi.org/project/dev-guru/)**: the site's hero runs the real
report of Dev Guru exploring its own source.

## What's in a report

| View | Question it answers |
| --- | --- |
| ✦ Constellation | What's here? A 3D force-directed graph: drag to orbit, hover to light up imports |
| ⇶ Flow | What depends on what? Entry side to foundations; cycles glow rose |
| ◎ Impact | What breaks if this changes? Blast-radius rings over importers and callers |
| ƒ Calls | Who calls in, and what goes out? A symbol-level ego network |
| ▦ Hotspots | Where is change expensive? A treemap of size against how depended-on a file is |
| ☄ Tour | Show me around: a narrated walk through the codebase |

Plus search (`/`), a command palette (`Ctrl`/`⌘` `K`), a source inspector, a light and dark theme, and shareable
URLs. Reports are **offline and view-only**, treat source as text, and carry a manifest with the input digest and the
Git revision. See [report safety](docs/concepts/report-safety.md).

## More than the explorer

```bash
dev present talk.md                  # Markdown slides → one offline, accessible HTML deck
dev diagram docs/arch.md             # an animated SVG of what a document states, every edge cited
dev explore . --profile public       # a report safe to publish: no source, docstrings or Git revision
dev sources                          # capabilities from your folders, private Git and Dex Trove
dev serve                            # a local web interface: live runs, the code graph, your capabilities
dev learning review NAME             # review what Ananke learned before it becomes reusable
```

## From Python

```python
from dev_guru import GuruClient

with GuruClient(workspace="path/to/project") as guru:
    result = guru.explore()
    guru.export(result, output="explorer.html")
```

## In your browser

`dev serve` opens a web interface to what Ananke computes. It shows what's connected, starts and follows runs (which
survive a reload or a lost connection, and stop only when you press Cancel), browses the code graph, and searches your
capabilities. It listens only on your computer, only the link it prints gets in, and it needs no Node: everything comes
from the [Dev Guru package on PyPI](https://pypi.org/project/dev-guru/). See [The local gateway](docs/guides/gateway.md).

What's coming next, including code maps, flows, ERDs and CVE views, is in the [roadmap](ROADMAP.md).

## How it fits together

| Repository | Role |
| --- | --- |
| **Dev Guru** (this repo) | The product: CLI and SDK, report view models and renderers, a local web interface |
| [Ananke Plexus](https://github.com/Neo-Pragnya/Ananke-Plexus) | The harness: code graph, analysis, workflows, policy, runs and evidence |
| [Dex Trove](https://github.com/Neo-Pragnya/Dex-Trove) | Optional capability memory: curated skills, agents, instructions and workflows |

Dev Guru never analyses code itself: every domain operation goes through one client port to Ananke, and Dex is never
required. See [Architecture](docs/concepts/architecture.md) and [How Dev Guru talks to Ananke](docs/concepts/ananke-client.md).

## Quality gates

```bash
make verify             # ruff, ruff format, strict mypy, pytest
make acceptance-wheel   # capability scenarios on the built wheel, including real-Chrome journeys
make web-journeys       # just the web interface, in real Chrome, on a temporary workspace
make scan               # gitleaks, pip-audit, GuardDog and Bandit on dist/
```

## Licence

Apache-2.0. See [LICENSE](LICENSE).
