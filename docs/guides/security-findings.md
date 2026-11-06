---
title: Security findings
description: How a scanner finding is recorded, triaged, fixed or excepted, and verified.
---

# Security findings

This package uses the same release gate, process and evidence as Ananke Plexus. See
[Security findings](https://neo-pragnya.github.io/Ananke-Plexus/docs/guides/security-findings/): what each release's
scan report contains (`findings.json`, `triage.md` and a CycloneDX SBOM), how to triage a quarantine by the rule that
fired, how exceptions expire, and what to send your Black Duck administrator.

In short:

- **The gate runs on every pull request and every release.** It's `scripts/scan_dist.py`, and it blocks on secrets,
  CVEs from pip-audit, Grype and osv-scanner, undeclared bundled code, malware-shaped code, unreviewed heuristics, our
  metadata, vulnerable lower bounds, dependency licences, licence names in our files, and expired exceptions.
- **Accepted findings are in `.scan-dist.toml`,** each with a reason, an owner and a review date. Changing them needs the
  owner's review.
- **The scan report for each release is the run's `dist-scan` artifact.**
