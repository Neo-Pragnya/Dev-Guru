---
title: Mentoring from evidence
description: Advice only on failures that repeat across your Ananke runs, and a map of the lessons your team has captured.
---

# Mentoring from evidence

Dev Guru's mentoring is about what actually went wrong, not about style or opinion. It reads the runs Ananke
recorded in this workspace and the lessons captured from them.

## Advice on failures that repeat

```bash
dev mentor                       # advice for developers
dev mentor --level novice        # the same advice in plain words
dev mentor --level executive -o feedback.md
dev mentor --min-repeats 3 --json
```

- A failure is grouped with others like it by run kind, code and message, with what changes between runs (ids,
  numbers, quoted text, paths) masked.
- Only a failure seen in at least `--min-repeats` runs (2 by default, never fewer) gets advice. Each piece of advice
  names the runs, the code, an example message and what that code means, and says whether retrying can help.
- A failure seen once is listed under *Seen once*, with no advice: one occurrence isn't a pattern.
- If a **reviewed** lesson (a learning candidate that passed its gate) talks about the same thing, it's linked, with
  the words they share. Unreviewed lessons are never offered as advice.
- `--level` changes the words, not the evidence: every level cites the same runs.

## The learning graph

```bash
dev learning graph               # Mermaid
dev learning graph -f json       # dev-guru/learning-graph@1
```

Each lesson, its status (*needs review*, *blocked*, *reviewed*, *published*), the runs it was learned from and the
project files it mentions. Lessons that share at least two terms are linked, and the terms several lessons share are
listed as patterns: the lessons most likely to transfer to other work.

It only reads. Review a lesson with `dev learning review` and promote it with `ananke learning promote`.
