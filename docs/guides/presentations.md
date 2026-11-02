---
title: Presentations
description: Turn Markdown slides into one offline, accessible HTML deck with themes, responsive columns, step-by-step lists, charts, speaker notes and keyboard navigation.
---

# Presentations

`dev present` turns a Markdown file into **one HTML file** you can present, email or attach. It works offline: the
page can't make network requests, and images are embedded.

```bash
dev present talk.md                  # writes talk.html
dev present talk.md --theme paper    # the light theme
dev present talk.html --check        # verify an existing deck
```

## Writing slides

```markdown
---
title: Quarterly architecture review
theme: lantern       # lantern (dark) or paper (light)
lang: en
---

# Quarterly architecture review

---

## What changed

+ Lists written with "+" appear one item at a time
+ Lists written with "-" or "*" appear all at once

Notes: Speaker notes. Press N while presenting to show them.

---

## Two columns

::: columns
Text on the left
|||
![Queue diagram: API, queue, two workers](img/queue.png)
:::

---

## Deploys per week

```chart
{"type": "bar", "title": "Deploys per week", "labels": ["W1", "W2", "W3"], "values": [4, 7, 9], "unit": "deploys"}
```
```

- **Slides** are separated by a line with `---` (fenced code can contain `---` safely).
- **Columns**: `::: columns` … `|||` … `:::`. On a narrow screen they stack.
- **Charts**: a `chart` block with bar data becomes an inline SVG with an accessible description and a hidden data
  table. Bars grow in, unless reduced motion is on.
- **Images** must be local files inside the deck's folder, with alt text. They're embedded, so the deck stays one
  file.
- **Raw HTML is shown as text.** A pasted `<script>` can't run.

## Presenting

| Key | Action |
| --- | --- |
| → · Space · Enter · Page Down | next step, then next slide |
| ← · Backspace · Page Up | previous slide |
| Home · End | first · last slide |
| N | show or hide speaker notes |
| click | right two-thirds: next; left third: previous |

The URL keeps the slide number (`talk.html#3`), so a link opens on that slide. Printing gives one slide per page,
with every step shown, ready to save as PDF.

## Accessibility and safety checks

Every deck is checked before it's written, and `--check` runs the same checks on any deck:

- a content security policy that forbids all network requests;
- no remote images, scripts or styles;
- `lang` on the page, and alt text on every image;
- slides labelled "n of N" for screen readers, with a live region announcing each slide;
- animations that stop under `prefers-reduced-motion`;
- no browser storage and no `fetch`.
