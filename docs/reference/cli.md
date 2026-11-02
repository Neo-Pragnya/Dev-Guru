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
dev explore [WORKSPACE] [-o, --output FILE] [--name NAME] [--open] [--transport in-process] [--json]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `WORKSPACE` | `.` | project to explore |
| `-o, --output` | `dev-guru-explorer.html` | the report; `<output>.manifest.json` is written next to it |
| `--name` | the folder name | project name shown in the report |
| `--open` | off | open the report in your browser once it's written |
| `--json` | off | print `report`, `manifest`, `input_digest`, `project` counts and insight counts |

Exit `0` on success. Exit `1` with a stable error code (`WORKSPACE_INVALID`, `HARNESS_MISSING`, …) when nothing can
be explored. An empty folder is an error, never an empty report. Set `SOURCE_DATE_EPOCH` for a reproducible
`generated_at`.
