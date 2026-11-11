---
title: Reviewing a change
description: Review a change from Git, the code graph and the project's own reports, and draft its pull request description.
---

# Reviewing a change

```bash
dev review --base main                       # committed and uncommitted changes since main
dev review --base main --spec specs/pricing.md --pr-body PR.md
dev review --base origin/main --json -o review.json
```

`dev review` exits `1` when something blocks the change, so it works as a CI step, and `2` when the base isn't a
commit.

| Part | Where it comes from |
| --- | --- |
| **Changed** | `git diff` against the base (committed and uncommitted): files, the functions and classes whose lines changed, and the commits |
| **Reach** | who calls the changed functions, and the files that import a changed file, directly or not (Ananke's code graph) |
| **Blocking** | findings Ananke ranks *fix now* for this change: scanner findings in changed files, failing tests, low coverage on a changed file, a reachable critical vulnerability; and, with `--spec`, a requirement whose code changed but that no test mentions |
| **Advisory** | findings ranked *fix soon*, a changed function with complexity of 10 or more, a changed file in an import cycle, a requirement only possibly linked |
| **Retest** | the test files that import what the change reaches, as a command, and the gates whose reports the findings came from |

## The pull request description

`--pr-body FILE` drafts one from the review: a summary from the commits, the changed functions, the requirements it
touches and whether they're tested, the tests to run, the evidence (revision and model digest) and the residual risks.
Every line comes from the review. Read and edit it before posting: nothing is posted for you.

## What it can't see

Calls made dynamically, behaviour at run time, and anything newer than the reports in the repository. Rerun the
listed gates to confirm.
