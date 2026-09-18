---
status: open
type: prototype
---

# A ticket carries a brief for the human, and the board links its artefacts

## Question

Ruled worth grilling by the user in chat, 2026-09-18, while reviewing figures-and-demos. Two things a ticket lacks when the user opens it cold on the board:

1. **A brief for the human.** A ticket's body is written for the worker that builds it, and expanding one on the board hands the user that text: daunting after a week away, and useless for orienting across ten proposals from several agents. The ticket wants a field, or a section, that says in a glance what this is about, why, in what context, and roughly how, written cold for the user and passed through `/mx:writing-for-humans` before it lands; the board shows it first.
2. **Links to the ticket's artefacts.** The spec is read on diffview and nowhere else; the figures a round draws, the demos a landing stages and whatever else a ticket produced sit under `agent/show/` unlinked. The ticket's frontmatter names its artefacts, the board renders each as a link, and they live and retire with the ticket. The shape is the agent's: one page collecting every rendering, or several standalone files.

3. **The demo's path, copyable.** Where a ticket has a demo, its absolute path on this machine is a frontmatter element the board shows as one more row to click and copy, beside the review page; a ticket has no demo where its change has no shape the show table gives one (a prose edit, a change the diff shows whole), and the board shows nothing for it.

The user's reading of the shape (2026-09-18): one expert call on the interfaces, the seams and the data structure, then a prototype or two of the board with these elements, on which the user decides; little grilling. The board's other open tickets ([The board's needs-human section](board-carries-what-needs-you.md), [A ticket records the sessions that touched it](ticket-sessions.md)) share the surface and may go to one worker.

To decide, options sketched by the agent, frame unconfirmed: the brief as a frontmatter field or a first section under a fixed heading, and who writes it (to-tickets for a slice, the worker at closing for what it built, the orchestrator for a proposal it files); the length the board shows before expanding; how the artefact links are declared (a frontmatter list, or the board reading the ticket's show directory on its own); whether a spec gets the same treatment (its figures, its review page) from the feature's row; and what `/mx:writing-for-humans` is run over, the brief alone or the whole ticket.
