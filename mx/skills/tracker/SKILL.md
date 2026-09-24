---
name: tracker
description: "Tracker conventions: the ticket tree, how a ticket is filed, fetched, claimed, ruled on and retired, and the board that shows them all. Use when filing or fetching a ticket, picking work from the frontier, cutting a ticket into child tickets, recording a ruling, rendering the board, or when another skill says \"publish to the issue tracker\"."
---

# Tracker

One kind of file: a **ticket**, `agent/tickets/<slug>.md`, flat, the slug its id. `parent: <slug>` makes it the **child ticket** of another, and the tree goes as deep and as wide as the work needs. The tracker sits in the repo it plans, or, where the work spans repos or the tickets stay out of a shared one, in a workspace repo holding the clones as untracked directories and the tracker beside them.

The `tracker` command owns every mechanical operation on those files, read and write, and `tracker --help` is the reference for all of them: filing, reading a field or the whole tracker, a ticket's context, the frontier, status changes, rulings, retiring, dropping. Publishing to the issue tracker is `tracker new`, fetching a ticket is `tracker context`. Its check runs over the staged tickets from a pre-commit hook (`/mx:project-setup` wires it into a repo), so a file no reader could read is refused where it was written. What no command writes is the body, the prose the agent puts in the file: [MARKDOWN.md](MARKDOWN.md) is its shape, and [SLICING.md](SLICING.md) is how one ticket is cut into child tickets.

## The tree

A ticket's **context** is its own body and every ancestor's, so a parent ticket says once what its children are slices of and a child ticket never repeats it. Properties are read through the same ancestry and cited `<slug>#P<n>` from any descendant. A child ticket's file is committed on its parent ticket's branch, a top-level ticket's on the integration branch.

A parent ticket is done when every child ticket is done and its own close-out is ruled: the full suite, the review one level up, harden, the debrief (`/mx:dispatch`).

## State

Which status may follow which is `tracker`'s, refused by the rule it names. What they mean:

- **proposed**: an agent filed it on its own reading (a worker's friction, a review finding too large to fix there, a punt) and the user has not ruled. It is on the frontier and built like an open ticket, so what waits is the ruling and not the build; its brief says what it was cut from.
- **open**: ruled, and not yet built. A ticket the user asked for in conversation is ruled already; silence is not a ruling.
- **claimed**: a session holds it, a worker resumed to revise included. Where several run at once, one agent is the sole claim-writer.
- **review**: the work is finished and waits for the user's **ruling**, made on the ticket's review page and its demo, or as a line in chat. It unblocks nothing, so a dependent never builds on a guess.
- **done**: the accept, and nothing less. A ticket the user is in the loop for (`needs-user`) is done by their ruling alone, having no branch to merge.

The ruling has four outcomes. **Accept** merges the branch and writes `done`. **Amend** sends the user's comments back to the worker, which revises on the same branch and comes back for a ruling. **Redo** discards the build and keeps the ticket: `git branch -D`, back to `open`, the reason under its Comments. **Reject** takes the ticket out with its build: `tracker drop`, `git branch -D`, the reason in the commit message, and a reason the next build must know goes where rules live (an ADR, the project's CLAUDE.md, the tool's config).

Two facts carry **provenance**. Whether the user wanted the ticket at all is its status. Whose framing it carries is inline: an approach an agent sketched says so ("options sketched by agent <date>, frame unconfirmed"), one the user decided points at the decision, and unmarked framing reads as agent-sketched. Acceptance criteria that keep the option space open ("decision recorded; options outside this list count") leave the session working the ticket the problem, not the menu it arrived with.

## Supersede

A newer artefact never leaves the older one looking live; agents read whatever exists as current truth. A superseded file is **tombstoned** (one line at the very top: `> Historical artifact as of <date>, superseded by <successor>. Not current; kept as the reasoning trail.`) or, with no reader value left, deleted, which git history keeps.

While nothing is built on a ticket's answer, a later decision that overturns it amends it in place, marking the changed claim inline (`(amended <date>, was <old>)`). Once code reads the answer it is the reasoning behind that code: leave it, file a ticket that supersedes it, and put a one-line forward pointer on the old one. Either way the **sweep** follows in the same session: grep the retired claim across `agent/tickets/`, `CONTEXT.md` and `decisions/`, since a copy left standing is current truth to every later reader. A sweep that cannot run now is a ticket with a blocking edge.

## Retire

Retiring is for work that has **shipped**: `tracker retire` takes the ticket and everything under it out of the live tracker, and the commit is the caller's. What a README, a PR or the build still needs is promoted out of `agent/show/` in that same commit (`/mx:show`, Promotion). `git log --diff-filter=D -- agent/tickets agent/show agent/prototypes` is where retired work is read afterwards.

## Board

The board is the tracker as one page, `agent/board.html` beside it (gitignored); `board --help` says what it shows and which checkout's copy. The human runs `board` and the tab then follows every tracker change on its own. A session renders once, without opening a tab, after it changes tracker state, so the page on disk is current for whoever opens it next.
