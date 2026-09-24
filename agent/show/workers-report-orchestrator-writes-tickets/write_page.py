#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# ///
"""Write the demo's page out of the transcript its run left: the before and after figures, then
one panel per step, each with what the step is for above the commands it ran.

    write_page.py <out dir> <transcript> <figure dir>

Called by `demo`, which is the thing to run.
"""

import html
import sys
from pathlib import Path

# What each step of the transcript shows, in the transcript's own order. The key is the step's
# heading as `demo` prints it; the words are what the reader is looking at and where to look.
SAYS = {
    "two repos, and the one setting that joins them": (
        "<code>plans</code> holds the tickets and <code>lamp</code> holds the code, and nothing in "
        "either repo says so: the join is <code>git config mx.tracker</code> in the code repo's "
        "clone, machine-local like the path it holds. From there every read and write of a ticket "
        "in <code>lamp</code> lands in <code>plans</code>, which is what <code>tracker root</code> "
        "answers and what <code>tracker frontier</code> has read."
    ),
    "the claim, committed where the ticket files are": (
        "The claim is a ticket write, so it is committed in the tracker's checkout. The two logs "
        "under it are the point: <code>plans</code> has the claim, <code>lamp</code> has only its "
        "own first commit, and no branch or merge was needed for the ticket change."
    ),
    "the spawn, and the brief the worker is given": (
        "The spawn reads no ticket on the worker host at all: <code>dispatch</code> reads the "
        "tracker here, where a ticket the user is in the loop for is kept back, and sends the "
        "ticket's context in the prompt. The brief at the end of the panel is the whole of what "
        "the worker has: the orchestrator's own message, then the ticket's body and its parent's."
    ),
    "what the worker left behind": (
        "Two things. The report, written to the file the runner named it, beside the worklog and "
        "outside the worktree: the closing comment under <code>## Comments</code>, the question "
        "its build raised under <code>## Questions</code>, in the shapes the ticket gives both. "
        "And the branch, which carries the code and the demo file and nothing of the tracker: the "
        "worker never opened a ticket file."
    ),
    "fetch and review: the report becomes the ticket": (
        "<code>dispatch fetch</code> brings the branch and the report back together. "
        "<code>dispatch review</code> imports the report through <code>tracker</code>, which is "
        "one checked write: the comment lands under <code>## Comments</code>, the question under "
        "<code>## Questions</code>, and the status goes to <code>review</code>. The notes under "
        "it are the review page's, projected out of the ticket's own copy rather than read off "
        "the branch, and the assumption anchored in the comment is what they are made of."
    ),
    "the ruling, before the merge": (
        "The question is in the tracker's copy the moment the report is imported, so "
        "<code>tracker rule</code> answers it here, with the build still unmerged. The rule that "
        "a build's questions waited for the merge is gone with the second copy that made it."
    ),
    "the landing: a range that names the repo it is in": (
        "The accept merges the branch in <code>lamp</code> and the second "
        "<code>dispatch review</code> writes <code>done</code> and the range into the ticket in "
        "<code>plans</code>. The range carries the repo it is in, <code>lamp@&lt;sha&gt;..&lt;sha&gt;"
        "</code>, since nothing else on the ticket says which repo to render it from; in a tracker "
        "that plans its own repo it stays a bare range. The log at the end is <code>lamp</code>'s "
        "whole history: the code, and no ticket commit anywhere in it."
    ),
}

BOARD = (
    "The board of <code>plans</code>, rendered by the <code>dispatch review</code> above with the "
    "build still in flight. It reads one directory, the tracker's own: the worker's worktree and "
    "its branch are in the other repo, and nothing here goes looking for them. The row is in "
    "<b>needs me</b> because the ticket says <code>review</code> and carries an open question, "
    "both of which the import put there."
)

# The house tokens, copied from mx/skills/house-style/tokens.css: the colours, the muted/strong
# split and the roles are what make it the house, so they stay as that file has them.
STYLE = """
  :root {
    color-scheme: light dark;
    --ground: light-dark(#f4e4cd, #1a1714);
    --ground-2: light-dark(#eddabe, #201c18);
    --edge: light-dark(#cfbca3, #4a433b);
    --muted: light-dark(#5e5650, #b0a89e);
    --body: light-dark(#37261d, #ede3d2);
    --strong: light-dark(#22140b, #faf2dc);
    --accent: light-dark(#426724, #6ea444);
    --radius: 6px;
  }
  [data-theme="day"] { color-scheme: light; }
  [data-theme="night"] { color-scheme: dark; }

  * { box-sizing: border-box; }
  body { margin: 0 auto; max-width: 62rem; padding: 2.5rem 1.5rem 5rem;
    background: var(--ground); color: var(--body);
    font: 19px/1.62 Georgia, "Liberation Serif", "DejaVu Serif", ui-serif, serif; }
  h1, h2 { color: var(--strong); font-weight: 600; }
  h1 { font-size: 1.6rem; margin: 0 0 .4rem; }
  h2 { font-size: 1.1rem; margin: 2.6rem 0 .5rem; }
  p.sub { color: var(--muted); margin: 0 0 2rem; }
  p { margin: 0 0 .9rem; }
  code, pre { font-family: ui-monospace, "SFMono-Regular", Menlo, monospace; font-size: .78rem; }
  code { background: var(--ground-2); padding: .05rem .25rem; border-radius: var(--radius); }
  pre { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius);
    padding: .8rem 1rem; overflow-x: auto; line-height: 1.5; margin: 0; }
  .panel { margin: 0 0 1.4rem; }
  figure { margin: 1.2rem 0 0; }
  figure img { width: 100%; height: auto; background: #fff; border: 1px solid var(--edge);
    border-radius: var(--radius); }
  figcaption { color: var(--muted); font-size: .9rem; margin-top: .4rem; }
  .scheme { position: fixed; top: 1rem; right: 1rem; border: 1px solid var(--edge);
    border-radius: 999px; background: var(--ground-2); color: var(--muted); cursor: pointer;
    font: inherit; font-size: .8rem; padding: .1rem .7rem; }
  .scheme:hover { color: var(--accent); border-color: var(--accent); }
"""

# The scheme is the system's; `?theme=day|night` pins one, which is what a screenshot needs, and the
# button pins one by hand (`/mx:house-style`). The two figures are mermaid renders and carry the
# renderer's own colours, so they sit on white in either scheme.
TOGGLE = """
  const root = document.documentElement;
  const asked = new URLSearchParams(location.search).get("theme");
  if (asked === "day" || asked === "night") root.dataset.theme = asked;
  document.querySelector(".scheme").addEventListener("click", () => {
    const now = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "night" : "day");
    root.dataset.theme = now === "day" ? "night" : "day";
    document.querySelector(".scheme").textContent = root.dataset.theme;
  });
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
    return (f'<section class="panel"><h2>{html.escape(heading)}</h2>'
            + f"<p>{SAYS[heading]}</p>"
            + (f"<pre>{html.escape(said)}</pre>" if said.strip() else "")
            + "</section>")


def figures(figure_dir: Path) -> str:
    """The before and after of who writes a ticket file, as the two sequence diagrams beside the
    demo. Inlined, so the page opens as one file from anywhere."""
    drawn = []
    for name, caption in (
        ("before", "Before: two copies of one ticket file. The worker writes its questions, its "
                   "closing comment and the <code>review</code> flip on its own branch, and they "
                   "reach the tracker's copy only at the merge."),
        ("after", "After: one copy, written by one party. The worker writes a report outside its "
                  "worktree, and <code>dispatch review</code> imports it into the ticket."),
    ):
        source = figure_dir / f"{name}.svg"
        if not source.exists():
            continue
        drawn.append(f'<figure>{source.read_text().split("?>", 1)[-1]}'
                     f"<figcaption>{caption}</figcaption></figure>")
    return "".join(drawn)


def board(out: Path) -> str:
    if not (out / "board.png").exists():
        return "<p>The board did not render; the transcript above says what happened.</p>"
    return (f'<section class="panel"><h2>the board, with the build in flight</h2><p>{BOARD}</p>'
            '<figure><img src="board.png" alt="the board of the plans repo, the warm-preset row in needs me">'
            "</figure></section>")


def main() -> None:
    out, transcript, figure_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    written = steps(transcript.read_text())
    ran = [heading for heading, _ in written]
    assert set(ran) == set(SAYS), (
        "the steps and the words about them have drifted apart: "
        f"{sorted(set(ran) - set(SAYS))} ran with nothing to say, {sorted(set(SAYS) - set(ran))} said of no step"
    )
    body = "".join(panel(heading, said) for heading, said in written)
    page = (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>The worker reports, the orchestrator writes the ticket</title>"
        f"<style>{STYLE}</style></head><body>"
        "<h1>The worker reports, the orchestrator writes the ticket</h1>"
        '<p class="sub">A worker writes code and a report; the orchestrator alone writes ticket '
        "files, in the tracker's own checkout. Below: what changed, then one ticket driven end to "
        "end with the tickets in one repo and the code in another. Every command was run; the "
        "output under it is what it printed.</p>"
        f"{figures(figure_dir)}"
        f"{body}{board(out)}"
        '<button class="scheme" title="day or night; ?theme=day|night on the address pins one">scheme</button>'
        f"<script>{TOGGLE}</script>"
        "</body></html>\n"
    )
    (out / "index.html").write_text(page)


if __name__ == "__main__":
    main()
