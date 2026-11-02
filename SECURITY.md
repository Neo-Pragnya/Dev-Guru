# Security policy

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/Neo-Pragnya/Dev-Guru/security/advisories/new). Please don't open a
public issue. We aim to acknowledge reports within five working days.

## What Dev Guru promises

- Exports are view-only. Opening a report never runs commands, contacts a network, or starts a listener.
- Untrusted text (source code, scanner output, upstream skill content) is shown as text, never as HTML.
- Dev Guru stores only product state (preferences, saved views, report assets). Runs and evidence stay in Ananke.
- Credentials are referenced from the host's credential store and never written into exported manifests.

Each release is checked by `make scan` (secrets, vulnerable dependencies, malicious-code heuristics) and by the
acceptance gate against the built wheel.
