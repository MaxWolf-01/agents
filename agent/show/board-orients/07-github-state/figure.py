#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
"""Writes figure.html beside this file: a tracker's GitHub links before this slice and after it.

The three panels are the board's own rows, lifted whole out of three real renders of one demo
tracker and laid under the board's own stylesheet, so a link's colour is the board's colour and
the words it says on hover are the board's words rather than a picture of them. Hover a link in
any panel; the scheme switch puts all three through the night scheme.

The `before` render runs the board as the feature branch had it before this slice (BEFORE below),
read out of git, so the left panel is what the board did rather than an account of it.

    figure.py [--before <git ref>] [--keep <dir>]
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
TRACKER = HERE.parents[3] / "mx" / "skills" / "tracker"
BEFORE = "eaf3703"  # board-orients as 07-github-state was cut from it: 10-workflow landed, no GitHub state

# The demo's three references, in two repositories, with the states they were in on 2026-09-23
# (read from api.github.com that day). The panels are a render, so the answer is stubbed rather
# than asked for: a figure that needed a GitHub login would render differently on every machine.
REFS = {"csv-import/02-map-columns.md": ["cli/cli#1", "cli/cli#2"], "speed-up-tests.md": ["anthropics/claude-code#96304"]}
ANSWER = {"data": {
    "r0": {"nameWithOwner": "cli/cli",
           "n0": {"__typename": "PullRequest", "number": 1, "prState": "MERGED", "isDraft": False, "reviewDecision": "APPROVED"},
           "n1": {"__typename": "Issue", "number": 2, "issueState": "CLOSED"}},
    "r1": {"nameWithOwner": "anthropics/claude-code",
           "n0": {"__typename": "Issue", "number": 96304, "issueState": "OPEN"}},
}}
# what an unauthenticated gh says, and the code it says it with
LOGGED_OUT = "To get started with GitHub CLI, please run:  gh auth login"

ROWS = ("t-csv-import-02", "standalone-speed-up-tests")


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    done = subprocess.run([str(a) for a in args], capture_output=True, text=True, **kwargs)
    assert done.returncode == 0, f"{args[0]} failed: {done.stderr.strip()[-2000:]}"
    return done


def demo_tracker(dest: Path) -> Path:
    """The tracker the board renders, with the three references on the two tickets that name any."""
    run("uv", "run", TRACKER / "demo_tracker.py", dest)
    for path, refs in REFS.items():
        ticket = dest / "agent" / "tickets" / path
        ticket.write_text(re.sub(r"^gh: .*$", f"gh: [{', '.join(refs)}]", ticket.read_text(), flags=re.M))
    return dest / "agent" / "tickets"


def gh_stub(bin_dir: Path, answers: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "gh").write_text(f"#!/bin/sh\n{answers}\n")
    (bin_dir / "gh").chmod(0o755)


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
    """A numbered badge in front of the `which`th GitHub link on the row, which is where the note
    of that number points."""
    parts = row.split('<a class="gh')
    parts[which + 1] = f'<span class="mk">{n}</span><a class="gh' + parts[which + 1]
    return parts[0] + "".join(p if p.startswith("<span") else '<a class="gh' + p for p in parts[1:])


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


def build(work: Path) -> str:
    tracker = demo_tracker(work / "demo")
    board = TRACKER / "board.py"
    was = work / "before-board.py"
    was.write_text(run("git", "-C", str(TRACKER), "show", f"{BEFORE}:mx/skills/tracker/board.py").stdout)

    gh_stub(work / "answering", f"cat <<'JSON'\n{json.dumps(ANSWER)}\nJSON")
    gh_stub(work / "logged-out", f'printf "%s\\n" "{LOGGED_OUT}" >&2\nexit 4')

    # the same tracker three times: the board as it was, the board now, and the board now with
    # GitHub out of reach. Each render gets its own page, so each keeps its own cache.
    pages = {
        "before": render(was, tracker, work / "before.html", work / "answering"),
        "after": render(board, tracker, work / "after.html", work / "answering"),
        "unasked": render(board, tracker, work / "unasked.html", work / "logged-out"),
    }
    style = pages["after"].split("<style>", 1)[1].split("</style>", 1)[0]

    rows = {name: [summary(page, row) for row in ROWS] for name, page in pages.items()}
    for name in ("before", "after"):  # a badge per reference, in the order the notes read them
        rows[name][0] = mark(mark(rows[name][0], 1, which=0), 2, which=1)
        rows[name][1] = mark(rows[name][1], 3)
    rows["unasked"][0] = mark(rows["unasked"][0], 1)

    panels = panel(
        "before", "the board as it was until this slice", rows["before"],
        ["<code>cli/cli#1</code> — a merged pull request, in the muted ink every reference wore.",
         "<code>cli/cli#2</code> — a closed issue, in the same ink: the row could not tell them apart.",
         "<code>anthropics/claude-code#96304</code> — an open issue, likewise. Hover any of the three: "
         "<i>A pull request or issue this ticket names, on GitHub.</i> — true of all three, and the same words for each."],
    ) + panel(
        "after", "the same tracker, the same three references", rows["after"],
        ["<code>cli/cli#1</code> in the callout purple: merged. Hover it — <i>A merged pull request on GitHub.</i>",
         "<code>cli/cli#2</code> struck through: closed. Hover — <i>A closed issue on GitHub.</i>",
         "<code>anthropics/claude-code#96304</code> in the accent: open. Hover — <i>An open issue on GitHub.</i> "
         "A draft is underlined and a pull request whose review asked for changes takes the rose a question wears."],
    ) + panel(
        "after, with GitHub out of reach", "no <code>gh</code>, no auth or no network", rows["unasked"],
        ["Every reference is the muted link it was before this slice, and says the same words on hover: "
         "the board asked and was told nothing, and no row pretends otherwise.",
         "The one note at the top of the page, above every row, carries what <code>gh</code> itself said. "
         "It is said once however many links the board shows, and nothing else on the page says it."],
        absent=note(pages["unasked"], 2),
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
  /* the rows keep the width the board gives them, since below about 1100px the board
     reflows a row and the figure is about the line the links sit on */
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
  .rows { border: 1px solid var(--edge); border-radius: var(--radius); background: var(--ground-2); padding: .25rem 0; overflow-x: auto; }
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


def main() -> None:
    keep = None
    args = sys.argv[1:]
    while args:
        flag = args.pop(0)
        if flag == "--before":
            globals()["BEFORE"] = args.pop(0)
        elif flag == "--keep":
            keep = Path(args.pop(0))
        else:
            sys.exit(f"figure.py: unknown argument {flag!r}\n\n{__doc__}")
    work = keep or Path(tempfile.mkdtemp(prefix="board-gh-figure-"))
    work.mkdir(parents=True, exist_ok=True)
    try:
        (HERE / "figure.html").write_text(build(work))
        print(HERE / "figure.html")
    finally:
        if keep is None:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
