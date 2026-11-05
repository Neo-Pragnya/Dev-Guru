---
title: Business processes
description: Swimlanes, an offline viewer and BPMN 2.0 from a reviewed process document. Every step cites its source, nothing is guessed, and nothing runs.
---

# Business processes

Write a process as a numbered list, with each step naming who does it:

```markdown
# Order handling

1. Sales: Receive the order
2. Finance: Is the credit good?
   - Yes: go to step 3
   - No: go to step 5
3. Warehouse: Pick and pack
4. Warehouse: Ship the order. End.
5. Sales: Tell the customer
```

```bash
dev bpmn process.md                       # process.process.html: swimlanes, sources and the BPMN
dev bpmn process.md --xml p.bpmn --svg p.svg
```

Or open **Documentation** in `dev serve`, and choose **Make a process**.

| You write | You get |
| --- | --- |
| `1. Sales: Receive the order` | A task in the Sales lane |
| A step ending in `?`, with `- Yes: go to step 3` beneath it | A decision, with a labelled link for each line |
| `Go to step 4` at the end of a step | A link to that step, rather than the next |
| `End.` at the end of a step, or `- No: end` | An end event |

## Nothing is guessed

Each step cites its line. If the text doesn't hold together, the viewer says what's wrong and `dev bpmn` exits with 1. That covers a step going to one that doesn't exist, one nothing leads to or that can't reach an end, and a decision with fewer than two ways out. Ananke reports these, and doesn't repair them.

## Editing it elsewhere

The BPMN is standard 2.0, so tools like Camunda Modeler or bpmn.io can open and change it. Read an edited file back the same way:

```bash
dev bpmn edited.bpmn -o edited.html
ananke process check edited.bpmn --against process.md   # does it still say what the document says?
```

## Nothing runs

A process is a description to review. It's never marked executable, and neither tool runs it.
