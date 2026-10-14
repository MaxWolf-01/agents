#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["tyro", "markdown"]
# ///
"""Render story.md into a self-contained static folder: the mx workflow told as one page of pictures.

story.md holds the text: an H1 title, a lead paragraph and an intro, then one `## ` section per
picture. A section opens with `key: value` lines:
- image: the picture's name in mx/assets, `<name>.png` the night render and `<name>-light.png` the
  day render; a picture with one render shows it in both schemes
- source: the repo path of what draws or shoots the picture; defaults to docs/figures/<name>.html

The output folder gets index.html, the pictures it uses, the stylesheets, the scripts and the fonts,
and nothing on the page loads from outside it, so the folder can be copied anywhere and opened over
file:// or any static server. A missing picture or source fails the build, naming it.

Examples:

    docs/figures/story/build.py
    docs/figures/story/build.py --out /tmp/story
"""

import datetime
import html
import json
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import markdown
import tyro

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ASSETS = REPO / "mx" / "assets"
TOKENS = REPO / "mx" / "skills" / "house-style" / "tokens.css"
PLUGIN = REPO / "mx" / ".claude-plugin" / "plugin.json"
GENERATOR = "docs/figures/story/build.py"
META_KEYS = ("image", "source")


@dataclass
class Args:
    out: Path = HERE / "site"
    """Folder to write the page into. Emptied first; a non-empty folder this script did not write is refused."""


@dataclass
class Section:
    heading: str
    image: str
    source: str
    body: str  # markdown


@dataclass
class Story:
    title: str
    lead: str
    intro: str  # markdown
    sections: list[Section]


def fail(message: str) -> None:
    sys.exit(f"build.py: {message}")


def parse(text: str) -> Story:
    """story.md into its title, lead, intro and sections, failing on a malformed section."""
    head, *chunks = re.split(r"^## ", text, flags=re.M)
    m = re.match(r"\s*# (.+)\n", head)
    if not m:
        fail("story.md must open with an H1 title")
    paragraphs = [p.strip() for p in head[m.end():].strip().split("\n\n") if p.strip()]
    if not paragraphs:
        fail("story.md needs a lead paragraph under its title")
    sections = []
    for chunk in chunks:
        heading, _, rest = chunk.partition("\n")
        meta: dict[str, str] = {}
        lines = rest.split("\n")
        while lines and (not lines[0].strip() or re.match(rf"({'|'.join(META_KEYS)}):", lines[0])):
            line = lines.pop(0).strip()
            if line:
                key, _, value = line.partition(":")
                meta[key] = value.strip()
        if "image" not in meta:
            fail(f"section {heading!r} names no image")
        name = meta["image"]
        sections.append(Section(heading.strip(), name,
                                meta.get("source", f"docs/figures/{name}.html"), "\n".join(lines).strip()))
    return Story(m.group(1).strip(), paragraphs[0], "\n\n".join(paragraphs[1:]), sections)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{path} is not a PNG")
    return struct.unpack(">II", data[16:24])


def renders(section: Section) -> dict[str, Path]:
    """The scheme -> file map a section shows: both renders, or the one it has."""
    night, day = ASSETS / f"{section.image}.png", ASSETS / f"{section.image}-light.png"
    have = {k: p for k, p in (("night", night), ("day", day)) if p.exists()}
    if not have:
        fail(f"no render of {section.image!r} in {ASSETS} (looked for {night.name} and {day.name})")
    return have


def inline(text: str) -> str:
    """One paragraph of markdown as inline HTML, without the <p>."""
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(text))


def plain(text: str) -> str:
    """Markdown as plain text, for the viewer's caption."""
    return html.unescape(re.sub(r"<[^>]+>", "", markdown.markdown(text))).replace("\n", " ")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


SCHEME_ICONS = """<svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
        <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>"""


def figure(section: Section, shown: dict[str, str], sizes: dict[str, tuple[int, int]], github: str) -> str:
    """One picture as a button that opens the viewer, with the line naming its source."""
    alt = html.escape(section.heading, quote=True)
    if len(shown) == 2:
        imgs = "\n".join(
            f'<img class="{scheme}" src="{src}" width="{sizes[scheme][0]}" height="{sizes[scheme][1]}" '
            f'alt="{alt}" loading="lazy" decoding="async">'
            for scheme, src in shown.items()
        )
        day, night = shown["day"], shown["night"]
    else:
        (scheme, src), = shown.items()
        imgs = (f'<img src="{src}" width="{sizes[scheme][0]}" height="{sizes[scheme][1]}" '
                f'alt="{alt}" loading="lazy" decoding="async">')
        day = night = src
    kind = "figure, drawn by" if section.source.endswith(".html") else "screenshot, taken by"
    source = f'<a href="{github}/blob/master/{section.source}">{html.escape(section.source)}</a>'
    return f"""<figure class="shot">
          <button class="open" type="button" aria-label="open {alt} full size"
            data-day="{day}" data-night="{night}"
            data-title="{alt}" data-text="{html.escape(plain(section.body), quote=True)}">
            {imgs}
          </button>
          <figcaption class="v-meta"><span>{kind} {source}</span></figcaption>
        </figure>"""


def page(story: Story, figures: list[str], version: str, github: str) -> str:
    contents = "\n".join(
        f'<li><span class="v-num muted">{i:02}</span><a class="v-small" href="#{slug(s.heading)}">{html.escape(s.heading)}</a></li>'
        for i, s in enumerate(story.sections, 1)
    )
    steps = "\n".join(
        f"""<section class="step" id="{slug(s.heading)}">
        <h2 class="v-h2 column"><span class="v-num">{i:02}</span><span>{html.escape(s.heading)}</span></h2>
        <div class="prose column">{markdown.markdown(s.body)}</div>
        {fig}
      </section>"""
        for i, (s, fig) in enumerate(zip(story.sections, figures), 1)
    )
    built = datetime.date.today().isoformat()
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
  <script src="theme.js"></script>
</head>
<body>
  <header class="page">
    <div class="row">
      <span class="v-h3 name">mx</span>
      <button class="scheme" id="scheme" type="button" aria-label="switch scheme">
        {SCHEME_ICONS}
      </button>
    </div>
  </header>

  <main class="wide">
    <div class="hero column">
      <h1 class="v-title">{html.escape(story.title)}</h1>
      <p class="v-meta">mx {html.escape(version)} · {len(story.sections)} pictures · built {built}</p>
      <p class="v-lead">{inline(story.lead)}</p>
    </div>
    <div class="prose intro column">{markdown.markdown(story.intro)}</div>
    <ol class="contents column" aria-label="contents">
      {contents}
    </ol>
    {steps}
  </main>

  <footer class="page">
    <hr>
    <p class="v-small muted">Built by <a href="{github}/blob/master/{GENERATOR}">{GENERATOR}</a> from
      <a href="{github}/blob/master/docs/figures/story/story.md">story.md</a> and the pictures in
      <a href="{github}/tree/master/mx/assets">mx/assets</a>.</p>
    <p class="v-small muted">Set in Newsreader and IBM Plex Mono, both under the SIL Open Font License; the
      licence texts are <a href="fonts/OFL-Newsreader.txt">fonts/OFL-Newsreader.txt</a> and
      <a href="fonts/OFL-IBM-Plex-Mono.txt">fonts/OFL-IBM-Plex-Mono.txt</a>.</p>
  </footer>

  <div class="viewer" id="viewer" hidden role="dialog" aria-modal="true" aria-labelledby="viewer-title">
    <div class="stage"><img alt=""></div>
    <div class="bar">
      <div class="caption">
        <p class="v-h3" id="viewer-title"></p>
        <p class="v-small"></p>
        <p class="v-meta">drag to pan · scroll or pinch to zoom · 0 fits · esc closes</p>
      </div>
      <div class="tools">
        <button class="tool out" type="button" aria-label="zoom out">&minus;</button>
        <span class="zoom v-meta" aria-live="polite">100%</span>
        <button class="tool in" type="button" aria-label="zoom in">+</button>
        <button class="tool fit" type="button">fit</button>
        <button class="tool close" type="button">close</button>
      </div>
    </div>
  </div>
  <script src="zoom.js"></script>
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
    for s in story.sections:
        if not (REPO / s.source).exists():
            fail(f"section {s.heading!r}: source {s.source} does not exist")
    chosen = [renders(s) for s in story.sections]  # every check before the folder is touched

    out = args.out.resolve()
    prepare(out)
    figures = []
    for section, files in zip(story.sections, chosen):
        shown, sizes = {}, {}
        for scheme, path in files.items():
            shutil.copy2(path, out / "img" / path.name)
            shown[scheme] = f"img/{path.name}"
            sizes[scheme] = png_size(path)
        figures.append(figure(section, shown, sizes, github))

    (out / "index.html").write_text(page(story, figures, plugin["version"], github))
    shutil.copy2(TOKENS, out / "tokens.css")
    for name in ("story.css", "theme.js", "zoom.js"):
        shutil.copy2(HERE / name, out / name)
    for font in (HERE / "fonts").iterdir():
        shutil.copy2(font, out / "fonts" / font.name)
    print(f"wrote {out / 'index.html'}: {len(story.sections)} sections, "
          f"{sum(len(f) for f in chosen)} pictures")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
