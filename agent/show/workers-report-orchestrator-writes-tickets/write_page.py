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
    "one project, two repos": (
        "A project is a code repo with its <code>agent/</code> a git repo of its own inside it, "
        "which the code repo ignores: the tickets, the show directories, the prototypes and the "
        "research are committed there. Nothing configures it: <code>tracker root</code> answers "
        "with that repo's <code>tickets</code> from anywhere in either, and <code>git status</code> "
        "in the code repo says nothing about it."
    ),
    "the claim, committed where the ticket files are": (
        "The claim is a ticket write, so it is committed in the agent repo. The two logs under it "
        "are the point: the agent repo has the claim, the code repo has only its own first commit, "
        "and no branch or merge was needed for the ticket change."
    ),
    "the spawn, and the brief the worker is given": (
        "The spawn cuts <code>ticket/warm-preset</code> in both repos and checks the agent one out "
        "inside the code worktree, where every checkout of the project keeps it. It reads no ticket "
        "on the host at all: <code>dispatch</code> reads the tracker here, where a ticket the user "
        "is in the loop for is kept back, and sends the ticket's context in the prompt. The brief "
        "at the end of the panel is the whole of what the worker has."
    ),
    "what the worker committed, and where": (
        "Code on the code repo's ticket branch; the demo and the report on the agent repo's, under "
        "the ticket's show directory. Neither branch carries a ticket file: a worker never opens "
        "one, the commit check refuses one staged on a ticket branch, and <code>dispatch review</code> "
        "refuses a branch that wrote one anyway."
    ),
    "fetch and review: the report becomes the ticket": (
        "<code>dispatch fetch</code> brings both branches back, the report among the files on the "
        "agent one. <code>dispatch review</code> reads it there and imports it through "
        "<code>tracker</code>, which is one checked write: the comment lands under "
        "<code>## Comments</code>, the question under <code>## Questions</code>, and the status "
        "goes to <code>review</code>. The notes under it are the review page's, projected out of "
        "the ticket's own copy, and the assumption anchored in the comment is what they are made of."
    ),
    "the ruling, before the merge": (
        "The question is in the ticket the moment the report is imported, so <code>tracker rule</code> "
        "answers it here, with both branches still unmerged."
    ),
    "the landing: one range per repo": (
        "The accept merges the ticket branch in each repo, and the second <code>dispatch review</code> "
        "writes <code>done</code> and the round's two ranges into the ticket: "
        "<code>code@&lt;sha&gt;..&lt;sha&gt;</code> and <code>agent@&lt;sha&gt;..&lt;sha&gt;</code>, "
        "since one round is one diff per repo and the review page renders both. The two logs at the "
        "end are the whole of what the project holds: the code, the ticket's own history, and no "
        "ticket commit on any ticket branch."
    ),
}

BOARD = (
    "The board of the agent repo, rendered by the <code>dispatch review</code> above with the build "
    "still in flight. It reads one directory, that repo's <code>tickets</code>: the worker's "
    "worktrees and both its branches are elsewhere, and nothing here goes looking for them. The row "
    "is in <b>needs me</b> because the ticket says <code>review</code> and carries an open question, "
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
        ("after", "After: one copy, written by one party. The worker commits a report in the agent "
                  "repo with its demo and its figures, and <code>dispatch review</code> imports it "
                  "into the ticket."),
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
            '<figure><img src="board.png" alt="the board of the toy project, the warm-preset row in needs me">'
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
        "files, in the agent repo a project holds at <code>agent/</code>. Below: what changed, then "
        "one ticket driven end to end over the two repos that project is. Every command was run; "
        "the output under it is what it printed.</p>"
        f"{figures(figure_dir)}"
        f"{body}{board(out)}"
        '<button class="scheme" title="day or night; ?theme=day|night on the address pins one">scheme</button>'
        f"<script>{TOGGLE}</script>"
        "</body></html>\n"
    )
    (out / "index.html").write_text(page)


if __name__ == "__main__":
    main()
