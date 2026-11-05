---
title: Roadmap
description: What's released in Dev Guru, and what's planned.
---

# Roadmap

What's released in [Dev Guru](https://pypi.org/project/dev-guru/), and what's planned. Details of each version are in
[the changelog](https://github.com/Neo-Pragnya/Dev-Guru/blob/main/CHANGELOG.md). Plans change: this says what's intended, and nothing below "Planned" exists until it's
released.

## Released

| Version | Highlights |
| --- | --- |
| **0.9.0** | Findings, from reports in the repository, with what to fix first. What's certain: how far to trust each view |
| **0.8.0** | A workflow canvas that works from the keyboard. Swimlanes and BPMN 2.0 from a reviewed process |
| **0.7.0** | Workflows, Documentation and Learning review in the web interface, so nothing is marked as missing |
| **0.6.0** | One offline file with every page of `dev serve`, and an example that shows them all. Folders of notebooks: code in `%%writefile` cells counts, and a Notebooks page explains each one. Impact and paths on the Code map |
| **0.5.1** | The Architecture page lists differences from a declared model. A guide to mapping a new repository |
| **0.5.0** | How a repository works, in `dev serve`: a code map across folders, end-to-end flows, an ERD, API pathways, a CALM architecture, quality, coverage, CVEs and saving tokens. `dev context` for AI assistants |
| **0.4.0** | A web interface in `dev serve`: overview, live runs with cancel, a code view, and capabilities from your sources. No Node needed |
| **0.3.0** | `dev serve`, a local gateway to Ananke that only your browser session can reach |
| **0.2.0** | `dev present` (offline decks), `dev diagram` (a cited, animated SVG of what a document states), `dev sources`, `dev learning review`, and reports safe to publish (`--profile public`). Reports now run through Ananke's app facade |
| **0.1.x** | `dev explore`: one offline HTML explorer of a Python project, with a 3D constellation, flow, impact, calls, hotspots and a tour. `dev doctor` and a Python SDK |

## Next: repository intelligence

These views are in 0.5.0, and offline since 0.6.0. What we'd do next:

- Check them against more real repositories, and fix what they get wrong.
- Connect several repositories in one map.
- Look up symbols from the web interface, using `ananke context symbol` and `callers`.

The rules they follow:

- **Everything cites evidence.** Tables, routes and steps name the file and line they came from.
- **Unknown isn't zero.** With no coverage report, the view says so rather than show 0%. A skipped CVE scan doesn't read as clean.
- **Nothing happens behind your back.** Analysis reads files and runs nothing. Checking for CVEs uses the network only when you ask.

## Planned: going further in the web interface

- **Running a workflow from the browser**, once a real agent backend has been tested end to end.
- **Editing a process in the browser.** Today, you edit the text or use a BPMN tool, and read it back.
- **Richer documents:** outlines by audience, and previewing in the page.

