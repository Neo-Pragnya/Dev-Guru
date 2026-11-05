---
title: Repository views
description: See how a repository works in dev serve. A code map across folders, end-to-end flows, an ERD, API pathways, an inferred CALM architecture, quality, coverage, CVEs and a small map for AI assistants.
---

# Repository views

Point `dev serve` at a repository and these pages show how it works, in any folder layout. Ananke analyses the code and Dev Guru shows the result.

```bash
dev serve ../shop
```

Open any of these pages and choose **Analyse this repository**. Analysis reads your files and runs nothing from them. Pages show nothing until an analysis exists, rather than showing invented data.

## The pages

| Page | What it answers |
| --- | --- |
| **Code map** | How do the folders, files and functions connect? |
| **End-to-end flows** | What happens from a request to the database? |
| **Data** | What tables and fields exist, how do they relate, and which code uses them? |
| **API pathways** | What's every route, and who calls it? |
| **Architecture** | What are the components and how do they connect? |
| **Quality** | Where are the complexity, the large files and the tests? |
| **Coverage** | What do the tests cover, per file? |
| **CVEs** | Which dependencies are vulnerable? |
| **Saving tokens** | What's the smallest useful picture of this repository for an AI assistant? |

### Code map

The map starts with folders and draws what links them: imports, calls, HTTP calls from a frontend to a backend route, and reads and writes to tables. Open a folder to see its files, and a file to see its functions. Select anything to see what uses it, with its source, how many items in the view could be affected by changing it, and a path to anything else.

It tells you what it left out: third-party imports aren't drawn, but are counted. Folders nothing links to are listed under **Not connected**, because they may be standalone scripts, or linked in a way the analysis can't read.

### End-to-end flows

Choose a route and step through it, from the frontend call through the route and its handler to the tables it writes. Each step shows its file, line and source. Calls to routes that don't exist in this repository are listed at the top, because they may be bugs.

A flow only follows links found in the code, so background jobs, schedules and message consumers aren't traced as starting points. The page says so.

### Data

An ERD of the tables, fields and keys, drawn from models and SQL files. Select a table to see its fields and the code that uses it. **Data lineage** shows what writes each table and what reads it, and you can copy or download the ERD as Mermaid.

A table only known because code uses it is counted separately as **Known only from use**.

### Architecture

The components, drawn so what depends on what reads left to right, with the evidence for each link. This is inferred from files such as `docker-compose.yml`, and the page says so, so check it against what you know. If you've declared a model at `.ananke/architecture/system.calm.json`, the page lists what differs. **Download CALM model** saves it in the [CALM](https://calm.finos.org/) format.

The diagram shows components that take part in links. The table lists all of them, including notebooks and tests.

### Quality, coverage and CVEs

These pages keep "unknown" apart from "zero":

- **Coverage** reads a report your tests already produced. Without one, it says so rather than show 0%.
- **CVEs** say they haven't been checked, not that you're clean. Checking uses the network, so it happens only when you ask.

### Saving tokens

A small map of the repository to paste into an AI assistant, the tool to use for each question, and which tools are installed. The same map is available from the command line:

```bash
dev context ../shop
```

To have an assistant use these by default, see [Saving tokens](https://github.com/Neo-Pragnya/Ananke-Plexus/blob/main/docs/guides/saving-tokens.md) in Ananke's guide.

## Mapping a new repository

1. **Start with the Overview and Code map.** Check the components and folders look right. A folder under **Not connected** that should be connected is the first thing to look into.
2. **Check one flow you know.** Choose a route whose path through the code you can check by hand. If it's right, trust the others more. If a step's missing, the page's limits usually say why.
3. **Check the broken calls.** Calls to routes that don't exist here are either bugs, or a service in another repository.
4. **Compare the Data page with your schema.** Tables **Known only from use** have no model or SQL file here.
5. **Save what you confirm as a declared architecture.** Put your model at `.ananke/architecture/system.calm.json`, and the Architecture page shows how the code differs from it each time you analyse.
6. **Produce a coverage report and ask for a CVE check.** Both stay marked as unknown until you do.

## Limits

- A link is inferred from names and imports, not from running the code, so a call made through a variable or a framework's magic can be missing.
- Analysis describes one repository at a time. Calls to another service appear as calls with no route here.
- Very large repositories show the most connected items first, and say that they did.
