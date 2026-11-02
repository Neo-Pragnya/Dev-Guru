"""``dev present``: Markdown slides → one self-contained, offline, accessible HTML deck.

Authoring::

    ---
    title: Quarterly architecture review
    theme: lantern            # lantern (dark) or paper (light)
    lang: en
    ---

    # First slide

    Text, **emphasis**, `code`, tables, fenced code.

    ---

    ## Second slide

    + bullets written with "+" appear one at a time
    + the rest of the list stays as is

    ::: columns
    Left column
    |||
    ![Diagram of the queue](img/queue.png)
    :::

    ```chart
    {"type": "bar", "title": "Deploys per week", "labels": ["W1", "W2"], "values": [4, 7], "unit": "deploys"}
    ```

    Notes: speaker notes, shown with the N key.

Safety and access: raw HTML in the Markdown is shown as text; images must be local files with alt text and are
embedded; the page's CSP forbids every network request; slides are labelled for screen readers; navigation works
from the keyboard; animations stop under reduced motion. :func:`check` verifies a built deck offline.
"""

from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

THEMES = ("lantern", "paper")
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/svg+xml", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class DeckError(ValueError):
    pass


@dataclass
class Deck:
    title: str
    theme: str
    lang: str
    slides: list[str]


def _front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.split("#", 1)[0].strip().strip("'\"")
    return meta, text[end + 5 :]


def _split(body: str) -> list[str]:
    """Slides are separated by a line of three dashes (outside fenced code)."""
    slides: list[str] = []
    cur: list[str] = []
    fence = False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            fence = not fence
        if line.strip() == "---" and not fence:
            slides.append("\n".join(cur))
            cur = []
        else:
            cur.append(line)
    slides.append("\n".join(cur))
    return [s.strip() for s in slides if s.strip()]


def _chart(spec_text: str) -> str:
    try:
        spec = json.loads(spec_text)
        labels, values = [str(x) for x in spec["labels"]], [float(v) for v in spec["values"]]
    except (ValueError, KeyError, TypeError) as exc:
        raise DeckError(f"chart block isn't valid: {exc}") from exc
    if spec.get("type", "bar") != "bar" or len(labels) != len(values) or not values:
        raise DeckError("chart blocks support type 'bar' with matching labels and values")
    title, unit = str(spec.get("title", "Chart")), str(spec.get("unit", ""))
    top = max(values) or 1
    w, h, pad, bw = 640, 300, 36, 600 / len(values)
    bars = []
    for i, (lab, val) in enumerate(zip(labels, values, strict=True)):
        bh = (h - 2 * pad) * val / top
        x, y = pad + i * bw + bw * 0.15, h - pad - bh
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw * 0.7:.1f}" height="{bh:.1f}" rx="4" class="bar" style="--i:{i}"/>'
            f'<text x="{x + bw * 0.35:.1f}" y="{h - pad + 18}" class="axis">{html.escape(lab)}</text>'
            f'<text x="{x + bw * 0.35:.1f}" y="{y - 6:.1f}" class="value">{val:g}</text>'
        )
    rows = "".join(
        f'<tr><th scope="row">{html.escape(lab)}</th><td>{val:g} {html.escape(unit)}</td></tr>'
        for lab, val in zip(labels, values, strict=True)
    )
    desc = ", ".join(f"{lab}: {val:g}" for lab, val in zip(labels, values, strict=True))
    return (
        f'<figure class="chart"><svg viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}. {html.escape(desc)} {html.escape(unit)}">'
        f"<title>{html.escape(title)}</title>{''.join(bars)}</svg>"
        f"<figcaption>{html.escape(title)}</figcaption>"
        f'<table class="sr-only"><caption>{html.escape(title)}</caption><tbody>{rows}</tbody></table></figure>'
    )


def _renderer(base: Path) -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
    root = base.resolve()

    def image(_self: Any, tokens: Any, idx: int, options: Any, env: Any) -> str:
        tok = tokens[idx]
        src, alt = str(tok.attrGet("src") or ""), tok.content.strip()
        if not alt:
            raise DeckError(f"image {src!r} needs alt text: ![what it shows]({src})")
        if re.match(r"^[a-z]+:", src, re.I):
            raise DeckError(f"image {src!r}: decks are offline, so images must be local files")
        path = (root / src).resolve()
        if root not in path.parents or not path.is_file():
            raise DeckError(f"image {src!r} not found inside {root}")
        mime = mimetypes.guess_type(path.name)[0] or ""
        if mime not in IMAGE_TYPES or path.stat().st_size > MAX_IMAGE_BYTES:
            raise DeckError(f"image {src!r}: use png, jpeg, gif, svg or webp under 5 MB")
        data = base64.b64encode(path.read_bytes()).decode()
        return f'<img src="data:{mime};base64,{data}" alt="{html.escape(alt)}">'

    def fence(_self: Any, tokens: Any, idx: int, options: Any, env: Any) -> str:
        tok = tokens[idx]
        if tok.info.strip() == "chart":
            return _chart(tok.content)
        lang = html.escape(tok.info.strip().split(" ")[0])
        return f'<pre><code class="lang-{lang}">{html.escape(tok.content)}</code></pre>'

    def bullet_open(_self: Any, tokens: Any, idx: int, options: Any, env: Any) -> str:
        return '<ul class="steps">' if tokens[idx].markup == "+" else "<ul>"

    md.add_render_rule("image", image)
    md.add_render_rule("fence", fence)
    md.add_render_rule("bullet_list_open", bullet_open)
    return md


def _slide(md: MarkdownIt, text: str) -> tuple[str, str]:
    notes = ""
    m = re.search(r"(?ms)^Notes:\s*(.*)\Z", text)
    if m:
        notes, text = m.group(1).strip(), text[: m.start()].rstrip()
    parts = re.split(r"(?ms)^::: columns\s*$(.*?)^:::\s*$", text)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            cols = [md.render(c.strip()) for c in re.split(r"(?m)^\|\|\|\s*$", part)]
            out.append(
                f'<div class="cols" style="--n:{len(cols)}">'
                + "".join(f"<div>{c}</div>" for c in cols)
                + "</div>"
            )
        elif part.strip():
            out.append(md.render(part))
    return "".join(out), md.render(notes) if notes else ""


def parse(text: str) -> tuple[dict[str, str], list[str]]:
    meta, body = _front_matter(text)
    slides = _split(body)
    if not slides:
        raise DeckError("the deck has no slides")
    return meta, slides


def build(text: str, base: Path, *, theme: str | None = None) -> str:
    meta, slides = parse(text)
    theme = theme or meta.get("theme", "lantern")
    if theme not in THEMES:
        raise DeckError(f"theme {theme!r}: choose {', '.join(THEMES)}")
    title = (
        meta.get("title") or re.sub(r"^#+\s*", "", slides[0].splitlines()[0]).strip() or "Slides"
    )
    md = _renderer(base)
    sections = []
    for i, s in enumerate(slides, start=1):
        body, notes = _slide(md, s)
        aside = f'<aside class="notes" aria-label="Speaker notes">{notes}</aside>' if notes else ""
        sections.append(
            f'<section class="slide" aria-roledescription="slide" aria-label="{i} of {len(slides)}" id="s{i}" '
            f'{"" if i == 1 else "hidden"}><div class="frame">{body}</div>{aside}</section>'
        )
    return (
        TEMPLATE.replace("{{LANG}}", html.escape(meta.get("lang", "en")))
        .replace("{{TITLE}}", html.escape(title))
        .replace("{{THEME}}", theme)
        .replace("{{CSS}}", CSS)
        .replace("{{JS}}", JS)
        .replace("{{SLIDES}}", "\n".join(sections))
        .replace("{{COUNT}}", str(len(slides)))
    )


def check(page: str) -> list[str]:
    """Offline and accessibility problems in a built deck (empty when it passes)."""
    problems = []
    if "connect-src 'none'" not in page or "default-src 'none'" not in page:
        problems.append(
            "the page must forbid network requests (CSP default-src and connect-src 'none')"
        )
    for attr, url in re.findall(r'\b(src|href)="((?:https?:)?//[^"]+)"', page):
        if attr == "src":
            problems.append(f"loads a remote resource: {url}")
    if not re.search(r'<html lang="[a-z]{2}', page):
        problems.append("the <html> element needs a lang attribute")
    if re.search(r"<img(?![^>]*\balt=\"[^\"]+\")[^>]*>", page):
        problems.append("an image has no alt text")
    slides = re.findall(r'<section class="slide"[^>]*aria-label="(\d+) of (\d+)"', page)
    if not slides:
        problems.append("no labelled slides")
    if "prefers-reduced-motion" not in page:
        problems.append("animations don't respect reduced motion")
    if "localStorage" in page or "fetch(" in page:
        problems.append("the deck must not store data or fetch")
    return problems


CSS = """
:root{--radius:18px;--gap:28px}
[data-theme=lantern]{--bg:#0d0e1c;--panel:#15172f;--ink:#efedf9;--muted:#a4a6c9;--accent:#ffb347;--accent-2:#3dd6c6;--line:rgba(160,165,255,.18)}
[data-theme=paper]{--bg:#faf7f0;--panel:#fff;--ink:#1d1b2c;--muted:#5d5a73;--accent:#a3420f;--accent-2:#0b6f66;--line:rgba(40,30,90,.14)}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--ink);font:clamp(16px,1.6vw,26px)/1.5 Inter,system-ui,sans-serif;overflow:hidden}
.slide{position:absolute;inset:0;display:grid;place-items:center;padding:clamp(16px,4vw,64px)}
.slide[hidden]{display:none}
.frame{width:min(1200px,100%);max-height:100%;overflow:auto;animation:enter .45s ease both}
h1{font-size:2.6em;line-height:1.1;margin:0 0 .4em;letter-spacing:-.01em}h2{font-size:1.8em;margin:0 0 .5em;color:var(--accent)}
h3{font-size:1.2em;color:var(--accent-2)}p,li{max-width:62ch}code{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:.85em;background:var(--panel);padding:.1em .35em;border-radius:6px}
pre{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:1em;overflow:auto;font-size:.7em}pre code{background:none;padding:0}
table{border-collapse:collapse;font-size:.8em}th,td{border-bottom:1px solid var(--line);padding:.4em .8em;text-align:left}
img{max-width:100%;max-height:60vh;border-radius:var(--radius)}a{color:var(--accent-2)}
.cols{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:var(--gap);align-items:start}
@media (max-width:760px){.cols{grid-template-columns:1fr}}
.steps>li{transition:opacity .35s ease,transform .35s ease}.steps>li.later{opacity:0;transform:translateY(8px)}
.chart svg{width:100%;max-width:760px;height:auto}.chart .bar{fill:var(--accent);transform-origin:bottom;transform-box:fill-box;animation:grow .7s ease both;animation-delay:calc(var(--i)*80ms)}
.chart .axis,.chart .value{fill:var(--muted);font-size:13px;text-anchor:middle}.chart figcaption{color:var(--muted);font-size:.7em}
.notes{display:none;position:absolute;bottom:56px;left:5%;right:5%;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.6em 1em;font-size:.6em;color:var(--muted)}
.show-notes .notes{display:block}
.bar-progress{position:fixed;left:0;bottom:0;height:4px;background:linear-gradient(90deg,var(--accent),var(--accent-2));transition:width .3s ease}
.counter{position:fixed;right:16px;bottom:12px;font-size:12px;color:var(--muted)}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@keyframes enter{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@media print{body{overflow:visible}.slide,.slide[hidden]{position:relative;display:grid;page-break-after:always;min-height:100vh}.steps>li.later{opacity:1;transform:none}.bar-progress,.counter{display:none}}
"""

JS = """
(() => {
  const slides = [...document.querySelectorAll(".slide")];
  const bar = document.querySelector(".bar-progress"), counter = document.querySelector(".counter"), live = document.getElementById("live");
  let i = 0, step = 0;
  const steps = () => [...slides[i].querySelectorAll(".steps > li")];
  function show(n, s = 0) {
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach((el, k) => (el.hidden = k !== i));
    const list = steps(); step = Math.min(s, list.length);
    list.forEach((li, k) => li.classList.toggle("later", k >= step));
    bar.style.width = ((i + 1) / slides.length) * 100 + "%";
    counter.textContent = (i + 1) + " / " + slides.length;
    live.textContent = slides[i].getAttribute("aria-label") + ": " + (slides[i].querySelector("h1,h2,h3")?.textContent || "");
    history.replaceState(null, "", "#" + (i + 1));
  }
  function next() { const list = steps(); if (step < list.length) { step++; list.forEach((li, k) => li.classList.toggle("later", k >= step)); } else if (i < slides.length - 1) show(i + 1); }
  function prev() { if (i > 0) show(i - 1, Infinity); }
  document.addEventListener("keydown", (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (["ArrowRight", "PageDown", " ", "Enter"].includes(e.key)) { e.preventDefault(); next(); }
    else if (["ArrowLeft", "PageUp", "Backspace"].includes(e.key)) { e.preventDefault(); prev(); }
    else if (e.key === "Home") show(0); else if (e.key === "End") show(slides.length - 1, Infinity);
    else if (e.key.toLowerCase() === "n") document.body.classList.toggle("show-notes");
  });
  document.addEventListener("click", (e) => { if (!e.target.closest("a")) (e.clientX > innerWidth / 3 ? next : prev)(); });
  const fromHash = parseInt(location.hash.slice(1), 10);
  show(Number.isFinite(fromHash) ? fromHash - 1 : 0, Number.isFinite(fromHash) ? Infinity : 0);
  window.__deck = { show, next, prev, get index() { return i; }, get step() { return step; } };
})();
"""

TEMPLATE = """<!doctype html>
<html lang="{{LANG}}" data-theme="{{THEME}}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="Dev Guru present">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'">
<title>{{TITLE}}</title>
<style>{{CSS}}</style>
</head>
<body>
<main aria-roledescription="slide deck" aria-label="{{TITLE}}, {{COUNT}} slides">
{{SLIDES}}
</main>
<div class="bar-progress" aria-hidden="true"></div>
<div class="counter" aria-hidden="true"></div>
<p id="live" class="sr-only" aria-live="polite"></p>
<script>{{JS}}</script>
</body>
</html>
"""

__all__ = ["THEMES", "DeckError", "build", "check", "parse"]
