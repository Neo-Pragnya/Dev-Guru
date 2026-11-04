# Roadmap

What's released in [Dev Guru](https://pypi.org/project/dev-guru/), and what's planned. Details of each version are in
[CHANGELOG.md](CHANGELOG.md). Plans change: this says what's intended, and nothing below "Planned" exists until it's
released.

## Released

| Version | Highlights |
| --- | --- |
| **0.4.0** | A web interface in `dev serve`: overview, live runs with cancel, a code view, and capabilities from your sources. No Node needed |
| **0.3.0** | `dev serve`, a local gateway to Ananke that only your browser session can reach |
| **0.2.0** | `dev present` (offline decks), `dev diagram` (a cited, animated SVG of what a document states), `dev sources`, `dev learning review`, and reports safe to publish (`--profile public`). Reports now run through Ananke's app facade |
| **0.1.x** | `dev explore`: one offline HTML explorer of a Python project, with a 3D constellation, flow, impact, calls, hotspots and a tour. `dev doctor` and a Python SDK |

## Planned: repository intelligence

Give Dev Guru a code repository, in any folder layout, and it shows how the whole thing works. Ananke will do the
analysis and Dev Guru will show the result, in the web interface and in reports.

| View | What it will answer | Status |
| --- | --- | --- |
| **Code map** | How do the files and functions connect, across folders? | Planned |
| **End-to-end flow** | What happens from a request to the database and back? | Planned |
| **Data (ERD)** | Which tables and fields exist, how do they relate, and which code uses them? | Planned |
| **API pathways** | What's every route, who calls it, and what does it do? | Planned |
| **Architecture** | What does a full CALM model of the system look like? | Planned |
| **Quality** | Where are the complexity, size, hotspots and tests? | Planned |
| **Coverage** | What do the tests cover, per file? | Planned |
| **CVEs** | Which dependencies are vulnerable, and what's the fix? | Planned |

The rules these views will follow:

- **Everything cites evidence.** Every table, route and step will link to the file and line it came from.
- **Unknown isn't zero.** With no coverage report, the view will say so rather than show 0%. A skipped CVE scan won't
  read as clean.
- **Nothing happens behind your back.** Analysis will read files and run nothing. Checking for CVEs will use the network
  only when you ask, and tests will run only when you ask.

## Planned: the rest of the web interface

These pages are in the navigation today, marked "Not in this version", and each names the commands that work meanwhile.

| Page | What it will do | Status |
| --- | --- | --- |
| **Workflows** | Assemble and preview a workflow in the browser, then run it | Planned |
| **Quality** | Show the quality, coverage and CVE views above | Planned |
| **Documentation** | Make decks and diagrams from your documents in the browser | Planned |
| **Learning review** | Review what Ananke learned before it becomes reusable | Planned |
