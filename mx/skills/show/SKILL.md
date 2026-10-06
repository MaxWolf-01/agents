---
name: show
description: "Show, don't tell: a session's answers on its session page, and the artifacts that make a thing visible, so a reader sees what it is and what it does: a figure, a diagram, a demo, an explainer page. Use whenever a turn delivers an answer, an artifact, a question or a landing, when writing a ticket's Decisions or an ADR, when work lands for the user's ruling, when someone asks for a demo or has to see or learn how something works, or when another skill needs an artifact."
---

# Show

A thing is understood in front of a render: someone sees what it is and what it does, whether they are ruling on it, grilling it, reviewing it, or learning how it works. Pick the cells of the grid the reader's question needs, have what the table names for the thing's shape built, look at it, put it in front of the reader on the session page.

## The session page

A session the user reads answers on its **session page**: one page per session, rendered from plain-text records each time a turn ends, with the questions waiting on the user at its top and the turns below, newest first. Every session the user sits at has one from its first turn that ends on a reply. A turn that delivers something (an answer, an artifact, a question, a landing) writes it there as a turn record and ends on a chat recap, with the Stop hook's line under it: the questions waiting on the user and a link to the page. A turn that only reports where it stands (working on X, waiting on a worker or a run) ends on a line or two in the chat, which the page shows as the session's status. A session outside a project with an agent repo (`session-page` refuses) answers in the chat, and so does one nobody reads live, a dispatched worker or a print-mode run, whose artifacts are its report.

The records sit in the directory `session-page` prints, outside git and the same from every worktree of the project. A write to one is checked as it lands: a record that does not parse comes back with the reader's error, and the turn's record gets a light review of its prose once it parses, whose findings come back while the turn still runs. As the turn ends the page renders from the records, and the turn is sent back instead when a record does not parse or was written other than with the Write tool. A turn that writes no record and ends on a reply gets one from the Stop hook, whatever the reply's length: the reply as it stood, as a chat turn, which the page shows among the turns by its time and without a number. The session's first such reply is what creates its directory and its page.

A turn that delivers something, in order:

1. **Its artifacts**, each built by a subagent or a fork (Who builds it, below), since the session writes no HTML. The turn waits for them, so every link its record carries points at a page that exists.
2. **The session record**, with the first turn record: `session.md`, with frontmatter `session` (the id) and `repo` (the directory the session was started in, which the page's resume command changes into), an H1 that names the session's subject the way an email subject line does (the area of the project and the things worked on, by name), and a `## Brief` of a few sentences. Until it exists, the page takes the title Claude Code keeps for the session and shows no brief. Both are rewritten when the session's scope moves, and a turn that rewrites them has them reviewed with its record.
3. **The turn record**, below, written with the Write tool, since the page pairs the record with the user's message by that call. Revise it where a finding holds.
4. **The chat recap**, the turn's last message, once the record is final: what waits on the user, as action items, one plain line each that reads on its own, each open question named by what it decides ("Rule on Q7, what reviews a turn's prose"), or one line saying nothing does. The user reads the recap in the terminal and the page beside it, so the recap never points at the page, and the questions themselves, with their reasons, options and figures, stay on the page. It reads the same whether or not a finding or a parse error came back on the way.

A question still open when the session ends leaves the page for a ticket, since every question on the board belongs to a ticket: a grilling's as the child tickets `/mx:grilling` files, any other as one of the questions of the ticket it concerns (`/mx:tracker`), or a proposed ticket where no ticket holds it. A question is tagged where it lives: `Qn` on the session page, `Dn` in a ticket.

### The turn record

`turns/NN.md`, numbered on from the last `NN.md`, shaped like a ticket file and written once: a later turn never edits it, and a question clears through the frontmatter of the turn that received its answer.

```markdown
---
date: 2026-09-28
answered:
  Q3: a
  Q4: keep both, the user's own words where the answer was neither option
superseded:
  Q5: Q7
---

# The turn's headline: what it answers, in one line

## Questions

- [Q7] **The decision, as a question** the part of the design it would change
  - (a) The option recommended *my pick*
  - (b) The other option
  - Why: the argument for the pick, and what it costs

## Links

- [What the artifact shows](agent/show/<slug>/figure.html): why to open it

## Details

A few lines of plain markdown: what the reader needs beyond the headline and the links.
```

- `date` is the day the turn ends. `answered` maps each question whose answer this turn received to the option's letter, or to the user's own words where the answer was neither option; `superseded` maps a question to the one that replaced it. A question either one names leaves the top of the page.
- **Questions** holds only the calls the user must make. The user decides what gets built: its purpose, its scope, its constraints, and the trade-offs between them; you decide how. Ask them before you change what they asked for: adding to it, cutting from it, replacing one of their rulings, or assuming what it is for. Never ask them how to build it, or whether to go ahead with what they already asked for: do it, and the landing shows them. A question that passes names what they asked for and the change you would make to it, with at least two options you would defend and your pick marked. Tags run `Q1`, `Q2`, … across the whole session. A call the user need not make is a line of Details, or a call mark in the ticket it shapes, and nothing asks the user to acknowledge it. A ticket's own question shown on the page is a line of Details citing its ticket and its `Dn`, since it clears through the ticket.
- **Links** are the artifacts this turn made or moved, each a path from the repo root (absolute for one in another repo) and a note on why to open it. As the turn ends, the Stop hook opens every one but a ticket file in the user's browser.
- **Details** says what the reader needs beyond the headline and the links, and never retells what an artifact shows.
- Anything the record points at is a link. A path on this machine written as code opens the file; `[text](#t07)` opens turn 07 and `[text](#q3)` shows question Q3, so a question at the top links the turn whose Details it leans on.
- A section with nothing in it is left out. The user's own message is read from the transcript, so the record never quotes it.

## What a reader can be shown

It sits on two axes. The **level** is what they look at: the **concept** (how it fits and why, drawn), the **code** (what is written: code, config, a prompt, a skill's prose) or the **output** (what it produces: a printout, a record, a render, what an agent answers). The **form** is the thing as it is, or how it changed.

| | as it is | how it changed |
| --- | --- | --- |
| concept | concept figure | concept diff |
| code | code listing | code diff |
| output | output | output diff |
| prose | abstract prose, narrated example | |

The line that matters is **narrated against real**: an example written from the head is a narrated example, one made by running the thing is output, and a narrated example says it is one.

The reader's question picks the level: how does it fit, what did you write, what will I see. Whether something moved picks the form: a thing that existed and changed gets the diff form, a new thing the as-is form, and a decision nothing has built yet the concept level alone. Cells combine whenever each adds what the others do not; a clean output diff, the same scenario on the old and the new, is usually the one that shows most. A change to something the user looks at (a page, a view, a command's output) is shown as that thing: the page opened or rendered, the command run, before and after where it existed. A change to how things fit (the architecture, a flow, an interface) is drawn at the concept level. The code diff sits beside either, and stands alone only where it makes the change plain at a glance (a typo, a rename).

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

Shape decides, never size: a one-column change gets no ER diagram, a two-table schema gets one. A thing of several shapes gets every row it hits. An empty cell means nothing is owed there, and no cell is padded to have something in it. At a landing the table says what its show holds. Every document takes this table, an ADR included, and most ADRs hit no row.

The rows are examples, not the boundary. Media craft below is the open set, and an artifact nothing here names is the right answer whenever it shows the thing better. An explanation built for learning is one more case, and a page in the distill.pub tradition, with figures the reader pokes at, is what it wants.

## A landing's show

Every landing (`/mx:dispatch`) comes with its review page and one show, a build that puts no call to the user included, read whenever the user looks. A change the diff alone makes plain at a glance (a typo, a renamed variable) goes without one, and the landing says so in a line. The show is for the user's understanding of what was built, and where the landing puts calls to the user, it is built around them, as far as their ruling needs it. Demonstrating that the tests are green or that it runs is not the show's job: the tests and the review already did that, and a build that does not run has no show to be made of it. Its reader has the product sense and none of the weeds: technical, did not build it, and wants to understand it, told accurately and never sold.

- **One per landing.** A tree's show covers every child ticket in review, and goes to the parent ticket's directory; a tick that brings another to review rebuilds it rather than adding a second, so it is whole when the user sits down to rule: on a hinge alone, and on the rest with the parent ticket at its close-out. A standalone ticket's goes to its own.
- **Built by a fork** of the session landing the work (invoke `mx:fork`): it holds the conversation the user's questions came from, and its build loop stays out of that session's window.
- **Top down.** It opens with the intent and the change to how the parts fit, a figure where the structure moved; each lower level appears only where the one above needs it, and the code diff, on the review page, comes last. The user reads it from the top and goes a level lower only where the one above looks wrong or needs explaining, so a mistake high up is caught before the diff is read.
- **The few things the user would notice.** Each gets a caption of a sentence or two, the cells the grid picks, and numbered notes on where to look. The commands a run made sit folded under what they produced.

## Where it goes

An artifact goes to the show directory of the work it serves, committed with that work: `agent/show/<slug>/` for a ticket, `agent/show/<branch>/` for loose work. That directory is the agent repo's, so `git -C agent` is what commits it, and a landing's show is committed in its main checkout, as a ticket file is. One that serves no ticket or branch goes to `~/Downloads/show/<slug>/` instead: the user wants it throwaway, there is no repo to keep it in, or the repo is the wrong home for it.

## A figure

A concept figure or a concept diff is drawn, in one of two file shapes chosen by how the picture is made.

- **A diagram whose layout mermaid solves**: one source file named for what it shows with its SVG beside it, `<name>.mmd` and `<name>.svg`, both committed. The SVG is what gets opened, since it scales with zoom where a raster does not. A mermaid render carries the renderer's own colour scheme, so the both-schemes rule under Produce and present does not reach it.
- **A picture whose coordinates you place yourself**: one self-contained HTML file ([`SVG-FIGURES.md`](SVG-FIGURES.md)), which draws itself in either scheme from that one source. A figure heading for a document wants this shape, since the document needs both schemes and a renderer of its own reads the file.

Either way the render is regenerated from the source whenever the decision moves, and a PNG for embedding is rendered on demand and stays untracked beside its source, which is why a figure a document in the tree embeds is promoted with the script that renders it rather than copied (Promotion, below). A page (`index.html`) holds more than one thing at once, several figures, or a diagram and the sample instance beside it, and there every image sits at `width:100%; height:auto` so it scales too.

## A runnable artifact

What runs in a show directory (a walkthrough that drives the tool, a script that renders a sample) is an executable file taking no arguments, with a shebang and whatever language it needs; a one-off script is not a CLI, so `/mx:tyro-cli` does not bind it. It writes what it produces into `out/` beside itself, untracked because the next run regenerates it; it opens what it produced when a display is there and lets go of it rather than waiting on it; it runs from a fresh checkout on any host where the project is installed, and says so when it fails rather than printing an empty result. The board lists it with the rest of the directory and, seeing the executable bit, puts the command that runs it from the code repo's root on a button, so the reader starts it when they want it.

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
- A script a page loads from outside itself names an exact version (`mermaid@11.17.2`, never `@11`) and carries its `integrity` hash: a classic script in its `<script src integrity crossorigin>`, a module and every chunk it imports in an import map's `integrity` entries. Where a package ships a one-file classic build, load that: it needs one pin. Every page an agent opens is served from one local origin together with every agent directory, so a script changed at its CDN could read them all and send them off; the browser refuses a file whose hash does not match. jsDelivr lists each file's hash, which goes after `sha256-`, at `https://data.jsdelivr.com/v1/packages/npm/<package>@<version>?structure=flat`. An update is a deliberate edit of version and hash together.
- A page names the session the reader resumes to get back to the conversation behind it: `session <first 8 of the id>` in its `v-meta` line, as a button that copies `claude --resume <id>`, the id being `${MX_ORIGIN_SESSION:-$CLAUDE_CODE_SESSION_ID}` read in the shell.
- Look at your own render before presenting: Read the PNG, run what runs, open the page. Done means you have seen it explain the thing *and* it looks good; an ugly artifact obscures what it was meant to clarify.
- Present it as a link in the turn record that asked for it (The session page). Where there is no page, open it (`claude-browser` where it exists, else `xdg-open`) and give one line on what it shows and its absolute path.

## Who builds it

Every artifact is built by a subagent or a fork, never by the session answering the user, so its render and debug loop stays out of that session's context. A subagent works from a brief: the artifact, its output path, and the sources on disk to read. A fork of the session (invoke `mx:fork`) is taken when the conversation itself is the source the artifact needs and no file carries it.

The builder is done once it has seen the artifact and reviewed its prose. It looks at its own render (Produce and present), then runs one `/mx:writing-for-humans` pass over the artifact's text and fixes what the pass finds, and only then hands back the path.

## Promotion

A figure, or an output, that a README or a PR description needs moves to where that document's assets live, a `docs/` or `assets/` directory the document already reads from: the render, its source, and the script that regenerates it travel together, and every reference is repointed in the same commit. No show directory outlives the work it belongs to, whatever still reads it, so a copy left behind in one is a stale figure waiting to be read as current. What the destination takes varies: a PNG the README embeds, committed with it; an image in an issue or a PR description, pushed with `gh-asset push` for its URL; an output pasted into a PR as a code block; a script that asserts moved under `make check`. The move is your own call and visible in the diff, so no ruling gates it.
