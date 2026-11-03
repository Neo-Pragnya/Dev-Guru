---
title: Diagrams from documents
description: Turn the relationships an approved document states into an animated SVG where every edge cites its file and line, and nothing is invented.
---

# Diagrams from documents

`dev diagram` draws the relationships a document **states**, and every edge cites the line it came from:

```bash
dev diagram docs/payments.md                     # writes docs/payments.svg
dev diagram docs/payments.md --model model.json  # also write an editable model
dev diagram docs/payments.md --from-model model.json -o edited.svg
dev diagram docs/payments.md --static            # no animation
```

## What it reads

Only explicit statements, so text in a document can't talk it into adding a relationship:

````markdown
- API -> Queue: enqueues payment jobs
- Worker --> Queue: pulls jobs

```mermaid
flowchart LR
  W[Worker] -->|charges| P(Provider)
```

| From | To | Relation |
| --- | --- | --- |
| Ledger | Reports | feeds |
````

Prose and other code blocks are ignored. If a document has no explicit relationships, the command says so and draws
nothing. No model is involved.

## Citations and hypotheses

Hover an edge to see its file and line. You can edit the model to add or remove relationships, but each one is checked
against the document when it's rendered. The cited line must exist and name both ends. A relationship that fails this
is drawn as a **hypothesis**: dashed, with a "?", and counted in the summary. It's never drawn as a fact.

## Safe to embed

The SVG has no scripts, event handlers or external references, and every label is escaped text. The command checks
this before writing. The same document always gives the same bytes. Animation stops under reduced motion or with
`--static`.
