# Changelog

All notable changes to Dev Guru are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — [SemVer](https://semver.org/).

---

## [Unreleased]

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
