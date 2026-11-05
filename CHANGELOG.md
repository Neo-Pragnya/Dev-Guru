# Changelog

All notable changes to Dev Guru are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — [SemVer](https://semver.org/).

---

## [Unreleased]

---

## [0.5.1] — 2026-11-05

### Added

- The Architecture page lists what differs from a declared model as a table, rather than raw JSON.
- A guide to [mapping a new repository](docs/guides/repository-views.md#mapping-a-new-repository).

### Changed

- The Saving tokens page shows `ananke context enable --local`, which keeps it out of commits.
- Updated GitHub Actions for checkout, artifacts, Pages and build attestations.

### Security

- The test fixture no longer keeps its deliberately old package pins as real manifest files. They're restored only while a journey runs.

---

## [0.5.0] — 2026-11-04

### Added

- **See how a repository works, in `dev serve`.** Ananke does the analysis, and these pages show it. Guide: [Repository views](docs/guides/repository-views.md).
  - **Code map:** folders, files and functions, connected across folders by imports, calls, HTTP calls and table use. Open a folder to go deeper, and select something to see what uses it, with its source.
  - **End-to-end flows:** from a frontend call, through a route and its handler, to the tables, one step at a time.
  - **Data:** an ERD of tables, fields and keys, which code reads and writes each table, and a Mermaid copy.
  - **API pathways:** every route and what calls it, and calls to routes that don't exist.
  - **Architecture:** a CALM model inferred from the repository, marked as inferred, that you can download.
  - **Quality, Coverage and CVEs:** measured values. Without a coverage report or a CVE check, they say so rather than show 0 or clean. Checking for CVEs uses the network only when you ask.
  - **Saving tokens:** a small map of the repository for an AI assistant, and which tool answers which question.
- **`dev context`:** the same map from the command line, usually under 2,000 tokens, current with every edit.

### Changed

- Needs Ananke 0.3.22 or later.

---

## [0.4.0] — 2026-11-03

### Added

- **A web interface in `dev serve`.** Overview, runs, a code view and capabilities from your sources, as plain files in
  the package: no Node and no build step. Runs are shown live, survive a tab reload and a lost connection, name any
  events no longer kept, and stop only when you press Cancel. It works from the keyboard and on a phone. Pages that
  don't exist yet say so and name the commands that work today. Guide: [The local gateway](docs/guides/gateway.md).
- `GET /api/v1/runs`, the runs in a workspace.
- Real-Chrome journeys for the interface, on a temporary workspace they build themselves (`make web-journeys`, and part
  of the acceptance suite).
- [ROADMAP.md](ROADMAP.md): what's released and what's planned.
- Dependabot for `uv` and GitHub Actions, with a seven-day cooldown.

### Changed

- Needs Ananke 0.3.19 or newer, for its fixes to path traversal and vulnerable dependencies.
- CI grants `security-events: write` only to the jobs that upload findings.
- Releases are created with `gh release` rather than a third-party action.
- CI installs Trivy with retries and a pinned SHA-256 rather than through a third-party action, so one failed DNS lookup can't block a release.

### Fixed

- The run console could stop without showing a run's final event, if it read between the run's final state and that event.

- The gateway answered a login token or CSRF token that wasn't ASCII with a `500`. It's now the usual refusal. No request
  got through either way.

### Security

- Reviewed two Semgrep findings as false positives and marked each in the code with its reason. Reviewed findings no
  longer reappear as new alerts when a line moves.

---

## [0.3.0] — 2026-11-03

### Added

- **`dev serve`, a local gateway to Ananke.** It listens on loopback only. A single-use link signs in one browser, and
  changes also need a same-origin `Origin`, a CSRF token and a JSON body. Workspaces are named by opaque id, and no route
  takes a command or path to run. It starts and cancels runs, reads events and artifacts, previews workflows and serves
  the code graph. There's no web interface yet. Guide: [The local gateway](docs/guides/gateway.md).
- The client port gains run, event, artifact, plan and code graph operations, so the gateway reaches Ananke only through it.

### Changed

- Needs Ananke 0.3.17 or newer, for its facade that's safe across threads.

---

## [0.2.0] — 2026-11-03

### Added

- **Runs through the Ananke app facade** (`ananke-app/1`, needs Ananke 0.3.13):
  - `dev explore` builds the graph in an idempotent Ananke run, records the run in the report manifest
    (`ananke_run`), and registers the HTML back into that run as an artifact with its inputs;
  - a failed build is a failed run, with its id kept as evidence.
- **`dev sources`**: source-neutral capability discovery (internal folders, private Git, troves) with an offline
  picker page. Works with Dex switched off.
- **`dev learning review`**: an offline review page for an Ananke learning candidate, showing the gate status,
  evaluation, review, provenance and a diff per destination.

- **`dev diagram`**: an animated SVG of the relationships a document states (arrow lines, Mermaid flowcharts, From/To
  tables). Every edge cites its file and line, and an edited edge that fails its citation is drawn as a hypothesis.
  Guide: [Diagrams from documents](docs/guides/diagrams.md).
- **`dev present`**: Markdown slides become one offline, accessible HTML deck:
  - `lantern` and `paper` themes, responsive columns, step-by-step lists, speaker notes, keyboard navigation;
  - bar charts as accessible SVG;
  - embedded local images that require alt text; raw HTML is shown as text;
  - `--check` verifies a deck. Guide: [Presentations](docs/guides/presentations.md).
- **Publication profiles** for `dev explore` (`--profile public`): removes source, docstrings, string defaults in
  signatures and the Git revision, so a report is safe to publish. The manifest records the profile.

---

## [0.1.1] — 2026-11-02

### Changed

- **The constellation is a 3D force-directed graph.** Imports are springs, files repel each other and packages pull
  their files together. Drag to orbit, scroll to zoom, drag a file to pull the graph, double-click to fly to a file;
  it turns slowly when idle. Shaded bodies, depth fog, a star field and pulses along lit imports, with labels that
  never overlap. Drawn on a plain canvas inside the report: no WebGL, no library, no network. With reduced motion it
  settles before the first frame and stays still.
- Docs: the client-port design is now a plain concept page, [How Dev Guru talks to Ananke](docs/concepts/ananke-client.md).
  PyPI links on the README, the docs home and the site.

### Fixed

- `.trivyignore` added, so the release workflow's Trivy gate can run.

---

## [0.1.0] — 2026-11-02

The first release.

### Added

- **`dev explore`**: Ananke builds the code graph, and Dev Guru writes one interactive, offline HTML explorer plus a
  manifest.
  - Six views: constellation, flow (package or file level), impact rings, calls, hotspots and a narrated tour.
  - Around them: search, a command palette, a source inspector, a light and dark theme, and URL-shareable state.
  - Explicit downloads of the view state and of analysis requests.
- **Report safety.**
  - Everything is inlined, and the page sets a CSP with `connect-src 'none'`.
  - JSON is embedded with `<`, `>`, `&` and U+2028/U+2029 escaped; untrusted text is set only with
    `textContent`.
  - Templates are filled in a single pass, so source code containing the template's placeholders stays data.
  - A manifest records the renderer, the Dev Guru and Ananke versions, the input digest and the git revision.
- **View model `dev-guru/explorer@1`**: packages, files, symbols with source snippets, resolved import, call and
  inheritance edges, insights (most depended-on, largest, entry points, import cycles) and stated limitations.
  Deterministic.
- **SDK** `GuruClient(workspace).explore()` / `.export()`, sharing one service layer with the CLI.
- **`dev doctor`**: version and capability negotiation with Ananke (`ananke-plexus>=0.3.12,<0.4`) over one explicit
  transport, with stable error codes.
- **Docs site** with a live demo (Dev Guru exploring its own source) and the "Lantern" theme.
- **Release gates:**
  - acceptance on the built wheel, including real-Chrome report journeys and a dogfood run on Dev Guru's own source;
  - a distribution scan (gitleaks, pip-audit, GuardDog, Bandit);
  - Trivy and build provenance.

### Changed

- The command is **`dev`** (it was `devguru` in the unreleased scaffold).

### Fixed

- Import cycles in Dev Guru itself, found by exploring it: `dev_guru` now exposes `GuruClient` lazily, and
  `client.inprocess` imports `negotiation` directly.
