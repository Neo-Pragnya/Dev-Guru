---
title: CLI reference
description: The dev command, its subcommands, options and exit codes.
---

# CLI reference

```text
dev [--version] COMMAND [ARGS]...
```

## `dev doctor`

```text
dev doctor [--transport in-process] [--json]
```

Checks the Ananke harness: the installed version, the supported range, and the capabilities Dev Guru calls. Exit `0`
when compatible, `1` when Ananke is missing or incompatible, and `2` for an unknown transport. `--json` prints `ok`,
`dev_guru`, `python`, `harness` (version, range, capabilities, `missing_required`, reasons) and `optional`
(`dex-trove`).

## `dev explore`

```text
dev explore [WORKSPACE] [-o, --output FILE] [--name NAME] [--open] [--transport in-process] [--profile private|public] [--json]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `WORKSPACE` | `.` | project to explore |
| `-o, --output` | `dev-guru-explorer.html` | the report; `<output>.manifest.json` is written next to it |
| `--name` | the folder name | project name shown in the report |
| `--open` | off | open the report in your browser once it's written |
| `--profile` | `private` | `public` removes source code, docstrings, string defaults in signatures and the Git revision, so the report is safe to publish; see [report safety](../concepts/report-safety.md#publication-profiles) |
| `--json` | off | print `report`, `manifest`, `input_digest`, `project` counts and insight counts |

Exit `0` on success. Exit `1` with a stable error code (`WORKSPACE_INVALID`, `HARNESS_MISSING`, …) when nothing can
be explored. An empty folder is an error, never an empty report. Set `SOURCE_DATE_EPOCH` for a reproducible
`generated_at`.

## `dev sources`

```text
dev sources [QUERY] [-w, --workspace DIR] [--html PICKER.html] [--json]
```

Lists the capabilities every source the project configures offers: approved folders and private Git repos
(`[capability_sources]`) and enabled troves, through Ananke's provider port. Identities are
`source:namespace/name`, with exact versions and digests. `--html` writes an offline picker with search and source
filters.

## `dev learning review`

```text
dev learning review NAME [-w DIR] [-o PAGE.html] [--open] [--json]
```

Writes a review page for a learning candidate: what still blocks promotion, the evaluation cases and results, the
review decision, provenance, and a diff against each destination. Reviewing changes nothing. Approve with
`ananke learning review --approve`, then promote with `ananke learning promote`.

## `dev serve`

```bash
dev serve [WORKSPACE]... [--port N] [--open/--no-open] [--transport NAME]
```

Starts [the local gateway and its web interface](../guides/gateway.md) for the listed folders, or the current one. It
listens on this computer only and prints a link that works once. Stop it with Ctrl-C. Exits `2` if a folder doesn't exist or the port is taken.

## `dev diagram`

```text
dev diagram DOCUMENT.md [-o, --output FILE] [--model FILE] [--from-model FILE] [--static] [--json]
```

An animated SVG of the relationships a document states, each cited by file and line. See
[Diagrams from documents](../guides/diagrams.md). Exit `2` when the document has no explicit relationships or a file is
missing or malformed.

## `dev present`

```text
dev present SLIDES.md [-o, --output FILE] [--theme lantern|paper] [--open]
dev present DECK.html --check
```

Turns Markdown slides into one offline, accessible HTML deck. See [Presentations](../guides/presentations.md).
Exit `2` on an authoring error (it names the slide content to fix), `1` if a deck fails `--check`.
