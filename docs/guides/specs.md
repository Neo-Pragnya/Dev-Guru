---
title: Spec-driven work
description: Start from an idea, write a spec with requirement ids, and trace every requirement to the code and tests that meet it.
---

# Spec-driven work

```bash
dev spec new "Order discounts" --idea "Customers abandon carts when discounts are unclear."
# fill in specs/order-discounts.md
dev spec trace specs/order-discounts.md
dev spec trace specs/order-discounts.md --level novice -o trace.md
dev spec trace specs/order-discounts.md --json
```

## Writing requirements

`dev spec new` writes a spec with a problem (your idea), users, outcomes, requirements, acceptance, scope and open
questions. It never overwrites a file. Give each requirement an id at the start of its line: `R1`, `REQ-12` or any
`ABC-3`, optionally bold or in a list. Only the **Requirements** section is read, when there is one.

Two habits make a trace useful:

- name the code a requirement touches in backticks (`` `discount` ``, `` `orders.py` ``);
- mention the id in the test that checks it (`# R1: the gold tier pays less`).

## What the trace says

| Status | Meaning |
| --- | --- |
| **linked** | The requirement names code that exists. Observed. |
| **possible** | It names no code, but at least two of its words match a function's or file's name or description. Inferred: up to three matches, best first. Check them. |
| **unlinked** | Nothing matches. Either it isn't built yet, or the words differ from the code's. |

**Tested** lists the test lines that mention the requirement's id. With `--level`, each requirement with code gets
the explanation ladder's words for its best match, so the trace is also a guide to that code for the reader you
chose.

## Kept in Ananke

The trace is recorded as `spec-trace.json` in the Ananke run that read the code, with the revision and the model's
digest. `ananke app evidence` lists it, so the trace stays with the code it was made against.

There's no language model involved: the same spec and code always give the same trace.
