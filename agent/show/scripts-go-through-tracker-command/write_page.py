#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# ///
"""Write the demo's page out of the transcript its run left: one panel per step, each with what
the step is for above the commands it ran, and the two board screenshots side by side.

    write_page.py <out dir> <transcript>

Called by `demo`, which is the thing to run.
"""

import html
import sys
from pathlib import Path

# What each step of the transcript shows, in the transcript's own order. The key is the step's
# heading as `demo` prints it; the words are what the reader is looking at and where to look.
SAYS = {
    "the tracker, in the one shape every script reads": (
        "The toy tracker is four ticket files, flat, each named by its slug: a parent ticket "
        "<code>lamp-ui</code>, two child tickets that name it as their <code>parent</code>, and one "
        "ticket in no tree. <code>tracker check</code> is what every other script below reads "
        "through; it says nothing here because every file passes. <code>tracker frontier</code> "
        "reads the same files and answers what can be started now."
    ),
    "property-coverage, over the tracker rather than a feature directory": (
        "A property is stated once, on the ticket it holds for, and a criterion anywhere in the "
        "tree takes it on by citing it. <code>property-coverage</code> asks the one question that "
        "leaves: which property no criterion cites. The second run takes the citing criterion out, "
        "and the finding points at the line the property is stated on."
    ),
    "the context a worker is briefed with, and a reviewer judges against": (
        "One assembly, <code>tracker context</code>: the ticket's own body first, then every "
        "ancestor's. This is what the spawn below sends a worker and what <code>review --spec "
        "&lt;slug&gt;</code> hands a reviewer, so the two cannot drift."
    ),
    "dispatch: the claim, through tracker's own transitions": (
        "<code>dispatch claim</code> no longer reads the status with an <code>awk</code> of its "
        "own: it calls <code>tracker set</code>, which is where the transitions live. The second "
        "claim is refused by the rule that forbids it, named in the refusal."
    ),
    "dispatch: a ticket the user is in the loop for is never handed to a worker": (
        "Where <code>spawn</code> refused a <code>type:</code> before, it reads "
        "<code>needs-user</code> off the ticket as it stands on the base branch, through the same "
        "parser, and refuses to hand it to a worker."
    ),
    "dispatch: the spawn, and the brief it sends": (
        "The spawn stages the host, which is where <code>dispatch-ctl init</code> installs the "
        "tracker's commit check; a local orchestrator passes its own checkout and the line says "
        "the hook stays theirs to install. The brief the worker receives is printed at the end of "
        "the panel: the orchestrator's own message, then the ticket's context under it."
    ),
    "dispatch review, before the merge: the flip, the notes, the page": (
        "The ticket branch is <code>ticket/warm-preset</code>, cut from the branch dispatch runs "
        "on. Before the merge the landing writes <code>status: review</code> and renders the page; "
        "the notes it projects for that page come from <code>tracker data</code>, so the "
        "assumption bullet its writer wrapped over two lines arrives whole rather than cut at the "
        "first line."
    ),
    "the ruling: the merge, and the landing": (
        "After the merge the same command writes <code>status: done</code> and appends the round's "
        "commit range to <code>diff:</code>, both in one <code>tracker set</code>, which refuses a "
        "landing the transitions do not allow."
    ),
    "review --spec, given a slug rather than a path": (
        "<code>--spec</code> takes a ticket's slug and writes the assembly above into the report "
        "directory as <code>ticket.md</code>, which is the file the reviewers read. A path still "
        "means the file it names."
    ),
    "the board, before and after": (
        "Two renders of the same tracker: the board from the commit this branch cut from, over the "
        "tracker in the shape that commit reads, and the board from this branch over the tracker "
        "in the shape every script now reads, one under the other below."
    ),
}

LOOK = [
    ("The tree, where the feature was", "The left column names the parent ticket a row is part of, "
     "and the pill in the top bar hides and shows that tree. A ticket with no parent ticket and no "
     "child tickets is in no tree: its column is empty and its pill says <code>alone</code>."),
    ("The slug, where the number was", "The second column is the ticket's own slug, which is the "
     "row's id, the anchor a graph node clicks to, and what agents say to the user. A click still "
     "copies the path of the file the row was read from."),
    ("What a row asks", "Four words where there were seven: to rule on, your answer, with you, "
     "build. The three that came from a decision ticket's <code>type</code> are gone, and "
     "<code>with you</code> is what a ticket carrying <code>needs-user</code> asks."),
    ("The parent ticket is a row", "<code>lamp-ui</code> was a <code>spec.md</code> with a status "
     "chip on the pill; it is a ticket now, with a row, a brief, a priority and a size of its own."),
]

STYLE = """
  :root { color-scheme: light dark;
    --ground: light-dark(#f4ece1, #14120f); --ground-2: light-dark(#ece1d2, #1d1a16);
    --ink: light-dark(#2f2a24, #e8e0d4); --muted: light-dark(#6d6256, #9a8f80);
    --edge: light-dark(#d8cab5, #332e27); --accent: light-dark(#426724, #9bbf6a); }
  * { box-sizing: border-box; }
  body { margin: 0 auto; max-width: 62rem; padding: 2.5rem 1.5rem 5rem;
    background: var(--ground); color: var(--ink);
    font: 16px/1.6 ui-serif, Georgia, "Liberation Serif", "DejaVu Serif", "Times New Roman", serif; }
  h1 { font-size: 1.6rem; margin: 0 0 .4rem; font-weight: 600; }
  h2 { font-size: 1.1rem; margin: 2.6rem 0 .5rem; font-weight: 600; }
  p.sub { color: var(--muted); margin: 0 0 2rem; }
  p { margin: 0 0 .9rem; }
  code, pre { font-family: ui-monospace, "SFMono-Regular", Menlo, monospace; font-size: .82rem; }
  code { background: var(--ground-2); padding: .05rem .25rem; border-radius: .2rem; }
  pre { background: var(--ground-2); border: 1px solid var(--edge); border-radius: .4rem;
    padding: .8rem 1rem; overflow-x: auto; line-height: 1.45; margin: 0; }
  .panel { margin: 0 0 1.4rem; }
  figure { margin: 1.2rem 0 0; }
  figure img { width: 100%; height: auto; border: 1px solid var(--edge); border-radius: .4rem; }
  figcaption { color: var(--muted); font-size: .9rem; margin-top: .4rem; }
  ol.look { padding-left: 1.2rem; }
  ol.look li { margin-bottom: .5rem; }
  .boards { display: grid; gap: 1.8rem; }
"""


def steps(transcript: str) -> list[tuple[str, str]]:
    """(heading, what the step printed) for each `== ` step of the transcript, in order."""
    found, heading, lines = [], None, []
    for line in transcript.splitlines():
        if line.startswith("== "):
            if heading:
                found.append((heading, "\n".join(lines).strip("\n")))
            heading, lines = line[3:].strip(), []
        elif heading is not None:
            lines.append(line)
    if heading:
        found.append((heading, "\n".join(lines).strip("\n")))
    return found


def panel(heading: str, said: str) -> str:
    words = SAYS.get(heading, "")
    return (f'<section class="panel"><h2>{html.escape(heading)}</h2>'
            + (f"<p>{words}</p>" if words else "")
            + (f"<pre>{html.escape(said)}</pre>" if said.strip() else "")
            + "</section>")


def boards(out: Path) -> str:
    if not (out / "board-before.png").exists() or not (out / "board-after.png").exists():
        return "<p>One of the two boards did not render; the transcript above says which.</p>"
    looking = "".join(f"<li><b>{head}</b> {words}</li>" for head, words in LOOK)
    return (
        '<div class="boards">'
        '<figure><img src="board-before.png" alt="the board, before">'
        "<figcaption>Before: the board of the commit this branch cut from, over a feature directory "
        "with a <code>spec.md</code> and <code>NN-</code> tickets.</figcaption></figure>"
        '<figure><img src="board-after.png" alt="the board, after">'
        "<figcaption>After: the board of this branch, over the same work as flat ticket files."
        "</figcaption></figure></div>"
        f'<ol class="look">{looking}</ol>'
    )


def main() -> None:
    out, transcript = Path(sys.argv[1]), Path(sys.argv[2])
    body = "".join(panel(heading, said) for heading, said in steps(transcript.read_text()))
    page = (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Every script through the tracker command</title>"
        f"<style>{STYLE}</style></head><body>"
        "<h1>Every script through the tracker command</h1>"
        '<p class="sub">One tracker of ticket files, driven through the scripts that read and write '
        "one: the board, dispatch, property-coverage and the code review's brief. Every command "
        "below was run; the output under it is what it printed.</p>"
        f"{body}{boards(out)}"
        "</body></html>\n"
    )
    (out / "index.html").write_text(page)


if __name__ == "__main__":
    main()
