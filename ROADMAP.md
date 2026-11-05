# Roadmap

What's released in [Dev Guru](https://pypi.org/project/dev-guru/), and what's planned. Details of each version are in
[CHANGELOG.md](CHANGELOG.md). Plans change: this says what's intended, and nothing below "Planned" exists until it's
released.

## Released

| Version | Highlights |
| --- | --- |
| **0.5.0** | How a repository works, in `dev serve`: a code map across folders, end-to-end flows, an ERD, API pathways, a CALM architecture, quality, coverage, CVEs and saving tokens. `dev context` for AI assistants |
| **0.4.0** | A web interface in `dev serve`: overview, live runs with cancel, a code view, and capabilities from your sources. No Node needed |
| **0.3.0** | `dev serve`, a local gateway to Ananke that only your browser session can reach |
| **0.2.0** | `dev present` (offline decks), `dev diagram` (a cited, animated SVG of what a document states), `dev sources`, `dev learning review`, and reports safe to publish (`--profile public`). Reports now run through Ananke's app facade |
| **0.1.x** | `dev explore`: one offline HTML explorer of a Python project, with a 3D constellation, flow, impact, calls, hotspots and a tour. `dev doctor` and a Python SDK |

## Next: repository intelligence

These views are in 0.5.0. What we'd do next:

- Check them against more real repositories, and fix what they get wrong.
- Show them offline in `dev explore`, as well as in `dev serve`.
- Connect several repositories in one map.
- Look up symbols from the web interface, using `ananke context symbol` and `callers`.

The rules they follow:

- **Everything cites evidence.** Tables, routes and steps name the file and line they came from.
- **Unknown isn't zero.** With no coverage report, the view says so rather than show 0%. A skipped CVE scan doesn't read as clean.
- **Nothing happens behind your back.** Analysis reads files and runs nothing. Checking for CVEs uses the network only when you ask.

## Planned: the rest of the web interface

These pages are in the navigation today, marked "Not in this version", and each names the commands that work meanwhile.

| Page | What it will do | Status |
| --- | --- | --- |
| **Workflows** | Assemble and preview a workflow in the browser, then run it | Planned |
| **Documentation** | Make decks and diagrams from your documents in the browser | Planned |
| **Learning review** | Review what Ananke learned before it becomes reusable | Planned |
