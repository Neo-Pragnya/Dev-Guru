---
title: Python SDK
description: Use Dev Guru from Python scripts and notebooks. The SDK and the CLI share one service layer.
---

# Python SDK

```python
from dev_guru import GuruClient

with GuruClient(workspace="path/to/project") as guru:
    print(guru.doctor().compatible)              # True when Ananke is in range
    result = guru.explore(name="My project")     # Ananke builds the graph; Dev Guru projects it
    page = guru.export(result, output="reports/explorer.html")

print(result.model["project"])     # {'files': 25, 'symbols': 146, 'imports': 26, 'calls': 88, ...}
print(result.manifest["input_digest"])
```

| Call | Returns |
| --- | --- |
| `GuruClient(workspace=".", transport="in-process")` | a client bound to one explicit transport |
| `.doctor()` | `HarnessInfo`: Ananke version, supported range, capabilities, reasons if incompatible |
| `.explore(name=None)` | `ExploreResult`: the view model (`dev-guru/explorer@1`), its manifest and the transport |
| `.export(result, output=..., format="html")` | the path of the written report (a manifest goes next to it) |
| `.export(result, output=..., format="mermaid", focus=..., depth=..., budget=..., level=...)` | the path of a code-graph drawing: `mermaid`, `svg` or `json` (see `dev graph`) |

## Errors

Failures raise `dev_guru.errors.GuruError` with a stable `code`, so branch on the code rather than on the message:

| Code | When |
| --- | --- |
| `HARNESS_MISSING` | Ananke Plexus isn't installed |
| `HARNESS_INCOMPATIBLE` | its version is outside the supported range |
| `CAPABILITY_MISSING` | it lacks a capability Dev Guru needs |
| `UNSUPPORTED_TRANSPORT` | you asked for a transport that doesn't exist (no silent fallback) |
| `WORKSPACE_INVALID` | the folder doesn't exist, or holds no Python files |
| `HARNESS_FAILED` | Ananke reported success but stored nothing |

## The lower-level port

`dev_guru.client.connect()` returns the `AnankeClient` port directly: `info()`, `graph_data(workspace)` (the graph
as plain data) and `graph_summary(workspace)`. Everything Dev Guru knows about your code comes through this one port.
