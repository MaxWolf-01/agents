---
name: tracker
description: "Tracker conventions: the ticket tree, how a ticket is filed, fetched, claimed, ruled on and retired, and the board that shows them all. Use when filing or fetching a ticket, picking work from the frontier, cutting a ticket into child tickets, recording a ruling, rendering the board, or when another skill says \"publish to the issue tracker\"."
---

# Tracker

One kind of file: a **ticket**, `agent/tickets/<slug>.md`, flat, the slug its id. `parent: <slug>` makes it the **child ticket** of another, and the tree goes as deep and as wide as the work needs. The tracker sits in the repo it plans, in its main checkout, or in a repo of its own that the code repo names with `git config mx.tracker <path>` in that clone alone: the path is machine-local, like the setting, so neither repo commits the other's layout, and the tickets can stay out of a repo that is shared. The path is the tracker's own `agent/tickets`, or the repo holding it.

The `tracker` command owns every mechanical operation on those files, read and write, and `tracker --help` is the reference for all of them. Publishing to the issue tracker is `tracker new`, fetching a ticket is `tracker context`. Its check runs over the staged tickets from a pre-commit hook (`/mx:project-setup` wires it into a repo), so a file no reader could read is refused where it was written. What no command writes is the body, the prose the agent puts in the file: its shape is below, and [SLICING.md](SLICING.md) is how one ticket is cut into child tickets.

## The ticket file

All of a ticket's metadata is frontmatter, and the fields are `tracker get --help`'s. Three of them are judgments rather than bookkeeping:

- **priority**: the agent's reading of how soon the ticket matters to the user, never their chore to rank.
- **size**: the user's own time on it, never the agent's. XS under 15 minutes, S about 20, M about an hour, L half a day, XL several sessions.
- **needs-user**: the user is in the loop for this one, so dispatch keeps it from a worker and their ruling is what lands it.

**The H1 is the ticket's short name**, the few words a board row shows; the sentence a title would carry goes in the brief instead. Under it the body is prose the agent writes, in the vocabulary of `CONTEXT.md`, in this order:

- **`## Brief`**, always, right under the H1: the intent and why it matters, as a technical stakeholder writes it, read cold. A proposal's says what it was cut from.
- **`## User stories`**: numbered, `As an <actor>, I want <a capability>, so that <a benefit>`.
- **`## Properties`**: `- P<n> <the property>`, one always or never sentence each. The id is permanent, and every descendant cites it `<slug>#P<n>`.
- **`## Decisions`**: the calls, each carrying the **call mark** that says who settled it.
- **`## Testing seams`**: the seams the work is tested at, their oracles, and every property disposed of as executable or reviewed.
- **`## Out of scope`**: what this ticket will not do, each with its reason.
- **`## Fog`**: in-scope work whose question cannot yet be stated.
- **`## Acceptance criteria`**, always: `- [ ]` items, what the work has to hold to be done.
- **`## Questions`**: the calls only the user can make, below.
- **`## Comments`**, always, at the bottom: notes, follow-up conversation and a worker's closing comment. A research finding lands in the ticket that asked for it, here or in the design sections, its detail in `agent/research/` (`/mx:research`).

Every section but the three marked always appears when it has content. Read [`/mx:grilling`'s DESIGN.md](../grilling/DESIGN.md) in the round that writes the design sections, User stories through Fog: it is how each one is written.

### Questions

One `- [Dn] **headline** detail` item each, the tag continued from the highest the file already carries so it names one thing for good:

```markdown
## Questions

- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing.
- [D2] **Keep the test in the fast suite?** It takes four seconds either way.
  - Ruled 2026-09-21: keep it in the fast suite.
```

A question is open, and shows in the board's needs-me group, until a `Ruled <date>:` line sits under it. A question a worker raised reaches the tracker's copy with its report, which is what puts it in front of the user, and `tracker rule` writes the answer under it, before the build's merge as after it. Every question belongs to a ticket: one with no ticket to hang on is filed as a proposed ticket, and the ruling on that proposal is the answer. A question the ruling on a build leaves open is filed as a proposed ticket then, so a done ticket carries none.

## The tree

A ticket's **context** is its own body and every ancestor's, so a parent ticket says once what its children are slices of and a child ticket never repeats it. Properties are read through the same ancestry and cited `<slug>#P<n>` from any descendant. Renaming a ticket is a string replace of its slug across the tracker, read over as a diff; no command does it, since the slug is unique.

Every ticket file is written and committed in the tracker's own checkout, on the branch that checkout has out and never on a code branch, so a ticket change needs no branch or merge of its own. The writers are the sessions working with the user and the orchestrator of a build (`/mx:dispatch`); a worker opens no ticket file, and what it has to say reaches its ticket when the orchestrator imports its report.

A parent ticket is done when every child ticket is done and its own close-out is ruled: the full suite, the review one level up, harden, the debrief (`/mx:dispatch`).

## State

Which status may follow which is `tracker`'s, refused by the rule it names. What they mean:

- **proposed**: an agent filed it on its own reading (a worker's friction, a review finding, a punt) and the user has not ruled. It is on the frontier and built like an open ticket, so what waits is the ruling and not the build; its brief says what it was cut from.
- **open**: ruled, and not yet built. A ticket the user asked for in conversation is ruled already; silence is not a ruling.
- **claimed**: a session holds it, a worker resumed to revise included. Where several run at once, one agent is the sole claim-writer.
- **review**: the work is finished and waits for the user's **ruling**, made on the ticket's review page and its demo, or as a line in chat. It unblocks nothing, so a dependent never builds on a guess.
- **done**: the accept, and nothing less. A ticket the user is in the loop for (`needs-user`) is done on their ruling with no branch to merge, travelling the same statuses to get there.

The ruling has four outcomes: **accept** the build, **amend** it with the user's comments, **redo** it from the ticket, or **reject** the ticket with it. `/mx:dispatch` runs each one. A reason for a rejection that the next build must know goes where rules live: an ADR, the project's CLAUDE.md, the tool's config.

Two facts carry **provenance**: whether the user wanted the ticket at all is its status, and whose framing it carries is inline, an approach an agent sketched saying so ("options sketched by agent <date>, frame unconfirmed") while unmarked framing reads as agent-sketched. Acceptance criteria that keep the option space open ("options outside this list count") leave the session working the ticket the problem, not the menu it arrived with.

## Supersede

A newer artefact never leaves the older one looking live; agents read whatever exists as current truth. A superseded file is **tombstoned** (one line at the very top: `> Historical artifact as of <date>, superseded by <successor>. Not current; kept as the reasoning trail.`) or, with no reader value left, deleted, which git history keeps.

While nothing is built on a ticket's answer, a later decision that overturns it amends it in place, marking the changed claim inline (`(amended <date>, was <old>)`). Once code reads the answer it is the reasoning behind that code: leave it, file a ticket that supersedes it, and put a one-line forward pointer on the old one. Either way the **sweep** follows in the same session: grep the retired claim across `agent/tickets/`, `CONTEXT.md` and `decisions/`, since a copy left standing is current truth to every later reader. A sweep that cannot run now is a ticket with a blocking edge.

## Retire

Retiring is for work that has **shipped**, and `tracker retire` is what runs it. What a README, a PR or the build still needs is promoted out of `agent/show/` in that same commit (`/mx:show`, Promotion). `git log --diff-filter=D -- agent/tickets agent/show agent/prototypes` is where retired work is read afterwards.

Loose work has no ticket to retire: its show directory and the prototypes it made are `git rm`'d on the branch itself, so the merge that lands the work carries the removal.

## Board

The board is the tracker as one page, `agent/board.html` beside it (gitignored); `board --help` says what it shows. The human runs `board` and the tab follows every tracker change on its own; a session renders once, without opening a tab, after it changes tracker state, so the page on disk is current for whoever opens it next.
