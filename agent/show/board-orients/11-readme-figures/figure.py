#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown", "pillow", "tyro"]
# ///
"""Write figure.html beside this file: the README's board section, and its ticket-state figure,
as master has them and as this branch has them.

Every panel is the README's own markdown rendered, with the images that version points at read out
of the tree it belongs to, so a panel is the section a reader meets rather than an account of it.
Each image carries the alt text under it, since half of what this slice changed is that text. The
images are carried inline, so the file opens anywhere on its own.

Examples:

    figure.py
    figure.py --before 7093bf7
"""

import base64
import html
import io
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import markdown
import tyro
from PIL import Image

HERE = Path(__file__).parent
ROOT = HERE.parents[3]
README = "mx/README.md"
PANEL_WIDTH = 1400  # what a panel draws an image at on a wide screen; the renders are twice that

# Each note: the string in the rendered HTML its badge is planted in front of, and what to look at.
NOTES = {
    ("board", "before"): [
        ("<p><code>board</code>",
         "What waits on the user is <em>the queue of things only you can answer</em>: one "
         "<code>needs-human.md</code> per feature, belonging to no ticket. The rebuild link points into "
         "<code>agent/show/</code>, where the figure pipeline lived before it was promoted."),
        ('<div class="shot" data-of="The board: rows grouped',
         "The needs-me group holds three queue lines rather than tickets: a feature's debrief, and two "
         "questions with nowhere to hang. A row is a feature chip, a name and a fold mark, and says nothing "
         "about what it asks of the reader, how much of their time it wants, or how much it matters."),
        ('<div class="alt">alt: The board: rows grouped',
         "Both screenshots are the night board alone, where the five other figures in this README ship a day "
         "render and a night one and let the reader's own setting pick."),
        ('<div class="shot" data-of="One feature on the board',
         "Below the fold mark, an opened ticket is the paragraph its file holds. The alt text calls it "
         "<em>the question it asks</em>, and no question on it is one the board knows about."),
    ],
    ("board", "after"): [
        ("<p><code>board</code>",
         "The prose names the one group everything waiting on you is in, what a row carries, the copy button "
         "on each question, the briefing and the graph preview. The rebuild link points at "
         "<code>docs/figures/board-fixture/build.py</code>, which is what shot these."),
        ('<div class="shot" data-of="The board: needs me at the top',
         "Three tickets in needs me, each with its <code>D1</code> question under it and a copy button beside "
         "it, under a group-wide <em>copy all 3 questions</em>. Every row says what it asks of you (to rule "
         "on, prototype, your answer), your time on it and its priority, and the briefing names the next "
         "three picks beside them."),
        ('<div class="alt">alt: The board: needs me',
         "Both schemes ship, as for every other figure here; the switch at the top of this page puts the "
         "panel through the other one."),
        ('<div class="shot" data-of="One feature on the board',
         "The opened ticket reads as blocks: its question with the detail under it, what to build, and the "
         "acceptance criteria as a checklist."),
    ],
    ("state", "before"): [
        ('<div class="shot" data-of="Ticket state',
         "The chain is proposed, open, claimed, done, retired: a build waiting on a ruling has no state of "
         "its own, and the accent arrow from your ruling lands on <code>done</code>. The third source card is "
         "the needs-human queue, drawn as a file the page merges in."),
        ('<div class="alt">alt: Ticket state',
         "The alt text lists four statuses where the tracker knows five, and names the queue."),
    ],
    ("state", "after"): [
        ('<div class="shot" data-of="Ticket state',
         "<code>review</code> sits between claimed and done, in the accent that means waiting on you: the "
         "worker's last act writes it, and your accept writes <code>done</code> through the merge. The queue "
         "card is now a ticket's own <code>## Questions</code>, closed by a <code>Ruled</code> line, and a "
         "third board panel names what a row can ask of you."),
        ('<div class="alt">alt: Ticket state',
         "The alt text lists every status the tracker knows, and the needs-me group the questions feed."),
    ],
}
SECTIONS = {"board": "The board", "state": "Every ticket holds"}


@dataclass
class Args:
    before: str = "7093bf7"
    """The commit the `before` panels are read from: master, before this feature touched the README."""


def at(ref: str | None, path: str) -> str:
    """A text file as `ref` has it, or as the working tree has it when `ref` is None."""
    if ref is None:
        return (ROOT / path).read_text()
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{path}"],
                          capture_output=True, text=True, check=True).stdout


def render_png(ref: str | None, name: str) -> str:
    """One of mx/assets' renders as a data URI, from the tree the panel belongs to.

    The README ships its renders at twice the width a screen reads them at, and eight of those
    inline would make this one file larger than every other figure in the tree put together, so
    each is resampled to the width a panel actually draws it at.
    """
    if ref is None:
        data = (ROOT / "mx" / "assets" / name).read_bytes()
    else:
        data = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:mx/assets/{name}"],
                              capture_output=True, check=True).stdout
    shown = Image.open(io.BytesIO(data))
    if shown.width > PANEL_WIDTH:
        shown = shown.resize((PANEL_WIDTH, round(shown.height * PANEL_WIDTH / shown.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    shown.convert("RGB").save(buffer, "webp", quality=88, method=6)
    return "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode()


def section(text: str, heading: str) -> str:
    """The body of the README's <details> block whose summary starts with `heading`."""
    for block in re.findall(r"<details>\n(.*?)\n</details>", text, re.S):
        if block.startswith(f"<summary><b>{heading}"):
            return block.split("\n", 1)[1].strip()
    raise AssertionError(f"no <details> for {heading!r}")


def inline(md: str, ref: str | None) -> str:
    """The section with every image carried inline, one copy per scheme, and its alt text under it.

    A <picture> names a render per scheme; a bare <img> is one render the README shows in both, and
    which of the two a figure is makes one of the notes above.
    """
    def shot(day: str, night: str, alt: str) -> str:
        alt = html.escape(alt)
        return (f'<div class="shot" data-of="{alt}"><img class="day" src="{render_png(ref, day)}" alt="{alt}">'
                f'<img class="night" src="{render_png(ref, night)}" alt="{alt}">'
                f'<div class="alt">alt: {alt}</div></div>')

    def from_picture(m: re.Match) -> str:
        night = re.search(r'srcset="assets/([\w.-]+)"', m.group(0)).group(1)
        img = re.search(r'<img alt="(.*?)" src="assets/([\w.-]+)">', m.group(0), re.S)
        return shot(img.group(2), night, img.group(1))

    md = re.sub(r"<picture>.*?</picture>", from_picture, md, flags=re.S)
    return re.sub(r'<img alt="(.*?)" src="assets/([\w.-]+)">',
                  lambda m: shot(m.group(2), m.group(2), m.group(1)), md, flags=re.S)


def panel(which: str, side: str, what: str, body: str) -> str:
    """One side of a comparison: the section rendered, badged where each note points."""
    notes = NOTES[(which, side)]
    out = markdown.markdown(body)
    for n, (anchor, _) in enumerate(notes, 1):
        assert anchor in out, f"{which}/{side}: nothing matching {anchor!r} to plant badge {n} on"
        out = out.replace(anchor, f'<span class="mk">{n}</span>{anchor}', 1)
    items = "".join(f'<li><span class="mk">{n}</span><span>{note}</span></li>'
                    for n, (_, note) in enumerate(notes, 1))
    return (f'<figure class="panel"><figcaption class="head"><b>{side}</b> {what}</figcaption>'
            f'<div class="readme">{out}</div><ol class="notes">{items}</ol></figure>')


def build(args: Args) -> str:
    trees = {"before": args.before, "after": None}
    text = {side: at(ref, README) for side, ref in trees.items()}
    what = {"before": "as master has it", "after": "as this branch has it"}
    panels = ""
    for which, heading in SECTIONS.items():
        panels += f'<h2>{"The board section" if which == "board" else "The ticket-state figure"}</h2>'
        for side, ref in trees.items():
            panels += panel(which, side, what[side], inline(section(text[side], heading), ref))
    return PAGE.replace("${panels}", panels)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The README's board section, before and after</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<script>
  (() => {
    const asked = new URLSearchParams(location.search).get("theme");
    const night = asked ? asked === "night" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = night ? "night" : "day";
  })();
</script>
<style>
:root {
  color-scheme: light dark;
  --ground: light-dark(#f4e4cd, #1a1714);
  --ground-2: light-dark(#eddabe, #201c18);
  --edge: light-dark(#cfbca3, #4a433b);
  --muted: light-dark(#5e5650, #b0a89e);
  --body: light-dark(#37261d, #ede3d2);
  --strong: light-dark(#22140b, #faf2dc);
  --accent: light-dark(#426724, #6ea444);
  --font-body: "Newsreader", Georgia, serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --radius: 6px;
}
[data-theme="day"] { color-scheme: light; }
[data-theme="night"] { color-scheme: dark; }
body { background: var(--ground); color: var(--body); font-family: var(--font-body);
  font-size: 18px; line-height: 1.6; margin: 0; padding: 0 0 5rem; }
.page { max-width: 84rem; margin: 0 auto; padding: 0 1.5rem; }
h1 { font-size: 1.7rem; font-weight: 600; margin: 2.5rem 0 .75rem; color: var(--strong); }
h2 { font-size: 1.15rem; font-weight: 600; margin: 3.5rem 0 0; color: var(--strong);
  border-bottom: 1px solid var(--edge); padding-bottom: .4rem; }
.lead { color: var(--muted); max-width: 46rem; }
code { font-family: var(--font-mono); font-size: .82em; background: var(--ground-2);
  border-radius: 3px; padding: .05em .3em; }
a { color: var(--accent); }
.switch { margin-top: 1.5rem; font-family: var(--font-mono); font-size: .78rem; color: var(--muted);
  background: none; border: 1px solid var(--edge); border-radius: 4px; padding: .2rem .5rem; cursor: pointer; }
.switch:hover { color: var(--accent); border-color: var(--accent); }
.panel { margin: 2rem 0 0; }
.head { color: var(--muted); margin-bottom: .6rem; }
.head b { color: var(--strong); font-weight: 600; font-family: var(--font-mono); font-size: .9rem; }
.readme { border: 1px solid var(--edge); border-radius: var(--radius); padding: 1.25rem 1.5rem;
  background: var(--ground-2); }
.readme > p:first-of-type { margin-top: 0; }
.shot { margin: 1.25rem 0; }
.shot img { display: block; width: 100%; height: auto; border: 1px solid var(--edge); border-radius: 4px; }
[data-theme="day"] .shot img.night, [data-theme="night"] .shot img.day { display: none; }
.alt { margin-top: .4rem; color: var(--muted); font-size: .78rem;
  font-family: var(--font-mono); line-height: 1.5; }
.notes { margin: .9rem 0 0; padding: 0; list-style: none; max-width: 60rem; }
.notes li { display: flex; gap: .5rem; align-items: baseline; margin-top: .45rem; color: var(--muted); }
.mk { flex: none; display: inline-grid; place-items: center; width: 1.25rem; height: 1.25rem;
  border-radius: 50%; background: var(--accent); color: var(--ground);
  font-family: var(--font-mono); font-size: .7rem; margin-right: .35rem; }
</style>
</head>
<body>
<div class="page">
<h1>The README's board section, before and after</h1>
<p class="lead">The mx README as master has it and as this branch has it, rendered from its own
markdown with the screenshots each version points at, and each image's alt text under it. A badge
sits at the start of what its note is about, and the notes follow the panel.</p>
<p class="lead">Built by <code>figure.py</code> beside this file. The pipeline that shoots the
screenshots is <code>demo</code>, beside it.</p>
<button class="switch" onclick="document.documentElement.dataset.theme = document.documentElement.dataset.theme === 'night' ? 'day' : 'night'">day / night</button>
${panels}
</div>
</body>
</html>
"""


def main(args: Args) -> None:
    (HERE / "figure.html").write_text(build(args))
    print(HERE / "figure.html")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
