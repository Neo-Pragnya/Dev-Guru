---
title: How Dev Guru talks to Ananke
description: One client port, an in-process transport, an explicit supported version range, and failures that are reported instead of hidden.
---

# How Dev Guru talks to Ananke

Dev Guru never analyses code itself. Every graph, workflow and piece of evidence comes from
[Ananke Plexus](https://neo-pragnya.github.io/Ananke-Plexus/), and every call to Ananke goes through one place:
`dev_guru.client`.

## One client port

- All harness access goes through `dev_guru.client.AnankeClient`. Nothing else in Dev Guru imports `ananke`.
- The port has three calls today: `info()` (version and capabilities), `graph_summary()` and `graph_data()`.
- The transport behind it is **in-process**: Dev Guru calls the installed Ananke in the same Python environment,
  through Ananke's public facade (`ananke.plexus.api.Ananke`) and its typed graph service.

## Version negotiation

- Dev Guru declares the Ananke versions it supports: `SUPPORTED_ANANKE = ">=0.3.12,<0.4"`. A test keeps this equal
  to the `ananke-plexus` dependency in `pyproject.toml`.
- Ananke's capabilities are checked by import, so nothing runs during the check. `graph.build` and `graph.load` are
  required.
- `dev doctor` shows the result: the Ananke version found, whether it is in range, and which capabilities are there.

## No silent fallback

- An unknown or failing transport is a `GuruError` with a stable code. Dev Guru never quietly switches to another
  transport.
- The caller chooses the transport, and every run records the one it used.
- A failure is never an empty success. A graph build that stores no snapshot raises `HARNESS_FAILED`; it doesn't
  return an empty graph.

## What this means in practice

- `ananke-plexus` is part of Dev Guru's base install.
- Dev Guru reads domain data from Ananke's typed models, not from untyped command output.
- `ananke-plexus` doesn't ship a `py.typed` marker yet, so Dev Guru's type checking follows its untyped imports.
- More transports come later, behind the same port: an isolated Ananke process speaking structured JSON (when
  dependencies must stay apart), and a local web app with a loopback API. Adding one doesn't change the port, and
  the supported version range moves with Ananke's own typed facade.

See also [Architecture](architecture.md) and the [CLI reference](../reference/cli.md).

## Which versions are tested together

Every pull request runs the full acceptance suite on the built wheel four times:

| Ananke | Dex Trove | Route |
| --- | --- | --- |
| the oldest version Dev Guru accepts (read from `pyproject.toml`) | not installed | internal only |
| the oldest version Dev Guru accepts | installed | Dex |
| the newest on PyPI | not installed | internal only |
| the newest on PyPI | installed | Dex |

So the declared range is the tested range, and Dev Guru works the same with or without Dex. Locally:
`make acceptance-wheel ACCEPTANCE_PINS="ananke-plexus==0.3.36 dex-trove"`.

