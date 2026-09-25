---
name: show
description: "Show, don't tell: build the artifact that makes a thing visible, so a reader sees what it is and what it does: a figure, a diagram, a demo, an explainer page. Use when writing a ticket's Decisions or an ADR, when work lands for the user's ruling, when an explanation is ballooning in prose, when someone asks for a demo or has to see or learn how something works, or when another skill needs an artifact."
---

# Show

A thing is understood in front of a render: someone sees what it is and what it does, whether they are ruling on it, grilling it, reviewing it, or learning how it works. Pick the cells of the grid the reader's question needs, build what the table names for the thing's shape, look at it yourself, put it in front of the reader.

## What a reader can be shown

It sits on two axes. The **level** is what they look at: the **concept** (how it fits and why, drawn), the **code** (what is written: code, config, a prompt, a skill's prose) or the **output** (what it produces: a printout, a record, a render, what an agent answers). The **form** is the thing as it is, or how it changed.

| | as it is | how it changed |
| --- | --- | --- |
| concept | concept figure | concept diff |
| code | code listing | code diff |
| output | output | output diff |
| prose | abstract prose, narrated example | |

The line that matters is **narrated against real**: an example written from the head is a narrated example, one made by running the thing is output, and a narrated example says it is one.

The reader's question picks the level: how does it fit, what did you write, what will I see. Whether something moved picks the form: a thing that existed and changed gets the diff form, a new thing the as-is form, and a decision nothing has built yet the concept level alone. Cells combine whenever each adds what the others do not; a clean output diff, the same scenario on the old and the new, is usually the one that shows most.

A **demo**, in the user's words, is a show made of the built thing's own output, walked through: the rendered page, the running tool, an annotated tutorial of either.

## What each level looks like, per shape

The code level is the same for every shape, the diff on the review page, so a show quotes code only for an interface (what an agent or the user types) or the snippet a concept needs.

| Shape | Concept | Output |
| --- | --- | --- |
| A schema, a record, an API: a new entity or relation, a row, a document, a payload | ER diagram for the entities and their relations | a record the code writes, a CSV row or a JSON line; for an API, a request and its response |
| An exchange or a flow: three or more parties, an ordering that matters, a long or interactive run | sequence diagram | the flow run: a recording, or a tmux pane to attach to |
| A state with named transitions | state chart | |
| A new or moved module boundary | dependency diagram | |
| A prompt, a skill, a process change | sequence or dependency diagram, when the workflow moved | a role-played exchange: what the agent answered before, what it answers now, marked as role-play; a real session is output nobody reads, and most often the diff is all such a change needs |
| A script, a hook, a CLI | the modules it reads and writes, when that moved | what an agent or the user types, and what it produced |
| A page or a UI | | the page rendered: screenshots, the page itself, or both; before the page exists, a prototype's render (`/mx:prototype`) |
| A config or a keybinding | | the setting or the keystroke, and what it does |

Shape decides, never size: a one-column change gets no ER diagram, a two-table schema gets one. A thing of several shapes gets every row it hits. An empty cell means nothing is owed there, and no cell is padded to have something in it. At a landing the table says what a show would hold, and the diff decides whether one is owed: where the review page's diff already shows all there is to see, it is the whole of it. Every document takes this table, an ADR included, and most ADRs hit no row.

The rows are examples, not the boundary. Media craft below is the open set, and an artifact nothing here names is the right answer whenever it shows the thing better. An explanation built for learning is one more case, and a page in the distill.pub tradition, with figures the reader pokes at, is what it wants.

## A landing's show

Work that lands for the user's ruling comes with its review page and, when it holds something the diff does not make visible, one show. It is for the user's understanding of what was built. Demonstrating that the tests are green or that it runs is not the show's job: the tests and the review already did that, and a build that does not run has no show to be made of it. Its reader has the product sense and none of the weeds: technical, did not build it, and wants to understand it, told accurately and never sold.

- **One per landing.** A tree's show covers every child ticket in review the user has not ruled on yet, and goes to the parent ticket's directory; a tick that brings another to review rebuilds it rather than adding a second, so it is whole when the user sits down to rule. A standalone ticket's goes to its own.
- **Built by a fork** of the session landing the work (invoke `mx:fork`): it holds the conversation the user's questions came from, and its build loop stays out of that session's window.
- **The few things the user would notice.** Each gets a caption of a sentence or two, the cells the grid picks, and numbered notes on where to look. The commands a run made sit folded under what they produced.

## Where it goes

An artifact goes to the show directory of the work it serves, committed with that work: `agent/show/<slug>/` for a ticket, `agent/show/<branch>/` for loose work. That directory is the agent repo's, so `git -C agent` is what commits it, and a landing's show is committed in its main checkout, as a ticket file is. One that serves no ticket or branch goes to `~/Downloads/show/<slug>/` instead: the user wants it throwaway, there is no repo to keep it in, or the repo is the wrong home for it.

## A figure

A concept figure or a concept diff is drawn, in one of two file shapes chosen by how the picture is made.

- **A diagram whose layout mermaid solves**: one source file named for what it shows with its SVG beside it, `<name>.mmd` and `<name>.svg`, both committed. The SVG is what gets opened, since it scales with zoom where a raster does not. A mermaid render carries the renderer's own colour scheme, so the both-schemes rule under Produce and present does not reach it.
- **A picture whose coordinates you place yourself**: one self-contained HTML file ([`SVG-FIGURES.md`](SVG-FIGURES.md)), which draws itself in either scheme from that one source. A figure heading for a document wants this shape, since the document needs both schemes and a renderer of its own reads the file.

Either way the render is regenerated from the source whenever the decision moves, and a PNG for embedding is rendered on demand and stays untracked beside its source, which is why a figure a document in the tree embeds is promoted with the script that renders it rather than copied (Promotion, below). A page (`index.html`) holds more than one thing at once, several figures, or a diagram and the sample instance beside it, and there every image sits at `width:100%; height:auto` so it scales too.

## A runnable artifact

What runs in a show directory (a walkthrough that drives the tool, a script that renders a sample) is an executable file taking no arguments, with a shebang and whatever language it needs; a one-off script is not a CLI, so `/mx:tyro-cli` does not bind it. It writes what it produces into `out/` beside itself, untracked because the next run regenerates it; it opens what it produced when a display is there and lets go of it rather than waiting on it; it runs from a fresh checkout on any host where the project is installed, and says so when it fails rather than printing an empty result.

## Register

Every artifact, in every medium, reads like a good README: it states, it never sells. A title, if there is one, names what is shown; a subtitle, if there is one, is one factual sentence. Every line of chrome and every aside carries a fact; a line that carries none is deleted. No slogans, no taglines, no coined phrases, no pitch-deck cadence; no display serif, no italics as decoration, no type chosen to look distinctive. This is the direction, not a starting point to improve on: the pull toward a punchier title or a more striking look is the failure mode, and it gets rewritten to plain on sight. Where `dataviz` taste disagrees with this, this wins.

## Media craft

How a row's medium gets made. An open set, not a menu; combining media is normal, and anything that carries the thing qualifies:

- **Diagram**: mermaid (invoke `mx:mermaid` first) when layout should be solved for you; hand-placed SVG (read `SVG-FIGURES.md`) when the figure is the artifact and deserves the control. Either way the classic families apply: UML, flowcharts, sequence and state charts, Nassi-Shneiderman, and the rest.
- **Comparison**: show a difference instead of describing it: a code diff (`diffview`), a table, two rendered variants side by side.
- **Runnable code**: the smallest script that exhibits the behavior; run it and show the output. When the question grows into "does this design/state model feel right?", that's `/mx:prototype`.
- **HTML/JS page**, the most flexible medium: interactive figures, animations, side-by-side panels, up to a full explainer in the distill.pub tradition (prose interleaved with figures the reader can poke at). Read `PAGES.md`.
- **LaTeX/TikZ**: publication-grade figures. TeX Live is fully installed: just compile, `pdftoppm` to PNG to inspect.
- **Animation**: a process unfolding over time. Interactive JS (the reader steps and scrubs) usually beats a linear video; manim is the option for math-heavy scenes when video is the right form.

## Produce and present

- Facts in an artifact come from primary sources (the config, the code, the live system), never only from prose docs about them. Docs drift, and the artifact inherits the drift; a figure states things with more authority than the README it was cribbed from.
- Anything opened in a browser wears the house style (`/mx:house-style`: tokens, type, parts, and the scheme toggle) unless the artifact has a reason to look otherwise, and ships both color schemes; the reader's system setting is the default, not a constraint. Look at both before presenting.
- Look at your own render before presenting: Read the PNG, run what runs, open the page. Done means you have seen it explain the thing *and* it looks good; an ugly artifact obscures what it was meant to clarify.
- Present it opened (`claude-browser` where it exists, else `xdg-open`), with one line on what it shows and the absolute path.

## A heavy artifact goes to a fresh agent

An artifact with a build loop (a manim video, a multi-section explainer, anything needing render and debug cycles) is built by a fresh agent from a brief: the artifact, its output path, and the sources on disk to read. A fork of this session (invoke `mx:fork`) is the exception, taken when the conversation itself is the source the artifact needs and no file carries it.

## Promotion

A figure, or an output, that a README or a PR description needs moves to where that document's assets live, a `docs/` or `assets/` directory the document already reads from: the render, its source, and the script that regenerates it travel together, and every reference is repointed in the same commit. No show directory outlives the work it belongs to, whatever still reads it, so a copy left behind in one is a stale figure waiting to be read as current. What the destination takes varies: a PNG the README embeds, an HTML page linked through `sftpgo-share upload`, an output pasted into a PR as a code block or screenshots, a script that asserts moved under `make check`. The move is your own call and visible in the diff, so no ruling gates it.
