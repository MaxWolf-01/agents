#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["tyro"]
# ///
"""Write figure.html beside this file: a moved ticket's sessions on the board before this slice and after it.

One demo tracker whose build in review leaves the feature it was grilled into, the way board-orients
15 left board-orients and became the standalone ticket `debrief-ticket`. Two renders of it: the
board as this slice was cut from it, read out of git, and the board now. Each panel is the row's own
markup under the board's own stylesheet, so a date says the board's words on hover rather than a
picture of them.

Examples:

    figure.py
    figure.py --before 74212f1 --work /tmp/board-moves-figure
"""

import html
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import tyro

HERE = Path(__file__).parent
ROOT = HERE.parents[3]
TRACKER = ROOT / "mx" / "skills" / "tracker"
sys.path.insert(0, str(TRACKER))

from demo_tracker import S3, commit as demo_commit, git as demo_git  # noqa: E402

WAS = "agent/tickets/csv-import/02-map-columns.md"  # the build in review, filed and worked under the feature
NOW = "agent/tickets/map-columns.md"  # where it sits once it leaves: a standalone ticket
MOVED_ON = "2026-09-20T09:40:00+02:00"
ROW = "standalone-map-columns"


@dataclass
class Args:
    before: str = "74212f1"
    """The commit the `before` panel is rendered from: board-orients as this slice was cut from it."""
    work: Path = Path("/tmp/board-moves-figure")
    """Where the two renders are built and left. The figure's file:// links point into it, so a
    reader who has run this script can follow them."""


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    done = subprocess.run([str(a) for a in args], capture_output=True, **{"text": True, **kwargs})
    assert done.returncode == 0, f"{args[0]} failed: {str(done.stderr)[-2000:]}"
    return done


def moved_tracker(dest: Path) -> Path:
    """The demo tracker with its build in review moved out of csv-import, in one commit of its own:
    the blocking edge goes with the move, since the feature's 01 is not a standalone ticket's
    blocker. Three sessions committed on it under the feature, one of them a worker on another host
    the board leaves off; a fourth moves it out."""
    run("uv", "run", TRACKER / "demo_tracker.py", dest)
    ticket = dest / WAS
    ticket.write_text(re.sub(r"^blocked-by: .*\n", "", ticket.read_text(), flags=re.M))
    (dest / NOW).parent.mkdir(parents=True, exist_ok=True)
    demo_git(dest, "add", "--", WAS)
    demo_git(dest, "mv", WAS, NOW)
    demo_commit(dest, S3, MOVED_ON, "map-columns: out of csv-import, it stands on its own", "agent/tickets")
    return dest / "agent" / "tickets"


def board_at(ref: str, work: Path) -> Path:
    """The board as `ref` had it, with the rest of its directory, since the board imports its siblings."""
    tree = work / "before"
    tree.mkdir(parents=True, exist_ok=True)
    tar = run("git", "-C", str(ROOT), "archive", ref, "mx/skills/tracker", text=False)
    run("tar", "-x", "-C", str(tree), input=tar.stdout, text=False)
    return tree / "mx" / "skills" / "tracker" / "board.py"


def render(board: Path, tracker: Path, out: Path) -> str:
    """One board, rendered against the fixture's own transcripts, so the sessions it lists are the
    fixture's and the resume commands are the ones its transcripts answer."""
    claude = tracker.parent.parent / "claude"
    run("uv", "run", board, tracker, "--no-watch", "--no-open", "--out", out,
        env={**os.environ, "CLAUDE_CONFIG_DIR": str(claude)})
    return out.read_text()


def opened(page: str, row_id: str, which: str) -> str:
    """The row as the board wrote it, opened, with its sessions block and nothing else of its body:
    the block is what this slice changed, and the rest of an opened ticket runs for pages."""
    at = page.index(f'id="{row_id}"')
    start = page.rindex("<details", 0, at)
    summary = page[start: page.index("</summary>", at) + len("</summary>")]
    return summary.replace("<details ", "<details open ", 1) + f'<div class="body">{sessions(page, at, which)}</div></details>'


def sessions(page: str, at: int, which: str) -> str:
    """The sessions block of the row that starts at `at`. Both renders list at least the session
    that moved the ticket, so no block at all means the board's markup has moved under this figure,
    which would otherwise draw an empty box and read as a board that lists nothing."""
    label = '<p class="label">sessions on this machine</p>'
    found = page.find(label, at)
    assert found >= 0, f"the {which} render gives {ROW} no sessions block"
    start = page.rindex("<section", at, found)
    return page[start: page.index("</section>", found) + len("</section>")]


def mark(row: str, n: int, title: str) -> str:
    """A numbered badge in front of the session `title` names, which is where the note points."""
    listed = f'<span class="stitle">{html.escape(title)}</span>'
    assert listed in row, f"the row lists no session called {title}"
    return row.replace(listed, f'<span class="mk">{n}</span>{listed}', 1)


def panel(title: str, what: str, row: str, notes: list[str]) -> str:
    items = "".join(f'<li><span class="mk">{i + 1}</span><span>{n}</span></li>' for i, n in enumerate(notes))
    return (
        f'<figure class="panel"><figcaption><b>{html.escape(title)}</b> {what}</figcaption>'
        f'<div class="rows">{row}</div><ol class="notes">{items}</ol></figure>'
    )


def build(args: Args) -> str:
    tracker = moved_tracker(args.work / "demo")
    pages = {
        "before": render(board_at(args.before, args.work), tracker, args.work / "before.html"),
        "after": render(TRACKER / "board.py", tracker, args.work / "after.html"),
    }
    style = pages["after"].split("<style>", 1)[1].split("</style>", 1)[0]

    rows = {name: opened(page, ROW, name) for name, page in pages.items()}
    rows["before"] = mark(rows["before"], 1, "Triage after the holidays")
    rows["after"] = mark(mark(mark(rows["after"], 1, "Grilling the CSV import"),
                              2, "Dispatching csv-import, wave 1"), 3, "Triage after the holidays")

    panels = panel(
        "before", "the board as it was until this slice", rows["before"],
        ["<b>Triage after the holidays</b>, 2026-09-20: the session that moved the ticket, and the only "
         "one the board could find. Every session that worked on the ticket while it was "
         "<code>csv-import/02-map-columns.md</code> is keyed by that path, which nothing on the board now "
         "reads, so the ticket reads as work nobody has touched."],
    ) + panel(
        "after", "the same tracker, the same move", rows["after"],
        ["<b>Grilling the CSV import</b>, 2026-09-14: the session that filed the ticket, back on it. It "
         "committed under <code>csv-import/02-map-columns.md</code>, and git records the move, so the "
         "board follows it.",
         "<b>Dispatching csv-import, wave 1</b>, 2026-09-17 → 2026-09-18: the orchestrator that claimed "
         "the slice and flipped it to review, likewise under the old path. Its span is what it did across "
         "both days, unchanged by the move.",
         "<b>Triage after the holidays</b>, 2026-09-20: the session that moved the ticket, where it was "
         "before. A ticket that moved twice lists the sessions from all three of its paths the same way: "
         "each move carries what the path before it held."],
    )
    return PAGE.replace("${style}", style).replace("${panels}", panels).replace("${work}", html.escape(str(args.work)))


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A moved ticket's sessions, before and after</title>
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
  .page { max-width: 74rem; margin: 0 auto; padding: 0 1.5rem; }
  h1 { font-size: 1.6rem; font-weight: 600; margin: 2.5rem 0 .75rem; color: var(--strong); }
  .lead { color: var(--muted); max-width: 46rem; }
  .lead + .lead { margin-top: .75rem; }
  .lead a { color: var(--accent); }
  .scheme { margin-top: 1.5rem; font-family: var(--font-mono); font-size: .78rem; color: var(--muted);
    background: none; border: 1px solid var(--edge); border-radius: 4px; padding: .2rem .5rem; cursor: pointer; }
  .scheme:hover { color: var(--accent); border-color: var(--accent); }
  .panel { margin: 2.5rem 0 0; }
  figcaption { color: var(--muted); margin-bottom: .6rem; }
  figcaption b { color: var(--strong); font-weight: 600; }
  /* a date says its words below itself, so the last one needs room inside the panel: nothing here
     clips or scrolls, which is the precondition the board's own tooltip is written against */
  .rows { border: 1px solid var(--edge); border-radius: var(--radius); background: var(--ground-2);
    padding: .25rem 0 3.5rem; overflow: visible; }
  .notes { margin: .9rem 0 0; padding: 0; list-style: none; max-width: 52rem; }
  .notes li { display: flex; gap: .5rem; align-items: baseline; margin-top: .4rem; color: var(--muted); }
  .notes b { color: var(--strong); font-weight: 600; }
  .mk { flex: none; display: inline-grid; place-items: center; width: 1.25rem; height: 1.25rem; margin-right: .3rem;
    border-radius: 50%; background: var(--accent); color: var(--ground); font-family: var(--font-mono); font-size: .7rem; }
</style>
</head>
<body>
<div class="page">
<h1>A moved ticket's sessions, before and after</h1>
<p class="lead">One demo tracker, rendered twice. Its build in review was filed and worked on inside
the feature <code>csv-import</code>, then moved out to <code>agent/tickets/map-columns.md</code> as a
standalone ticket, which is what board-orients 15 did on 2026-09-23 when it became
<code>debrief-ticket</code>. Three sessions committed on it before the move and a fourth moved it
out. Three of the four are below: the worker that built it ran on another host, and the board lists
no session this machine could not resume.</p>
<p class="lead">Both rows below are the board's own markup under the board's own stylesheet, opened,
with everything but the sessions block cut away. Hover a date for the words the board says about it.
The full renders are <a href="file://${work}/before.html">before.html</a> and
<a href="file://${work}/after.html">after.html</a>.</p>
<p class="lead">Built by <code>figure.py</code> beside this file. The walkthrough on this repo's own
tracker is <code>demo</code>, beside it.</p>
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
