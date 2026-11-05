---
title: The explorer
description: Every view in the Dev Guru explorer report, what it shows and the questions it answers.
---

# The explorer

`dev explore` writes one HTML file with six views over the same data. Each one answers a different question about
the codebase.

```mermaid
flowchart LR
  A[Ananke builds the graph] --> M[Dev Guru view model]
  M --> C[Constellation]
  M --> F[Flow]
  M --> I[Impact]
  M --> K[Calls]
  M --> H[Hotspots]
  M --> T[Tour]
```

## ✦ Constellation: what's here?

Every file is a body in a 3D force-directed graph. Imports act as springs, files repel each other, and each package
pulls its own files together, so the structure of the code becomes the shape in space. Size shows lines of code,
colour shows the package, and nearer bodies are brighter.

- **Drag** the background to orbit, **scroll** to zoom, and use **⤢** (or `F`) to fit everything in view.
- **Drag a file** to pull it: the graph follows and settles again.
- **Hover** a file and its imports and importers light up, with pulses travelling along the connections.
- **Click** to open it in the inspector, and **double-click** to fly to it.
- Import cycles glow rose. When you leave it alone, the graph turns slowly.

It is drawn on a plain canvas by the report itself (no WebGL, no library), and with reduced motion it settles
before the first frame and stays still.

## ⇶ Flow: what depends on what?

Dependencies laid out left to right, from the *entry side* to the *foundations*. Large projects start at
**package** level, with thicker edges for more imports; switch to **files** for detail. Click a package to drill
in. Edges that close a cycle are drawn in rose.

## ◎ Impact: what breaks if this changes?

Pick a file or symbol and its dependents spread out in rings: one hop, two hops, and so on. For a file, that's
everything that imports it or calls into it. For a function, it's every caller. For a class, it's callers of the
class and of its methods. The headline gives the blast radius as a number and as a share of the workspace.

## ƒ Calls: who calls in, and what does it call?

The symbols of the selected file sit in the middle, with callers on the left and callees on the right. Calls and
base classes are inferred statically by Ananke, so dynamic dispatch isn't shown. Read them as strong hints, not
proof.

## ▦ Hotspots: where is change expensive?

A treemap with area for lines of code and colour for how many files import it. Large files that many others depend
on are where changes cost the most and tests matter most.

## ☄ Tour: show me around

A narrated walk: the overview, the biggest packages, entry points, the most depended-on file, the largest file,
cycles, external dependencies, and finally what the map can't see. Use the arrow keys or the buttons; it pauses
when you ask it to.

## Every page of `dev serve`, in the file

The tabs after Tour are the pages of [`dev serve`](repository-views.md): Overview, Code map, End-to-end flows, Notebooks, Data, API pathways, Architecture, Quality, Coverage, CVEs, Saving tokens, Code, Runs and Capabilities. They're the same pages, with a recording of what they ask for, so you can step through a flow or read a table's fields with nothing running.

A file can't start anything, so its buttons for analysing, checking for vulnerabilities and starting a run say to use `dev serve`. It makes no network requests, so CVEs say they weren't checked unless you ask when you make it:

```bash
dev explore . -o report.html --check-vulnerabilities
```

That looks up dependencies at osv.dev, sending package names and versions, and nothing else. With `--profile public`, these pages are left out, and a Repository tab keeps only counts. On a very large repository, the views of single files stop at a limit, and a page says if it can't show you one.

## The inspector

Pick anything to see its path, docstring, signature, source with line numbers, and every connection, each one
clickable.

- **Ask for deeper analysis** downloads a small request file. You run it with Dev Guru or Ananke; the report never
  runs anything itself.
- **Download this view's state** (in the command palette) saves what you're looking at as JSON.

## What a report can't tell you

Every report lists its limitations under *About*:

- It's static analysis of Python source; nothing is executed.
- Calls are inferred through imports.
- External modules are named, not analysed.
- Large projects may have symbols omitted to keep the file bounded.
