#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["tyro"]
# ///
"""Write figure.html beside this file: a tracker's GitHub links before this slice and after it.

The three panels are the board's own rows, lifted whole out of three real renders of one demo
tracker and laid under the board's own stylesheet, so a link's colour is the board's colour and the
words it says on hover are the board's words rather than a picture of them. Hover a link in any
panel; the scheme switch puts all three through the night scheme.

The `before` render runs the board as the feature branch had it before this slice, read out of git,
so that panel is what the board did rather than an account of it. The renders stay in the work
directory, which is where the figure's own file:// links point.

Examples:

    figure.py
    figure.py --before eaf3703 --work /tmp/board-gh-figure
"""

import html
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import tyro

HERE = Path(__file__).parent
ROOT = HERE.parents[3]
TRACKER = ROOT / "mx" / "skills" / "tracker"
REFERENCES = json.loads((HERE / "references.json").read_text())
LOGGED_OUT = "To get started with GitHub CLI, please run:  gh auth login"  # what an unauthenticated gh says
ROWS = ("t-csv-import-02", "standalone-speed-up-tests")


@dataclass
class Args:
    before: str = "eaf3703"
    """The commit the `before` panel is rendered from: board-orients as this slice was cut from it."""
    work: Path = Path("/tmp/board-gh-figure")
    """Where the three renders are built and left. The figure's file:// links point into it, so a
    reader who has run this script can follow them."""


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    done = subprocess.run([str(a) for a in args], capture_output=True, **{"text": True, **kwargs})
    assert done.returncode == 0, f"{args[0]} failed: {str(done.stderr)[-2000:]}"
    return done


def demo_tracker(dest: Path) -> Path:
    """The tracker the board renders, with the three references on the two tickets that name any."""
    run("uv", "run", TRACKER / "demo_tracker.py", dest)
    for path, refs in REFERENCES["refs"].items():
        ticket = dest / "agent" / "tickets" / path
        ticket.write_text(re.sub(r"^gh: .*$", f"gh: [{', '.join(refs)}]", ticket.read_text(), flags=re.M))
    return dest / "agent" / "tickets"


def gh_stub(bin_dir: Path, answers: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "gh").write_text(f"#!/bin/sh\n{answers}\n")
    (bin_dir / "gh").chmod(0o755)


def board_at(ref: str, work: Path) -> Path:
    """The board as `ref` had it, with the rest of its directory, since the board imports its siblings."""
    tree = work / "before"
    tree.mkdir(parents=True, exist_ok=True)
    tar = run("git", "-C", str(ROOT), "archive", ref, "mx/skills/tracker", text=False)
    run("tar", "-x", "-C", str(tree), input=tar.stdout, text=False)
    return tree / "mx" / "skills" / "tracker" / "board.py"


def render(board: Path, tracker: Path, out: Path, bin_dir: Path) -> str:
    """One board, rendered with `bin_dir` first on PATH, so the gh it finds is the stub there."""
    run("uv", "run", board, tracker, "--no-watch", "--no-open", "--out", out,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"})
    return out.read_text()


def summary(page: str, row_id: str) -> str:
    """One row's line as the board wrote it: the details element with its summary and no body, which
    is the row folded, which is the row this figure is about."""
    opened = page.index(f'id="{row_id}"')
    start = page.rindex("<details", 0, opened)
    end = page.index("</summary>", opened) + len("</summary>")
    return page[start:end] + "</details>"


def mark(row: str, n: int, which: int = 0) -> str:
    """A numbered badge in front of the `which`th GitHub link on the row, which is where the note of
    that number points."""
    link = re.findall(r'<a class="gh[^>]*>', row)[which]
    return row.replace(link, f'<span class="mk">{n}</span>{link}', 1)


def note(page: str, n: int) -> str:
    """The page's one word about GitHub, where it said one."""
    found = re.search(r'<p class="absent" data-absent="github">.*?</p>', page)
    assert found, "the render said nothing about GitHub"
    return f'<span class="mk">{n}</span>{found.group(0)}'


def panel(title: str, what: str, rows: list[str], notes: list[str], absent: str = "") -> str:
    items = "".join(f'<li><span class="mk">{i + 1}</span><span>{n}</span></li>' for i, n in enumerate(notes))
    return (
        f'<figure class="panel"><figcaption><b>{html.escape(title)}</b> {what}</figcaption>'
        f'<div class="rows">{absent}{"".join(rows)}</div><ol class="notes">{items}</ol></figure>'
    )


def build(args: Args) -> str:
    tracker = demo_tracker(args.work / "demo")
    # the answer is stubbed rather than asked for: a figure that needed a GitHub login would render
    # differently on every machine and every day
    gh_stub(args.work / "answering", f"cat <<'JSON'\n{json.dumps(REFERENCES['answer'])}\nJSON")
    gh_stub(args.work / "logged-out", f'printf "%s\\n" "{LOGGED_OUT}" >&2\nexit 4')

    # the same tracker three times: the board as it was, the board now, and the board now with
    # GitHub out of reach. Each render gets its own page, so each keeps its own cache.
    pages = {
        "before": render(board_at(args.before, args.work), tracker, args.work / "before.html", args.work / "answering"),
        "after": render(TRACKER / "board.py", tracker, args.work / "after.html", args.work / "answering"),
        "unasked": render(TRACKER / "board.py", tracker, args.work / "unasked.html", args.work / "logged-out"),
    }
    style = pages["after"].split("<style>", 1)[1].split("</style>", 1)[0]

    rows = {name: [summary(page, row) for row in ROWS] for name, page in pages.items()}
    for name in ("before", "after"):  # a badge per reference, in the order the notes read them
        rows[name][0] = mark(mark(rows[name][0], 1, which=0), 2, which=1)
        rows[name][1] = mark(rows[name][1], 3)
    rows["unasked"][0] = mark(rows["unasked"][0], 2)

    panels = panel(
        "before", "the board as it was until this slice", rows["before"],
        ["<code>cli/cli#1</code>: a merged pull request, in the muted ink every reference wore.",
         "<code>cli/cli#2</code>: a closed issue, in the same ink, because the row could not tell the two apart.",
         "<code>anthropics/claude-code#96304</code>: an open issue, likewise. Hover any of the three and it says "
         "<i>A pull request or issue this ticket names, on GitHub.</i>: true of all three, and the same words for each."],
    ) + panel(
        "after", "the same tracker, the same three references", rows["after"],
        ["<code>cli/cli#1</code> in the callout purple: merged. Hover it for <i>A merged pull request on GitHub.</i>",
         "<code>cli/cli#2</code> struck through: closed. Hover it for <i>A closed issue on GitHub.</i>",
         "<code>anthropics/claude-code#96304</code> in the accent: open. Hover it for <i>An open issue on GitHub.</i> "
         "A draft is underlined, and a pull request whose review asked for changes takes the rose a question wears."],
    ) + panel(
        "after, with GitHub out of reach", "no <code>gh</code>, no auth or no network", rows["unasked"],
        ["The one note at the top of the page, above every row, carries what <code>gh</code> itself said. "
         "It is said once however many links the board shows, and nothing else on the page says it.",
         "Every reference is the muted link it was before this slice, and says the same words on hover: "
         "the board asked, was told nothing, and no row pretends otherwise."],
        absent=note(pages["unasked"], 1),
    )
    return PAGE.replace("${style}", style).replace("${panels}", panels)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub links on the board, before and after</title>
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
/* the board's own stylesheet, so every row below looks and behaves as it does on the board */
${style}

/* the figure around it */
  body { padding: 0 0 4rem; }
  /* the rows keep the width the board gives them: below about 1100px the board reflows a row, and
     the line the links sit on is what this figure is about */
  .page { max-width: 96rem; margin: 0 auto; padding: 0 1.5rem; }
  h1 { font-size: 1.6rem; font-weight: 600; margin: 2.5rem 0 .75rem; color: var(--strong); }
  .lead { color: var(--muted); max-width: 46rem; }
  .lead + .lead { margin-top: .75rem; }
  .scheme { margin-top: 1.5rem; font-family: var(--font-mono); font-size: .78rem; color: var(--muted);
    background: none; border: 1px solid var(--edge); border-radius: 4px; padding: .2rem .5rem; cursor: pointer; }
  .scheme:hover { color: var(--accent); border-color: var(--accent); }
  .panel { margin: 2.5rem 0 0; }
  figcaption { color: var(--muted); margin-bottom: .6rem; }
  figcaption b { color: var(--strong); font-weight: 600; }
  /* a row says its words below itself, so the last row's need room inside the panel: nothing here
     clips or scrolls, which is the precondition the board's own tooltip is written against */
  .rows { border: 1px solid var(--edge); border-radius: var(--radius); background: var(--ground-2);
    padding: .25rem 0 3.5rem; overflow: visible; }
  .rows .absent { padding: .5rem 1.25rem; }
  .notes { margin: .9rem 0 0; padding: 0; list-style: none; max-width: 52rem; }
  .notes li { display: flex; gap: .5rem; align-items: baseline; margin-top: .4rem; color: var(--muted); }
  .mk { flex: none; display: inline-grid; place-items: center; width: 1.25rem; height: 1.25rem; margin-right: .3rem;
    border-radius: 50%; background: var(--accent); color: var(--ground); font-family: var(--font-mono); font-size: .7rem; }
</style>
</head>
<body>
<div class="page">
<h1>GitHub links on the board, before and after</h1>
<p class="lead">Three renders of one tracker, whose two tickets name three real references in two
repositories. Every row below is the board's own markup under the board's own stylesheet, so the
links are live: hover one for the words it says.</p>
<p class="lead">Built by <code>figure.py</code> beside this file. The walkthrough of the state it
leaves is <code>demo</code>, beside it.</p>
<button class="scheme" onclick="document.documentElement.dataset.theme = document.documentElement.dataset.theme === 'night' ? 'day' : 'night'">day / night</button>
${panels}
</div>
</body>
</html>
"""


def main(args: Args) -> None:
    args.work.mkdir(parents=True, exist_ok=True)
    (HERE / "figure.html").write_text(build(args))
    print(HERE / "figure.html")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
