---
title: Report format
description: The explorer view model (dev-guru/explorer@1) and the report manifest (dev-guru/report-manifest@1).
---

# Report format

A report embeds two JSON documents: the **view model** it draws and the **manifest** that says where the view
model came from. The manifest is also written next to the report as `<report>.manifest.json`.

## View model: `dev-guru/explorer@1`

| Key | Contents |
| --- | --- |
| `project` | `name`, and counts of `files`, `packages`, `symbols`, `loc`, `imports`, `calls`, `external` |
| `packages[]` | `id` (folder path) and its `files` |
| `files[]` | `id` (`file:<path>`), `path`, `module`, `loc`, `doc`, `symbols`, `fan_in`, `fan_out`, `external`, `entry`, `parse_error` |
| `symbols[]` | `id`, `kind` (class / function / method), `name`, `file`, `line`, `end_line`, `signature`, `doc`, `source` (≤ 60 lines), `calls_in`, `calls_out` |
| `edges[]` | `s`, `t`, `k` (`imports` between files; `calls`/`inherits` between symbols), `o` (origin), `line` |
| `external[]` | modules outside the workspace and which files import them |
| `insights` | `most_depended`, `largest`, `entry_points`, `cycles` (strongly connected import groups), `isolated` |
| `limitations[]` | what this report doesn't cover, in plain words |
| `omitted` | how much was left out to keep the file bounded |

The view model is sorted and deterministic: the same graph always produces the same view model, and so the same
`input_digest`.

## Manifest: `dev-guru/report-manifest@1`

```json
{
  "schema": "dev-guru/report-manifest@1",
  "renderer": "dev-guru/explorer-html@1",
  "dev_guru": "0.1.0",
  "ananke": "0.3.12",
  "view_model": "dev-guru/explorer@1",
  "snapshot_id": "20261102T042619Z",
  "input_digest": "sha256:…",
  "workspace": {"name": "shop", "vcs": "git", "commit": "…", "dirty": false},
  "publication": "offline-single-file",
  "generated_at": "2026-11-02T04:26:19+00:00",
  "transport": "in-process",
  "limitations": ["…"]
}
```

`input_digest` is the SHA-256 of the canonical view-model JSON. Use it to tell whether two reports show the same
thing, whatever their timestamps.
