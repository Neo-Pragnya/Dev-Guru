# Changelog

All notable changes to Dev Guru are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — [SemVer](https://semver.org/).

---

## [Unreleased]

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
