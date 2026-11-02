# Changelog

All notable changes to Dev Guru are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — [SemVer](https://semver.org/).

---

## [Unreleased]

### Added

- **Scaffold** (`DG-PACKAGE`). A Python package (`dev-guru`, module `dev_guru` and command `devguru`, all
  provisional) with the same tooling as Ananke Plexus and Dex Trove:
  - uv + hatchling, ruff, strict mypy and pytest;
  - a capability acceptance suite with release gate (byte-identical harness);
  - a distribution scan (gitleaks, pip-audit, GuardDog, Bandit);
  - CI, security and workflow-lint pipelines with pinned actions.
- **Ananke client port** (`dev_guru.client`).
  - `connect(transport)` returns one explicit transport (`in-process`, over the installed `ananke-plexus`).
  - Negotiation checks the supported range (`>=0.3.11,<0.4`) and probes the capabilities Dev Guru calls.
  - `graph_summary(workspace)` summarises the graph Ananke builds.
  - Errors carry stable codes.
- **`devguru doctor [--json]`**: the harness version, the support verdict, capabilities, and whether Dex is present
  (optional).

Not released: no package has been published.
