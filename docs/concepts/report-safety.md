---
title: Report safety
description: Why an explorer report can't run code, load anything from the network, or be broken by hostile source text.
---

# Report safety

A report embeds your source code and is meant to be shared, so it's built to be inert.

- **Offline.** All CSS and JavaScript is inlined, with system fonts only. The page's own Content Security Policy sets
  `connect-src 'none'`, so it can't make network requests even if it tried. Tests check that no external URL appears.
- **Source stays text.** The data is embedded as JSON inside `<script type="application/json">`, with `<`, `>`, `&`
  and the U+2028/U+2029 separators escaped, so a docstring containing `</script>` can't close the block. On screen,
  every name, path, docstring and line of source is set with `textContent`, never parsed as HTML.
- **View-only.** Opening a report never runs a command or starts a server. "Ask for deeper analysis" downloads a
  request file that you run yourself.
- **Traceable.** The manifest records the renderer, the Dev Guru and Ananke versions, the input digest and the git
  revision (including whether the working tree had uncommitted changes).

These guarantees are tested on every release. A browser test opens a report generated from a hostile fixture, where
a docstring is `</script><script>window.__pwned = 1</script>`. It checks that the text shows up as text, that no
`<img>` or `<script>` appears in the inspector, that nothing ran, and that no request left `file://`.

## Publication profiles

A report made for your own machine can show everything: the source of each class and function, docstrings, and
the Git revision it came from. Before you publish one outside the team, use the **public** profile:

```bash
dev explore . -o explorer.html --profile public
```

| | `private` (default) | `public` |
| --- | --- | --- |
| files, packages, sizes, imports, calls, cycles, hotspots | ✓ | ✓ |
| signatures | ✓ | ✓, with string defaults blanked (`url='…'`) |
| source of classes and functions | ✓ | removed |
| docstrings | ✓ | removed |
| Git commit and dirty flag | ✓ | removed |

The report lists what was removed among its limitations, the manifest records `"profile": "public"`, and the input
digest covers exactly what the published report contains.
