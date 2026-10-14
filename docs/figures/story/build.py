#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["tyro", "markdown", "tinycss2"]
# ///
"""Render story.md into a self-contained static folder: the mx workflow told as one page whose pictures grow.

story.md holds the text: an H1 title, a lead paragraph and an intro, then one `## ` section per
picture. A section opens with one of two lines, then its intro, then its steps:
- `figure: <name>`: the SVG of docs/figures/<name>.html, inlined with the part of the figure's CSS
  its SVG uses, scoped to it. Step k shows every element whose `data-step` (on itself or an
  ancestor) is at most k, and the elements of step k in the accent; an element with no
  `data-step` shows at every step. A figure whose SVG carries no `data-step` is shown whole at
  every step.
- `screenshot: <name>`: mx/assets/<name>.png (night) and <name>-light.png (day); one render serves
  both schemes. Each step may name a `region: x y w h`, fractions of the image, and the picture
  closes in on that region while the step is read.
- `step: <k>` starts step k, numbered from 1, its text the paragraph under it; `region:` may follow.

The output folder gets index.html, the screenshots it uses, the stylesheets, the scripts and the
fonts, and nothing on the page loads from outside it, so the folder can be copied anywhere and
opened over file:// or any static server. A missing figure or screenshot, a malformed section, a
figure whose `data-step` values do not run 1 to the section's step count, or one that marks steps
outside the SVG the page inlines fails the build, naming it.

Examples:

    docs/figures/story/build.py
    docs/figures/story/build.py --out /tmp/story
"""

import html
import json
import re
import shutil
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

import markdown
import tinycss2
import tyro

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ASSETS = REPO / "mx" / "assets"
FIGURES = REPO / "docs" / "figures"
TOKENS = REPO / "mx" / "skills" / "house-style" / "tokens.css"
PLUGIN = REPO / "mx" / ".claude-plugin" / "plugin.json"
GENERATOR = "docs/figures/story/build.py"
COPIED = ("story.css", "head.js", "story.js")


@dataclass
class Args:
    out: Path = HERE / "site"
    """Folder to write the page into. Emptied first; a non-empty folder this script did not write is refused."""


@dataclass
class Step:
    number: int
    body: str  # markdown
    region: tuple[float, float, float, float] | None = None


@dataclass
class Section:
    heading: str
    kind: str  # "figure" or "screenshot"
    name: str
    intro: str  # markdown
    steps: list[Step] = field(default_factory=list)


@dataclass
class Story:
    title: str
    lead: str
    intro: str  # markdown
    sections: list[Section]


def fail(message: str) -> None:
    sys.exit(f"build.py: {message}")


def warn(message: str) -> None:
    print(f"build.py: warning: {message}", file=sys.stderr)


def parse_region(text: str, where: str) -> tuple[float, float, float, float]:
    try:
        x, y, w, h = (float(v) for v in text.split())
    except ValueError:
        fail(f"{where}: region must be four numbers, x y w h, got {text!r}")
    if min(x, y) < 0 or w <= 0 or h <= 0 or x + w > 1.0001 or y + h > 1.0001:
        fail(f"{where}: region {text!r} does not lie inside the picture (fractions from 0 to 1)")
    return x, y, w, h


def parse_section(chunk: str) -> Section:
    heading, _, rest = chunk.partition("\n")
    heading = heading.strip()
    lines = rest.strip("\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    m = re.match(r"(figure|screenshot):\s*(\S+)\s*$", lines[0] if lines else "")
    if not m:
        fail(f"section {heading!r} must open with a `figure: <name>` or `screenshot: <name>` line")
    kind, name = m.groups()
    blocks = re.split(r"^step:\s*", "\n".join(lines[1:]), flags=re.M)
    intro, steps = blocks[0].strip(), []
    for i, block in enumerate(blocks[1:], 1):
        number, _, body = block.partition("\n")
        where = f"section {heading!r}, step {number.strip()}"
        if number.strip() != str(i):
            fail(f"{where}: steps are numbered 1, 2, 3 in order; expected {i}")
        body = body.strip()
        region = None
        if body.startswith("region:"):
            first, _, body = body.partition("\n")
            region = parse_region(first.removeprefix("region:"), where)
            if kind == "figure":
                fail(f"{where}: a figure's steps come from its data-step marks; region is for screenshots")
        if not body.strip():
            fail(f"{where} has no text")
        steps.append(Step(i, body.strip(), region))
    if not intro:
        fail(f"section {heading!r} needs an intro paragraph before its first step")
    if not steps:
        fail(f"section {heading!r} has no steps")
    return Section(heading, kind, name, intro, steps)


def parse(text: str) -> Story:
    """story.md into its title, lead, intro and sections, failing on a malformed section."""
    head, *chunks = re.split(r"^## ", text, flags=re.M)
    m = re.match(r"\s*# (.+)\n", head)
    if not m:
        fail("story.md must open with an H1 title")
    paragraphs = [p.strip() for p in head[m.end():].strip().split("\n\n") if p.strip()]
    if not paragraphs:
        fail("story.md needs a lead paragraph under its title")
    return Story(m.group(1).strip(), paragraphs[0], "\n\n".join(paragraphs[1:]),
                 [parse_section(c) for c in chunks])


# ---- figures: the SVG and the CSS it uses, scoped ---------------------------------------------


def figure_svg(source: str, name: str) -> str:
    """The figure's drawing: every top-level <svg> whose viewBox is wider than an icon, joined."""
    spans, depth, start = [], 0, 0
    for m in re.finditer(r"<svg\b|</svg\s*>", source):
        if m.group().startswith("<svg"):
            if depth == 0:
                start = m.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                spans.append(source[start:m.end()])
    drawings = []
    for svg in spans:
        vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg[:svg.index(">")])
        if vb and float(vb.group(1)) >= 200:
            drawings.append(svg)
    if not drawings:
        fail(f"figure {name!r}: no <svg> with a viewBox wider than 200 units")
    return "\n".join(drawings)


def namespace_ids(svg: str, prefix: str) -> tuple[str, dict[str, str]]:
    """Prefix every id in the SVG and every reference to one, so two figures' ids cannot meet."""
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    renamed = {i: f"{prefix}--{i}" for i in ids}
    for old, new in renamed.items():
        o = re.escape(old)
        svg = re.sub(rf'\bid="{o}"', f'id="{new}"', svg)
        svg = re.sub(rf"url\(#{o}\)", f"url(#{new})", svg)
        svg = re.sub(rf'((?:xlink:)?href)="#{o}"', rf'\1="#{new}"', svg)
        svg = re.sub(rf'(aria-(?:labelledby|describedby)="[^"]*)\b{o}\b', rf"\1{new}", svg)
    return svg, renamed


def root_tokens() -> dict[str, str]:
    """The page's own custom properties, so a figure's identical copies of them can be dropped."""
    out = {}
    for rule in tinycss2.parse_stylesheet(TOKENS.read_text(), skip_comments=True, skip_whitespace=True):
        if rule.type == "qualified-rule" and tinycss2.serialize(rule.prelude).strip() == ":root":
            for d in tinycss2.parse_declaration_list(rule.content, skip_comments=True, skip_whitespace=True):
                if d.type == "declaration":
                    out[d.name] = " ".join(tinycss2.serialize(d.value).split())
    return out


def split_selectors(prelude: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in prelude:
        depth += ch in "([" and 1 or 0
        depth -= ch in ")]" and 1 or 0
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return [p for p in parts + [cur.strip()] if p]


ROOT_PREFIX = re.compile(r'^((?::root|html)?\[data-theme[^\]]*\])\s+')


def scope_css(css: str, scope: str, svg: str, ids: dict[str, str], tokens: dict[str, str]) -> str:
    """The rules of the figure's stylesheet that can reach an element of its SVG, under `scope`.

    A selector is kept when every class, id and element name it names occurs in the SVG; it is
    rewritten to start at the scope, after a leading [data-theme] on the root. Custom properties
    the figure sets on :root move to the scope, less those equal to the page's own tokens."""
    classes = {c for attr in re.findall(r'\bclass="([^"]*)"', svg) for c in attr.split()}
    tags = {t.lower() for t in re.findall(r"<([a-zA-Z][\w-]*)", svg)}
    found_ids = set(ids)

    def keep(selector: str) -> str | None:
        prefix = ""
        m = ROOT_PREFIX.match(selector)
        if m:
            prefix, selector = m.group(1) + " ", selector[m.end():]
        bare = re.sub(r"\[[^\]]*\]|::?[\w-]+(\([^)]*\))?", " ", selector)
        cls = set(re.findall(r"\.([\w-]+)", bare))
        idents = set(re.findall(r"#([\w-]+)", bare))
        types = {t.lower() for t in re.findall(r"(?:^|[\s>+~(])([a-zA-Z][\w-]*)", bare)}
        if not (cls or idents or types) or "html" in types or "body" in types:
            return None
        if cls - classes or idents - found_ids or types - tags:
            return None
        for old, new in ids.items():
            selector = re.sub(rf"#{re.escape(old)}\b", f"#{new}", selector)
        return f"{prefix}{scope} {selector}"

    def rules(nodes) -> list[str]:
        out = []
        for rule in nodes:
            if rule.type == "qualified-rule":
                prelude = tinycss2.serialize(rule.prelude).strip()
                body = tinycss2.serialize(rule.content).strip()
                if prelude == ":root":
                    decls = [d for d in tinycss2.parse_declaration_list(rule.content, skip_comments=True,
                                                                        skip_whitespace=True)
                             if d.type == "declaration" and d.name.startswith("--")
                             and tokens.get(d.name) != " ".join(tinycss2.serialize(d.value).split())]
                    if decls:
                        out.append(f"{scope} {{ " + " ".join(
                            f"{d.name}: {tinycss2.serialize(d.value).strip()};" for d in decls) + " }")
                    continue
                kept = [s for s in (keep(sel) for sel in split_selectors(prelude)) if s]
                if kept:
                    out.append(f"{', '.join(kept)} {{ {body} }}")
            elif rule.type == "at-rule" and rule.content is not None:
                if rule.lower_at_keyword in ("media", "supports", "layer"):
                    inner = rules(tinycss2.parse_rule_list(rule.content, skip_comments=True,
                                                           skip_whitespace=True))
                    if inner:
                        head = tinycss2.serialize(rule.prelude).strip()
                        if rule.lower_at_keyword == "layer":
                            out.extend(inner)  # the page's layers are its own; the figure's rules sit unlayered
                        else:
                            out.append(f"@{rule.at_keyword} {head} {{\n" + "\n".join(inner) + "\n}")
                elif rule.lower_at_keyword == "keyframes":
                    out.append(tinycss2.serialize([rule]))
        return out

    return "\n".join(rules(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)))


@dataclass
class Drawing:
    svg: str
    css: str
    width: float
    height: float
    stepped: bool


def load_figure(section: Section, tokens: dict[str, str]) -> Drawing:
    path = FIGURES / f"{section.name}.html"
    if not path.exists():
        fail(f"section {section.heading!r}: no figure at {path}")
    source = path.read_text()
    svg = figure_svg(source, section.name)
    tagged = lambda text: len(re.findall(r'<[^!>][^>]*\bdata-step="', text))
    if tagged(source) != tagged(svg):
        fail(f"figure {section.name!r} marks steps outside the SVG this page inlines; move them into the drawing")
    svg, ids = namespace_ids(svg, f"fig-{section.name}")
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", source, flags=re.S))
    scoped = scope_css(css, f".fig-{section.name}", svg, ids, tokens)
    marks = {int(v) for v in re.findall(r'\bdata-step="(\d+)"', svg)}
    if re.search(r'\bdata-step="(?!\d+")', svg):
        fail(f"figure {section.name!r}: every data-step must be a whole number from 1")
    n = len(section.steps)
    if marks and marks != set(range(1, n + 1)):
        fail(f"figure {section.name!r} marks steps {sorted(marks)}, but its section in story.md has "
             f"steps 1 to {n}; every step needs its marks and every mark its step")
    if not marks:
        warn(f"figure {section.name!r} carries no data-step; it is shown whole at every step")
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).replace(",", " ").split()]
    return Drawing(svg, scoped, vb[2], vb[3], bool(marks))


# ---- screenshots ------------------------------------------------------------------------------


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{path} is not a PNG")
    return struct.unpack(">II", data[16:24])


def renders(section: Section) -> dict[str, Path]:
    """The scheme -> file map a screenshot section shows: both renders, or the one it has."""
    night, day = ASSETS / f"{section.name}.png", ASSETS / f"{section.name}-light.png"
    have = {k: p for k, p in (("night", night), ("day", day)) if p.exists()}
    if not have:
        fail(f"no render of {section.name!r} in {ASSETS} (looked for {night.name} and {day.name})")
    sizes = {png_size(p) for p in have.values()}
    if len(sizes) > 1:
        fail(f"the renders of {section.name!r} differ in size {sorted(sizes)}; regions need one geometry")
    return have


# ---- the page ---------------------------------------------------------------------------------


def inline(text: str) -> str:
    """One paragraph of markdown as inline HTML, without the <p>."""
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(text))


def plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", markdown.markdown(text))).replace("\n", " ")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


SCHEME_ICONS = """<svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
        <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>"""


def stage(section: Section, drawing: Drawing | None, shots: dict[str, str], size: tuple[int, int]) -> str:
    label = html.escape(section.heading, quote=True)
    if section.kind == "figure":
        # the figure page names its SVG by its own h1, which is not inlined; the page names it by the heading
        head, rest = drawing.svg.split(">", 1)
        head = re.sub(r'\s(?:role|aria-label|aria-labelledby)="[^"]*"', "", head)
        svg = f'{head} role="img" aria-label="{label}">{rest}'
        return f"""<div class="stage" data-kind="figure"{' data-stepped' if drawing.stepped else ''}>
          <div class="frame"><div class="canvas fig-{section.name}" data-w="{drawing.width:g}" data-h="{drawing.height:g}">
            {svg}
          </div></div>
        </div>"""
    w, h = size
    imgs = "\n".join(
        f'<img class="{scheme if len(shots) == 2 else "both"}" src="{src}" width="{w}" height="{h}" alt="{label}" decoding="async">'
        for scheme, src in shots.items())
    return f"""<div class="stage" data-kind="screenshot">
          <div class="frame"><div class="canvas" data-w="{w}" data-h="{h}">
            {imgs}
            <div class="focus" aria-hidden="true"></div>
          </div></div>
        </div>"""


def chapter(i: int, section: Section, stage_html: str) -> str:
    steps = "\n".join(
        f'<div class="beat prose" data-step="{s.number}"'
        + (f' data-region="{" ".join(f"{v:g}" for v in s.region)}"' if s.region else "")
        + f">{markdown.markdown(s.body)}</div>"
        for s in section.steps)
    return f"""<section class="chapter" id="{slug(section.heading)}">
      {stage_html}
      <div class="text">
        <h2 class="v-h2"><span class="v-num">{i:02}</span> {html.escape(section.heading)}</h2>
        <div class="prose intro">{markdown.markdown(section.intro)}</div>
        {steps}
      </div>
    </section>"""


def page(story: Story, chapters: list[str], css: str, version: str, github: str) -> str:
    contents = "\n".join(
        f'<li><a href="#{slug(s.heading)}"><span class="v-num">{i:02}</span> {html.escape(s.heading)}</a></li>'
        for i, s in enumerate(story.sections, 1))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="generator" content="{GENERATOR}">
  <meta name="description" content="{html.escape(plain(story.lead), quote=True)}">
  <title>{html.escape(story.title)}</title>
  <link rel="stylesheet" href="fonts/fonts.css">
  <link rel="stylesheet" href="tokens.css">
  <link rel="stylesheet" href="story.css">
  <style>
{css}
  </style>
  <script src="head.js"></script>
</head>
<body>
  <header class="bar">
    <a class="name v-h3" href="#top">mx</a>
    <span class="version v-meta">{html.escape(version)}</span>
    <button class="whole" id="whole" type="button" role="switch" aria-checked="false">
      <span class="track" aria-hidden="true"></span><span class="v-small">whole figures</span>
    </button>
    <button class="scheme" id="scheme" type="button" aria-label="switch scheme">
      {SCHEME_ICONS}
    </button>
  </header>

  <main id="top">
    <div class="hero">
      <h1 class="v-title">{html.escape(story.title)}</h1>
      <p class="v-lead">{inline(story.lead)}</p>
      <div class="prose">{markdown.markdown(story.intro)}</div>
      <ol class="contents" aria-label="contents">
        {contents}
      </ol>
    </div>
    {"".join(chapters)}
  </main>

  <footer class="page">
    <p>mx is on GitHub at <a href="{github}/tree/master/mx">MaxWolf-01/agents</a>; its
      <a href="{github}/blob/master/mx/README.md">README</a> covers installing it, and
      <a href="{github}/blob/master/mx/skills/orient/SKILL.md"><code>/mx:orient</code></a> is this workflow as the agents read it.</p>
  </footer>
  <script src="story.js"></script>
</body>
</html>
"""


def prepare(out: Path) -> None:
    """Empty the output folder, refusing one with content this script did not write."""
    if out.exists() and any(out.iterdir()):
        index = out / "index.html"
        if not (index.exists() and f'content="{GENERATOR}"' in index.read_text()):
            fail(f"{out} holds files this script did not write; pick an empty or new folder")
        shutil.rmtree(out)
    (out / "img").mkdir(parents=True)
    (out / "fonts").mkdir()


def main(args: Args) -> None:
    story = parse((HERE / "story.md").read_text())
    plugin = json.loads(PLUGIN.read_text())
    github = plugin["repository"].rstrip("/")
    tokens = root_tokens()
    # every check before the folder is touched
    loaded = [(s, load_figure(s, tokens) if s.kind == "figure" else renders(s))
              for s in story.sections]

    out = args.out.resolve()
    prepare(out)
    chapters, css, counts = [], [], {"stepped": 0, "whole": 0, "screenshots": 0}
    for i, (section, thing) in enumerate(loaded, 1):
        if section.kind == "figure":
            stage_html = stage(section, thing, {}, (0, 0))
            css.append(f"/* {section.name}: from docs/figures/{section.name}.html */\n{thing.css}")
            counts["stepped" if thing.stepped else "whole"] += 1
        else:
            shots, size = {}, (0, 0)
            for scheme, path in thing.items():
                shutil.copy2(path, out / "img" / path.name)
                shots[scheme] = f"img/{path.name}"
                size = png_size(path)
            stage_html = stage(section, None, shots, size)
            counts["screenshots"] += 1
        chapters.append(chapter(i, section, stage_html))

    (out / "index.html").write_text(page(story, chapters, "\n".join(css), plugin["version"], github))
    shutil.copy2(TOKENS, out / "tokens.css")
    for name in COPIED:
        shutil.copy2(HERE / name, out / name)
    for font in (HERE / "fonts").iterdir():
        shutil.copy2(font, out / "fonts" / font.name)
    print(f"wrote {out / 'index.html'}: {len(story.sections)} sections; figures {counts['stepped']} "
          f"stepped, {counts['whole']} whole; "
          f"{counts['screenshots']} screenshots")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
