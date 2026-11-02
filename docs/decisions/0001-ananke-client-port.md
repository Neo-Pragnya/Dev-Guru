# ADR-0001: one Ananke client port, in-process first

**Status:** accepted · **Date:** 2026-11-01 · **Backlog:** `DG-PACKAGE` (prerequisite for `DG-CLIENT`)

## Context

Dev Guru needs Ananke's analysis, workflows and evidence from day one. Ananke already has a Python facade
(`ananke.plexus.api.Ananke`, whose methods return `CommandResult`) and typed services, such as
`graph.service.load_graph` returning `GraphSnapshot`. A typed, versioned app facade (`AN-APP-FACADE`) and an isolated
transport don't exist yet. The audit is in Ananke Plexus: `docs/reference/three-repository-audit.md`.

## Decision

- All harness access goes through `dev_guru.client.AnankeClient`. Nothing else in Dev Guru imports `ananke`.
- The first transport is **in-process**, over the existing public facade and services.
- **Negotiation is explicit.** `SUPPORTED_ANANKE = ">=0.3.12,<0.4"` (it was `>=0.3.11` before Dev Guru 0.1.0 needed the call graph) matches the declared dependency (tested).
  Capabilities are probed by import (nothing runs). `graph.build` and `graph.load` are required.
- **No silent fallback.** An unknown or failing transport is a `GuruError`. The caller chooses the transport, and
  each run records it.
- **Failures are not empty successes.** A graph build that stores no snapshot raises `HARNESS_FAILED`; it doesn't
  return an empty graph.

## Consequences

- Dev Guru depends on `ananke-plexus` in its base install. When `AN-APP-FACADE` lands, the in-process adapter moves to
  the typed facade without changing the port, and the supported range moves with it.
- Untyped `CommandResult.details` aren't relied on for domain data. Typed models are read from the owning Ananke
  service.
- `ananke-plexus` has no `py.typed` marker yet, so mypy follows its untyped imports.
