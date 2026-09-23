---
name: show
description: "Show, don't tell: build the artifact that makes a thing visible, so a reader sees what it is and what it does. A figure, a demo, a diagram, a driven run, an explainer page. Use when writing a spec's Decisions or an ADR, when closing or landing a piece of work, when an explanation is ballooning in prose, when someone has to see or learn how something works, or when another skill needs an artifact."
---

# Show

A thing is understood in front of a render: someone sees what it is and what it does, whether they are ruling on it, grilling it, reviewing it, or learning how it works. Look up the shape of the thing in the table, build what the row names, look at it yourself, put it in front of the reader.

## The table

| Shape | Figure | Demo |
| --- | --- | --- |
| A schema, a record, an API: a new entity or relation, a row, a document, a payload | ER diagram for the entities and their relations, and a sample instance of the record they hold beside it: a CSV row, a JSON line | the serialized instance the change now writes; for an API, a request and its response |
| An exchange or a flow: three or more parties, an ordering that matters, a long or interactive run | sequence diagram | the flow driven: a recording, a walkthrough the demo starts, or a tmux pane to attach to |
| A state with named transitions | state chart | none |
| A new or moved module boundary | dependency diagram | none |
| A prompt, a skill, a process change | the before and after of what an agent writes: a session driven each way, or one role-played as a stand-in where the change is not built yet | none |
| A script, a hook, a CLI | example invocations, or the interface with sample outputs | the real invocation and the output it produced, `--help` for a CLI |
| A page or a UI | before it exists, a prototype of it (`/mx:prototype`); once it does, renders of the old and the new state from the two branches, toggled or side by side, each with numbered where-to-look notes | the page opened, a screenshot per state, or a recording |
| A config or a keybinding | none | the setting or the keystroke, and what it does |

A **figure** explains through a drawing: a decision before anything exists, and a comparison the built thing cannot show on its own, above all a before and after. A **demo** is the built thing itself, running.

Which a delivered change owes follows from what it is. A change to something that was already there gets **both**: the before-and-after figure, and the demo of the new state. A new thing with no before gets the demo alone. A decision, and a change whose effect cannot be run, gets the figure alone. A change of no shape the table names gets neither, and the landing that carries it says so in one line: the diff is the demo.

Shape decides, never size: a one-column change gets no figure, a two-table schema gets its ER diagram. A thing of several shapes gets every row it hits. A cell reading none means nothing is owed there: no slot is ever padded to have something in it. Every document takes this table, an ADR included, and most ADRs hit no row.

The page row is the one whose figure can be another skill's artefact: `/mx:prototype` owns how a prototype is built and where it lives, and the decision links it the way it links a figure.

The rows are examples, not the boundary. Media craft below is the open set, and an artifact nothing here names is the right answer whenever it shows the thing better. An explanation built for learning is one more case, and a page in the distill.pub tradition, with figures the reader pokes at, is what it wants.

## Where it goes

An artifact goes to the show directory of the work it serves, committed with that work: `agent/show/<feature>/` for a feature, `agent/show/<slug>/` for a standalone ticket, `agent/show/<branch>/` for loose work. One that serves no feature, ticket or branch goes to `~/Downloads/show/<slug>/` instead: the user wants it throwaway, there is no repo to keep it in, or the repo is the wrong home for it.

## A figure

Two file shapes, chosen by how the picture is made.

- **A diagram whose layout mermaid solves**: one source file named for what it shows with its SVG beside it, `<name>.mmd` and `<name>.svg`, both committed. The SVG is what gets opened, since it scales with zoom where a raster does not. A mermaid render carries the renderer's own colour scheme, so the both-schemes rule under Produce and present does not reach it.
- **A picture whose coordinates you place yourself**: one self-contained HTML file ([`SVG-FIGURES.md`](SVG-FIGURES.md)), which draws itself in either scheme from that one source. A figure heading for a document wants this shape, since the document needs both schemes and a renderer of its own reads the file.

Either way the render is regenerated from the source whenever the decision moves, and a PNG for embedding is rendered on demand and stays untracked beside its source, which is why a figure a document in the tree embeds is promoted with the script that renders it rather than copied (Promotion, below). A page (`index.html`) holds more than one thing at once, several figures, or a diagram and the sample instance beside it, and there every image sits at `width:100%; height:auto` so it scales too.

## A demo

A demo is built to be read by someone with the product sense and none of the weeds: a founder who is technical but did not build this and wants to understand what it does, told accurately, not sold. So a demo explains as it shows. What it drives is annotated beside what happened, the commands it ran stay in view but under what they mean, a figure or a rendered page carries it where the shape allows one, and the raw transcript goes to `out/` as evidence rather than standing as the demo. A demo walks its reader through what it shows, tutorial style: where to look, what each thing on screen is, and what changed marked as changed. A wall of commands and their output is the material a demo is made from, not the demo, and the running thing with a paragraph beside it is not one either: "open the board and click two rows" leaves the reader to find the change. A run that only prints pass or fail is a test, and a test is yours to run without showing anyone.

One executable file named `demo`, taking no arguments, in the show directory of the work it demonstrates, a feature's slice taking a directory of its own: `agent/show/<feature>/NN-<slug>/demo`. A shebang and whatever language it needs; a one-off script is not a CLI, so `/mx:tyro-cli` does not bind it. The name fixes the entry point, not the contents: what it reads sits beside it in the same directory.

Running it is the whole demo. It writes what it produces, a transcript, a sample file, a screenshot, into `out/` beside itself, untracked because the next run regenerates it, and it opens what it produced when a display is there, so a worker on a headless host runs it for the files and the session on the user's machine runs it for the opening. It lets go of what it opened rather than waiting on it: a staged demo runs under `job`, and a handler that is a terminal or an editor would keep the run going until its window closed. It runs from a fresh checkout of its branch on any host where the project is installed, carrying nothing from the session that wrote it, and it says so when it fails rather than printing an empty result. The fixed name is what makes every demo findable and runnable without reading anything first: `fd -t x '^demo$' agent/show`.

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
- Look at your own render before presenting: Read the PNG, run the demo, open the page. Done means you have seen it explain the thing *and* it looks good; an ugly artifact obscures what it was meant to clarify.
- Present it opened (`claude-browser` where it exists, else `xdg-open`), with one line on what it shows and the absolute path.

## A heavy artifact goes to a fresh agent

An artifact with a build loop (a manim video, a multi-section explainer, anything needing render and debug cycles) is built by a fresh agent from a brief: the artifact, its output path, and the sources on disk to read. A fork of this session (invoke `mx:fork`) is the exception, taken when the conversation itself is the source the artifact needs and no file carries it.

## Promotion

A figure, or a demo's output, that a README or a PR description needs moves to where that document's assets live, a `docs/` or `assets/` directory the document already reads from: the render, its source, and the script that regenerates it travel together, and every reference is repointed in the same commit. No show directory outlives the work it belongs to, whatever still reads it, so a copy left behind in one is a stale figure waiting to be read as current. What the destination takes varies: a PNG the README embeds, an HTML page linked through `sftpgo-share upload`, a demo's output pasted into a PR as a code block or screenshots, a demo that asserts moved under `make check`. The move is your own call and visible in the diff, so no ruling gates it.
