# Changelog

All notable changes to Dev Guru are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — [SemVer](https://semver.org/).

---

## [Unreleased]

---

## [0.11.2] — 2026-11-05

### Fixed

- **Metadata a scanner may not read.** Wheels and sdists were built with Metadata-Version 2.5, which older SCA parsers reject, so they can't identify the package. Dev Guru now writes 2.4, with a licence classifier as well as `License-Expression`.
- Needs Ananke 0.3.32, which has the same fix and no longer allows vulnerable Jinja2 releases.

### Added

- **The release gate checks what Black Duck and similar tools check:** metadata, the oldest versions each range allows, every dependency's licence, and licence names in shipped files. It reports dependencies under 14 days old. Firewalls with a maturity rule block those, so installing Dev Guru fails even when it's allowed. The guide gives the command that avoids them.

---

## [0.11.1] — 2026-11-05

### Fixed

- **Package firewalls quarantined Dev Guru through Ananke.** Ananke up to 0.3.28 shipped a vendored, minified Mermaid bundle with undeclared licences and read keychain secrets with the command infostealers use. Dev Guru's own files were clean, but installing it pulled in that Ananke. It now needs Ananke 0.3.30, which ships neither.

### Added

- **The release gate blocks what got us quarantined:** minified or third-party code whose licence isn't declared, malware-shaped code anywhere in the wheel or sdist, and any GuardDog rule nobody has reviewed. Grype and osv-scanner check the dependency tree alongside pip-audit when installed. Reviewed findings, each with a reason, are in `.scan-dist.toml`.

---

## [0.11.0] — 2026-11-05

### Fixed

- **Windows: the constellation had no links and the flow one package.** Ananke wrote graph paths with backslashes on Windows, so imports between a repository's own files weren't matched. Ananke 0.3.28 fixes it, and Dev Guru now needs it. A new CI job runs `dev explore` on Linux, macOS and Windows and checks the report has its links and packages.
- **`dev explore` failed with `HARNESS_FAILED` on a folder copied or moved with its `.ananke` history.** Its run key now names the workspace, as Ananke's request does.

### Added

- **`dev serve` opens on the explorer.** It has every view a report has, Constellation, Flow, Impact, Calls, Hotspots and Tour among them, with the other pages live in its tabs. The pages alone are at `/app`. With no code graph yet, it offers to build one, because reading a page never starts anything.
- **`dev explore` says what it's doing,** each step with a running clock and how long it took. `-v`/`--verbose` adds what each step found, and `-q`/`--quiet` says nothing until it's done.
- **`--logs FILE` on `dev explore` and `dev serve`:** a record for finding faults, with versions, the operating system, each step's time and findings, warnings and any error in full. It holds no environment variables, tokens or file contents.
- **A warning when a graph looks wrong,** whatever the options: paths written with backslashes, many Python files with no imports between them, or hundreds of files in one package.

### Changed

- **`dev explore` is about three times faster** on a large repository: 40 seconds to 13 on 700 files, with the same report. Source is read in one call with Ananke's `read_sources`, and the repository map reuses the analysis instead of running another.
- Needs Ananke 0.3.28 or later.

---

## [0.10.0] — 2026-11-05

### Changed

- **Every page now looks and works like the explorer's first six views,** in reports and in `dev serve`: the same palette and type, a rail, a live stage, an inspector, and a walk-through. Hovering lights up what connects, with light travelling along the lines.
- **New drawings for pages that were only tables:** an overview of every view, callers to routes to handlers, files sized and coloured for quality and coverage, vulnerable packages, findings, how far each view can be trusted, which tool answers which question, runs, capabilities, documents and learning candidates.
- **CVEs group by package in the drawing,** with each advisory in the rail.
- **The Workflows canvas is shown first,** starting from a two-step draft, with the form a click away.

### Added

- **`#play=1` for a framed report:** it shows each view in turn until someone reaches for it.
- **A check on every page:** browser journeys now fail if a page loses its rail, stage or inspector, or stops moving, if the inspector covers the page at a tablet's width, or if a framed report's tabs squeeze its stage.

### Fixed

- A framed report's tabs took most of the frame and left almost no stage.
- The website showed empty black panels for 13 of its view cards, and left out six views. All 25 now have an animated preview.
- The example on the website now has real capabilities, Markdown files and a learning candidate to show.

---

## [0.9.0] — 2026-11-05

### Added

- **Findings.** What scanners and test runs already reported, from SARIF and JUnit reports in the repository, worst first, with a short list of what to fix first, including packages with a known fix. With no report, it says that's unknown.
- **What's certain.** How far to trust each view: what was found, what's unknown or failed, what's always inferred, and every limit the analysis noted, in one place.

### Changed

- Needs Ananke 0.3.27 or later.

---

## [0.8.0] — 2026-11-05

### Added

- **A workflow canvas.** Drag steps, or use the keyboard: Tab to a step or port, arrow keys to move, Enter to link, Delete to remove. Links only join ports of the same type. It edits the same draft as the form, and where steps sit isn't part of it, so moving one doesn't change the plan.
- **`dev bpmn`, and Make a process on the Documentation page.** From a reviewed process, read by Ananke: swimlanes, an offline viewer where each step cites its source, and BPMN 2.0 for tools like Camunda Modeler. A file edited elsewhere reads back. Nothing runs. Guide: [Business processes](docs/guides/business-processes.md).

### Changed

- Needs Ananke 0.3.26 or later.

---

## [0.7.0] — 2026-11-05

### Added

- **Workflows.** Put capabilities in order with a form, from a blank draft or a starting shape. Steps are linked by the type of what they take and give, and Ananke checks the draft and shows what would run, its order, permissions and approvals, or its own typed problems. Previewing runs nothing. A draft can be exported and imported.
- **Documentation.** Turn any Markdown file in the workspace into an offline deck, or a diagram of what it states. Each comes back as a download, and nothing in the workspace changes.
- **Learning review.** See what Ananke learned, its evidence, and how it would change each destination, before it becomes reusable. It's read-only, so rejecting can't publish anything.

Nothing in the navigation is marked as missing any more. All three are in the offline file too, where building and previewing say to use `dev serve`.

---

## [0.6.0] — 2026-11-05

### Added

- **Every page of `dev serve`, in the one offline `dev explore` file.** Overview, Code map, End-to-end flows, Data, API pathways, Architecture, Quality, Coverage, CVEs, Saving tokens, Code, Runs and Capabilities sit beside the explorer's tabs. They're the same pages, with a recording behind them, and the file still fetches nothing. The public profile leaves them out, and keeps counts in a Repository tab.
- **Folders of notebooks.** Code in `%%writefile` cells counts on every page, even if nobody has run the notebook. A new **Notebooks** page explains each one from its own headings and code: what it's for, what it covers, what it writes, what it builds on, and how they feed each other. Guide: [Folders of notebooks](docs/guides/notebooks.md).
- `dev explore --check-vulnerabilities`, for a file that shows real CVEs and fixes. It uses the network only when you ask.
- **Impact and paths on the Code map.** Select anything to see how many items in the view depend on it, directly or through others, and find how it connects to something else.
- **The `dev serve` Overview summarises each repository view,** and says what's unknown or not analysed yet.

### Changed

- The website's example now shows all of this, on a small shop with its notebooks. A second example shows Dev Guru itself.
- The roadmap moved into the documentation, and the website's home page shows the version on PyPI.
- Needs Ananke 0.3.25 or later.

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
