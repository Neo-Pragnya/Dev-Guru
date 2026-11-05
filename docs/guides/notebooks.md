---
title: Folders of notebooks
description: Point Dev Guru at a folder of notebooks and get an explanation of each one, how they feed each other, and every view of the code they contain, including code in %%writefile cells.
---

# Folders of notebooks

A course, a research project or a data science repository can keep most of its real code inside notebook cells. Point Dev Guru at the folder, and it treats that code like any other. You don't need to run anything.

```bash
dev explore ./my-course -o my-course.html    # one offline file with everything
dev serve ./my-course                        # the same pages, live
```

## Code in `%%writefile` cells counts

A cell like this writes a file when it runs:

```python
%%writefile churn/api.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}
```

Dev Guru reads it as a file at `churn/api.py`, next to the notebook, even if nobody has run it. So every page sees it:

| Written in a cell | Where it shows up |
| --- | --- |
| Python, JavaScript or TypeScript | Code map, Flow, Calls, Quality, and the source when you select it |
| A web route, or a call to one | API pathways and End-to-end flows |
| SQL or a model class | Data, as tables and fields |
| `requirements.txt` or `package.json` | CVEs |
| `docker-compose.yml` | Architecture |

Nothing is run or created. If a file is really on disk at that path, that's the one used, because it's what would be imported.

## The Notebooks page

For each notebook:

- **What it's for:** its first heading, and the paragraph under it.
- **What it covers:** every heading, its cell, and the first paragraph under it.
- **What it writes:** each file, with its cell, its size and what it defines. Select one to read it.
- **What it builds on, and what uses it:** a notebook importing a file another writes, or reading data another writes.
- **What it uses:** packages, and the data files it names.

The diagram shows how the notebooks feed each other. **Next notebook** goes through them in order, with Week-2 before Week-10.

An executed copy, or one in a delivery folder, is noticed and isn't counted again. Copies are compared on what they say, not on their outputs.

## Good to know

- The explanation comes from the notebook's own headings and code. Nothing is generated, so a notebook with no headings has little to say. An outline in Markdown cells gets you the most.
- A path built at run time, such as `%%writefile {name}.py`, can't be read. Neither can one that writes outside the folder. The page says how many it skipped.
- Data files need a path written in the code to appear. A computed path can't be followed.
- Outputs aren't read, so a notebook's results and charts aren't part of this.

## Sharing the result

The file has your code and notes in it, so treat it like the notebooks themselves. To share something outside your team:

```bash
dev explore ./my-course -o public.html --profile public
```

That leaves out source, docstrings, routes and tables, and keeps structure and counts.
