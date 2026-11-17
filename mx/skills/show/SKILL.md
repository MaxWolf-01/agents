---
name: show
description: "Show, don't tell: the artifacts that make a thing visible, so a reader sees what it is and what it does: a figure, a diagram, a demo, an explainer page. Use when writing a ticket's Decisions or an ADR, when work lands for the user's ruling, when someone asks for a demo or has to see or learn how something works, or when another skill needs an artifact."
---

# Show

A thing is understood in front of a render: the reader sees what it is and what it does, whether ruling on it, grilling it, reviewing it or learning how it works.

## What a reader can be shown

It sits on two axes. The **level** is what they look at: the **concept** (how it fits and why, drawn), the **code** (what is written: code, config, a prompt, a skill's prose) or the **output** (what it produces: a printout, a record, a render, what an agent answers). The **form** is the thing as it is, or how it changed.

| | as it is | how it changed |
| --- | --- | --- |
| concept | concept figure | concept diff |
| code | code listing | code diff |
| output | output | output diff |
| prose | abstract prose, narrated example | |

The line that matters is **narrated against real**: an example written from the head is a narrated example, one made by running the thing is output, and a narrated example says it is one.

The reader's question picks the level: how does it fit, what did you write, what will I see. Whether something moved picks the form: a changed thing gets the diff form, a new thing the as-is form, and a decision nothing has built yet the concept level alone. Combine cells wherever each adds what the others do not; a clean output diff, the same scenario on the old and the new, usually shows most. A change to something the user looks at (a page, a view, a command's output) is shown as that thing, opened, rendered or run, before and after where it existed; a change to how things fit (the architecture, a flow, an interface) is drawn at the concept level. The code diff sits beside either, and stands alone only where it makes the change plain at a glance (a typo, a rename).

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
| A page or a UI | | the page itself, running; screenshots beside it as the record; before the page exists, a prototype's render (`/mx:prototype`) |
| A config or a keybinding | | the setting or the keystroke, and what it does |

Shape decides, never size: a one-column change gets no ER diagram, a two-table schema gets one. A thing of several shapes gets every row it hits. An empty cell owes nothing and is never padded. Every document takes this table, an ADR included, though most ADRs hit no row.

The rows are examples, not the boundary: Media craft below is the open set, and an artifact nothing here names is right whenever it shows the thing better. An explanation built for learning wants a page in the distill.pub tradition, with figures the reader pokes at. For a process of several parts, its figure can grow as the reader goes: each step redraws the last with one part added and in focus, the whole figure comes at the end, and a toggle shows every step at once (`docs/figures/story/` in the agents repo is a first, rough instance).

## A figure

A concept figure or a concept diff takes one of two file shapes, chosen by how the picture is made.

- **A diagram whose layout Pele solves**: one Mermaid source named for what it shows with its SVG beside it, `<name>.mmd` and `<name>.svg`, both committed. Open the SVG: it scales with zoom where a raster does not. A Pele render opened on its own draws in Pele's default colours, so the both-schemes rule under Produce and present does not reach it.
- **A picture whose coordinates you place yourself**: one self-contained HTML file ([`SVG-FIGURES.md`](SVG-FIGURES.md)), which draws itself in either scheme from that one source. A figure heading for a document wants this shape, since the document needs both schemes and a renderer of its own reads the file.

Either way the render is regenerated from the source whenever the decision moves, and a PNG for embedding is rendered on demand and stays untracked beside its source. A page (`index.html`) holds several things at once (several figures, or a diagram beside its sample instance), and every image on it sits at `width:100%; height:auto` so it scales too.

## A runnable artifact

What a show runs (a walkthrough that drives the tool, a script that renders a sample) is an executable file with a shebang, in whatever language it needs, taking no arguments; it is not a CLI, so `/mx:tyro-cli` does not bind it. It writes its output into an untracked `out/` beside itself, opens that output without waiting on it when a display is there, runs from a fresh checkout on any host where the project is installed, and says so when it fails rather than printing an empty result.

## Register

Every artifact, in every medium, reads like a good README: it states, it never sells. A title, if any, names what is shown; a subtitle, if any, is one factual sentence. Every line of chrome and every aside carries a fact or is deleted. No slogans, no taglines, no coined phrases, no pitch-deck cadence; no display serif, no italics as decoration, no type chosen to look distinctive. This is the direction, not a starting point to improve on: a punchier title or a more striking look is the failure mode, rewritten to plain on sight. Where `dataviz` taste disagrees, this wins.

## Media craft

- **Diagram**: a structure or a flow, drawn. Mermaid, drawn by [Pele](https://github.com/obsidianmd/pele) ([`mermaid/SKILL.md`](mermaid/SKILL.md)), when the layout should be solved for you; a hand-placed SVG ([`SVG-FIGURES.md`](SVG-FIGURES.md)) when the figure is the artifact and deserves the control.
- **State diagram**: each state is labelled as the reader sees it ("Waiting for a free slot") and each arrow as what happens ("the worker's turn ends"); code names (`slot_wait`, `exit 3`) stay in the code.
- **Struktogramm**: a procedure as nested boxes with no arrows (Nassi-Shneiderman), when its loops and branches are what the reader has to see ([`struktogramm/SKILL.md`](struktogramm/SKILL.md)).
- **Comparison**: a difference shown instead of described: a code diff (`diffview`), a table, two rendered variants side by side, or a blind test (`blind-test`, `/mx:grilling`) when the reader is to choose between them by taste.
- **Runnable code**: a behaviour, exhibited by the smallest script that shows it and its output (A runnable artifact, above). A design or a state model to be felt is `/mx:prototype`.
- **HTML/JS page**: the most flexible medium, for interactive figures, animations, side-by-side panels and whole explainers ([`PAGES.md`](PAGES.md)).
- **Animation**: a process unfolding over time. Interactive JS the reader steps and scrubs usually beats a linear video; manim is for math-heavy scenes.

## Produce and present

- Facts in an artifact come from primary sources (the config, the code, the live system), never from prose docs alone: a figure repeats a doc's drift with more authority than the doc had.
- Anything opened in a browser wears the house style (`/mx:house-style`: tokens, type, parts, and the scheme toggle) unless the artifact has a reason to look otherwise, and ships both color schemes; the reader's system setting is the default, not a constraint. Look at both before presenting.
- A script a page loads from outside itself names an exact version (`pele@1.13.0`, never `@1`) and carries its `integrity` hash: a classic script in its `<script src integrity crossorigin>`, a module and every chunk it imports in an import map's `integrity` entries. Where a package ships a one-file classic build, load that: it needs one pin. Every page an agent opens is served from one local origin together with every agent directory, so a script changed at its CDN could read them all and send them off. jsDelivr lists each file's hash, which goes after `sha256-`, at `https://data.jsdelivr.com/v1/packages/npm/<package>@<version>?structure=flat`. An update is a deliberate edit of version and hash together.
- Look at your own render before presenting: `render-lint` an HTML page first (its `--help` says what it reports; `--narrow` for an app or a page read in a narrow window or zoomed in) and fix every fatal finding, then Read the PNG, run what runs, open the page. Drive a page or a UI the user will use as they will, in a browser you script: through the task it is for, by keyboard and by pointer, hovering what they would hover, and fix the friction and the ugliness met on the way before showing it. Done means you have seen it explain the thing *and* look good; an ugly artifact obscures what it was meant to clarify.
- Run one `/mx:writing-for-humans` pass over the artifact's text and fix what it finds.
- Present it: open it and give one line on what it shows and its absolute path.
