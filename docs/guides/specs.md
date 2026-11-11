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

## Test first: plan, tests, verify

```bash
dev spec plan specs/pricing.md            # kind, risk and tests for each requirement; tasks in order
dev spec tests specs/pricing.md           # failing tests for requirements with none (tests/spec/)
dev spec tests specs/pricing.md --style gherkin --out features
dev spec verify specs/pricing.md          # run the tests that name each requirement
```

- **Plan:** each requirement is classified by what it states, with fixed rules: *behaviour*, *state*, *invariant*
  ("never", "at most", "unique"), *interface* (API, request, status), *security* (role, token, secret) or
  *performance* (latency, "within"). Each kind brings its tests (an invariant gets a property test, an interface a
  contract test, security negative tests). Risk is high for invariants and security, or when the code reaches a
  quarter of the project. A requirement that says "after R1" comes after R1 in the task list.
- **Tests:** one failing test file per requirement with no test, named after its id and failing with what's missing.
  Existing files are never overwritten.
- **Verify:** runs, with pytest, the tests that name each requirement. A requirement is *done* only when it's linked
  to code, has tests and they pass. The result is kept in the Ananke run; exit `1` while any is open.

## Lock before building

```bash
dev spec lock specs/pricing.md            # specs/pricing.md.lock.json
dev spec trace specs/pricing.md --check-lock
```

The lock holds each requirement's text digest and the digest of every file the spec names. `--check-lock` reports
requirements added, removed or reworded and named code that changed since, and exits `1` on any drift.

