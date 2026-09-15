---
status: proposed
---

# Show carries the shape table: figures for decisions, demos for landings

Slice of `spec.md`, building on Solution (you, r4), Decisions "One table, two media columns" (you, r4), "Trigger by shape, not size, on every artefact" (you, r5), "The rows" (agent's call, r2 to r5; the sample-instance row is yours, r5), "The demo is one file named `demo`" (you, r4, r5), "A heavy artefact goes to a fresh agent with a brief" (you, r4), "File shape of a figure" (you, r4, r5), "Promotion is the agent's call" (you, r5).

## What to build

An agent that opens `/mx:show` with a decision or a delivered change in hand finds one table and needs no judgment call: the row for the shape of the thing names the figure a spec decision of that shape gets and the demo a landed change of that shape gets, and a shape with no row gets nothing. The skill's description fires from the two stations, writing a spec's Decisions and closing a landing, and not only from a struggling explanation.

Around the table, the conventions the rows lean on, each stated once: a figure is a source file with its SVG beside it, the SVG is what gets opened, the PNG is rendered for embedding and stays untracked, and a page holding several figures scales them; a demo is one executable file named `demo`, no arguments, in the show directory of the work it demonstrates (a feature's slice, a standalone ticket, a loose branch), producing what it produces beside itself and opening it when a display is there; a heavy artefact at either station goes to a fresh agent with a brief naming the artefact, its output path and the sources on disk, and a fork is taken only when the conversation itself is the source; a figure or a demo's output that a README or a PR needs is promoted there on the agent's own judgment, visible in the diff, HTML through the share script.

The rest of the skill (register, media notes, pages, SVG guidance) stays where the table does not retire it; what the table retires goes.

## Acceptance criteria

- [ ] Given a two-table schema decision, an agent following the skill produces an ER diagram with a sample row beside it, as source plus SVG under the feature's show directory, and opens the SVG.
- [ ] Given a landed CLI change, an agent following the skill writes an executable `demo` with no arguments that runs the CLI and pastes that run's output under the command; given a landed page, `demo` opens it.
- [ ] The description names both stations, so the skill is reached from a spec's Decisions and from a closing comment (`/mx:writing-for-agents`, context pointers).
- [ ] The fork rule is replaced by the fresh-agent-with-a-brief rule, the fork kept as the named exception.
- [ ] Property, reviewed: a demo file takes no arguments and runs from its branch on any host where the project is installed; what it produces lands beside it.
- [ ] Property, reviewed: a figure's source is committed; its raster render is regenerated and never tracked.
- [ ] Property, reviewed: a slot is never padded; the table says so.
- [ ] Demo: `agent/show/figures-and-demos/01-show-table/demo`, executable, no arguments, per the table's row for a skill change: a driven session given a two-table schema decision, showing the figure it produces; where the plugin cannot be loaded in that session, the closest render, and the comment says so.
