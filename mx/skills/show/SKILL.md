---
name: show
description: "Show, don't tell: the medium a thing is judged in, chosen by its shape. Use when writing a spec's Decisions or an ADR, when closing or landing a piece of work, when an explanation is ballooning in prose, when the user asks to see a thing rather than read about it, or when another skill needs an artifact."
---

# Show

A thing is judged in front of a render. The table decides the medium from the shape of what is to be judged: a **figure** for a decision being stated, a **demo** for a change that has landed, either for an explanation prose has stopped carrying. Look up the shape, build what the row names, look at it yourself, put it in front of the user.

## The table

| Shape | Figure, for a decision being stated | Demo, for a change that landed |
| --- | --- | --- |
| A schema, a record, an API: a new entity or relation, a row, a document, a payload | ER diagram; a record shape gets a sample instance beside it, a CSV row or a JSON line | the serialized instance the change now writes; for an API, a request and its response |
| An exchange or a flow: three or more parties, an ordering that matters, a long or interactive run | sequence diagram | the flow driven: a recording, a walkthrough the demo starts, or a tmux pane to attach to |
| A state with named transitions | state chart | none |
| A new or moved module boundary | dependency diagram | none |
| A prompt, a skill, a process change | none | a driven session transcript, before and after where the difference is the point |
| A script, a hook, a CLI | none | the invocation and the output it produced, `--help` for a CLI |
| A page or a UI | none | the page opened, or a screenshot per state |
| A config or a keybinding | none | the setting or the keystroke, and what it does |

Shape decides, never size: a one-column change gets no figure, a two-table schema gets its ER diagram. A thing of several shapes gets every row it hits. A cell reading none, and a shape with no row at all, are answers: nothing is built, and no slot is ever padded to have something in it. Every document takes this table, an ADR included, and most ADRs hit no row.

A **before/after** is the shape that crosses the rows: a decision or a change that moves something already there is shown as the two side by side, whatever else its row gives it.

Mermaid renders a figure by default, validated per `/mx:mermaid`. The craft below overrides that default wherever a better medium beats it.

## Where it goes

An artifact goes to the show directory of the work it serves, committed with that work: `agent/show/<feature>/` for a feature, `agent/show/<slug>/` for a standalone ticket, `agent/show/<branch>/` for loose work. One that serves no feature, ticket or branch goes to `~/Downloads/show/<slug>/` instead: the user wants it throwaway, there is no repo to keep it in, or the repo is the wrong home for it.

## A figure

One source file named for what it shows, with its SVG beside it: `<name>.mmd` and `<name>.svg`. Both are committed, and the render is regenerated from the source whenever the decision moves. The SVG is what gets opened, since it scales with zoom where a raster does not; a PNG is rendered on demand for embedding somewhere that needs one and stays untracked. A mermaid render carries the renderer's own colour scheme, and the both-schemes rule under Produce and present binds a page you author, not a renderer's output. A page (`index.html`) is for more than one thing at once, several figures, or a diagram and the sample instance beside it, and there every image sits at `width:100%; height:auto` so it scales too.

## A demo

One executable file named `demo`, taking no arguments, in the show directory of the work it demonstrates, a feature's slice taking a directory of its own: `agent/show/<feature>/NN-<slug>/demo`. A shebang and whatever language it needs; a one-off script is not a CLI, so `/mx:tyro-cli` does not bind it.

Running it is the whole demo. It writes what it produces, a transcript, a sample file, a screenshot, into `out/` beside itself, untracked because the next run regenerates it, and it opens what it produced when a display is there, so a worker on a headless host runs it for the files and the session on the user's machine runs it for the opening. It runs from a fresh checkout of its branch on any host where the project is installed, carrying nothing from the session that wrote it, and it says so when it fails rather than printing an empty result. The fixed name is what makes every demo findable and runnable without reading anything first: `fd -t x '^demo$' agent/show`.

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
- Anything opened in a browser ships both color schemes and a visible control to switch between them; the reader's system setting is the default, not a constraint. Look at both before presenting. `SVG-FIGURES.md` has the token and toggle mechanics.
- Look at your own render before presenting: Read the PNG, run the demo, open the page. Done means you have seen it explain the thing *and* it looks good; an ugly artifact obscures what it was meant to clarify.
- Present it opened (`claude-browser` where it exists, else `xdg-open`), with one line on what it shows and the absolute path.

## A heavy artifact goes to a fresh agent

An artifact with a build loop (a manim video, a multi-section explainer, anything needing render and debug cycles) is built by a fresh agent from a brief: the artifact, its output path, and the sources on disk to read. A fork of this session (invoke `mx:fork`) is the exception, taken when the conversation itself is the source the artifact needs and no file carries it.

## Promotion

A figure, or a demo's output, that a README or a PR description needs is copied there on your own judgment, in the same commit, and kept current where it lands: a PNG in the README, an HTML page linked through `sftpgo-share upload`, a demo's output pasted into the PR as a code block or screenshots, a demo that asserts moved under `make check`. The copy is visible in the diff, so no ruling gates it.
