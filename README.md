# Dev Guru

**Understand, improve, verify and learn from your software, locally.** Dev Guru is the developer product in a
three-repository system:

| Repository | Role |
| --- | --- |
| **Dev Guru** (this repo) | The product: SDK and CLI first, then offline HTML reports, then a local web UI |
| [Ananke Plexus](https://github.com/Neo-Pragnya/Ananke-Plexus) | The harness: code graph, analysis, workflows, policy, runs and evidence |
| [Dex Trove](https://github.com/Neo-Pragnya/Dex-Trove) | Optional capability memory: curated skills, agents, instructions and workflows |

Dev Guru never analyses code itself. Every domain operation goes through one client port to Ananke, and Dex is
never required.

> **Status: pre-alpha, not released.** This repository has its scaffold and the Ananke client port. The `explore`
> flow and the offline HTML reports come next (see [the plan](#whats-next)). The package name `dev-guru` and the
> command `devguru` are provisional: they're free on PyPI, and nothing is reserved yet.

## Try it from a checkout

```bash
git clone https://github.com/Neo-Pragnya/Dev-Guru && cd Dev-Guru
make install            # uv sync --all-extras (installs ananke-plexus from PyPI)
uv run devguru doctor   # is a compatible Ananke installed, and can it do what Dev Guru needs?
```

```console
$ uv run devguru doctor
dev-guru 0.1.0.dev0 · Python 3.14.6 · transport in-process
✓ ananke-plexus 0.3.11 (supported >=0.3.11,<0.4)
  ✓ graph.build
  ✓ graph.load
  ✓ graph.impact
  ✓ run.status
  ✓ spec.create
  ✓ registry.open
  dex-trove: 0.1.6
```

From Python:

```python
from pathlib import Path
from dev_guru.client import connect

ananke = connect()                       # one explicit transport: "in-process"
print(ananke.info().compatible)          # version range + required capabilities
summary = ananke.graph_summary(Path(".")) # real Ananke analysis of this workspace
print(summary.nodes_by_kind)             # e.g. {'class': 12, 'file': 40, 'function': 95}
```

Errors carry stable codes (`HARNESS_MISSING`, `HARNESS_INCOMPATIBLE`, `CAPABILITY_MISSING`,
`UNSUPPORTED_TRANSPORT`, `WORKSPACE_INVALID`, `HARNESS_FAILED`), so scripts branch on the code, not on the message.

## How it fits together

- [Architecture](docs/architecture.md): boundaries, transports and what lives where.
- [ADR-0001: the Ananke client port](docs/decisions/0001-ananke-client-port.md).
- [Three-repository audit](https://github.com/Neo-Pragnya/Ananke-Plexus/blob/main/docs/reference/three-repository-audit.md):
  what Ananke and Dex actually expose, and the gaps the plan closes.

## Quality gates

The same framework as Ananke Plexus and Dex Trove:

```bash
make verify             # ruff, ruff format, strict mypy, pytest
make acceptance-wheel   # capability scenarios against the built wheel, with a PROMOTE / CONDITIONAL / BLOCK gate
make scan               # what package firewalls check: gitleaks, pip-audit, GuardDog, Bandit on dist/
```

CI runs all three, plus Trivy, Semgrep and a gitleaks history scan, and lints its own workflows with actionlint
and zizmor.

## What's next

In backlog order (task ids from the three-repository plan):

1. Ananke: `AN-SOURCE-PORT` → `AN-INTERNAL-SKILLS` → `AN-CAPABILITY-LOCKS` → `AN-APP-FACADE`.
2. Dev Guru: `DG-CLIENT` (the typed facade) → `DG-VIEW-MODELS` → `DG-CLI-SDK` (`devguru explore`) →
   `DG-OFFLINE-HTML` (a safe, self-contained explorer report).
3. `AN-DEX-FREE-ACCEPTANCE`: internal skill → lock → graph run → offline report, with Dex disabled.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
