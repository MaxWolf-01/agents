---
status: draft
---

# Tickets are always dispatched, and the board is their standing view

## Problem Statement

The board (`dashboard.py`: every feature, its dependency graph, the needs-human queue, the review-page links) is the overview max wants whenever tickets exist, including a single session working them in sequence: "to have the overview of what tickets exist without having to constantly check in terminal". Today it is rendered only by `dispatch review`, after a landing; a session running `/mx:implement` per ticket, or a grilling claiming a decision ticket, never renders it, and the tracker skill that defines the tickets does not know the board exists. Underneath sits a choice the workflow makes the human take every time: orient offers two ways to work tickets, by hand (`/mx:implement` per ticket, fresh window each) or dispatched, and with three projects open the by-hand way leaves max asking "which ticket was this session again?".

## Solution

One way to work tickets: when a feature has tickets, a dispatcher works them, one at a time or in waves; when it has none, the session that grilled it builds it (you, r2). The by-hand loop leaves orient, the README and to-tickets; `/mx:implement` stays the worker's skill. The orchestrator, which holds the spec and every ticket, reads each landed diff before merging it, since it can spot what a worker's fresh context could not (my call).

The board is a tracker artefact, not a dispatch one: the script moves to the tracker skill, the tracker's markdown backend says when it renders, and the open tab stays current on its own. One board per tracker, written beside it as `agent/board.html` (you, r3); the tracker itself lives in the repo's `agent/tickets/`, or in a workspace repo over several clones when features span repos or the tickets stay private to max (you, r3). The GitHub backend goes: GitHub issues are the team's communication interface, never the tracker (you, r3). A session that fetches a ticket renders the board once, which opens the tab the first time (you, ticket) and starts a watcher that re-renders on every change under the tracker directory, so the tab stays current whoever writes: this session, another, a merge, a hand edit (you, r1). Dispatch keeps calling the same script from the same place.

## User Stories

1. As max working tickets in sequence in one session, I want the board open in a tab and current, so that I see which tickets exist and where each stands without checking the terminal.
2. As max with two sessions on one repo, I want one board both keep current, so that neither session's view lies about the other's claims.
3. As a session starting on a ticket (`/mx:implement`, a grilling claiming a decision ticket), I want the board rendered when I fetch the ticket, so that the tab opens once and stays.
4. As dispatch, I want the same script and the same page as every other ticket session, so that the board is one thing.
6. As max, I want one way to work tickets, so that I never decide whether a feature is "big enough" to dispatch.
7. As max, I want the orchestrator to read a landed diff with the whole feature in mind before it merges, so that a detail the worker's brief missed is caught by the session that knows it.
5. As a reader of the board, I want a feature's spec status (draft or confirmed) beside its tickets, so that a spec-only feature (grilled, not yet ticketed) is visible rather than an empty section.

## Properties

- The board renders from disk alone; any writer's render is correct, last writer wins.
- A change to tracker state is on the board within seconds without an agent's action (you, r1).
- One board per tracker, showing what is actionable now: rendered from the integration checkout, never from a worktree (you, r3); a feature with a worktree on its own branch is shown from that worktree's copy of its tickets, so a dispatcher's claims and done flips are on the board while the feature is in flight (you, r4).
- A re-render never moves the reader: scroll position, open sections and the chosen view survive it, and unchanged content never reloads (you, r3).

## Decisions

- `dashboard.py` moves to the tracker skill as `board.py`, the glossary's word, since the tracker skill is what every ticket session reads; `dispatch review` calls it there (you, r4).
- The tracker's markdown backend carries the rule: fetching a ticket renders the board (`--open auto` opens the tab only when the file is new) and ensures the watcher runs; one command does both, idempotent, like `diffview --serve` (you, r1).
- The board reads every worktree of the repo (`git worktree list`); a feature directory present in a worktree whose branch is that feature's is taken from there, every other feature and the standalone tickets from the integration checkout (you, r4). Nothing about how tickets are committed changes.
- The watcher (`board.py --watch`) polls the tracker directory for changes every few seconds and re-renders on one; it serves the page on localhost so the tab's stamp poll reaches it, and exits after fifteen minutes without a poll, i.e. once no tab is open (my call). A page opened from the file path keeps working, only without the live reload.
- Output `agent/board.html` beside the tracker, with its stamp file, gitignored like `agent/diffviews/`; the project-setup skill's gitignore list and this repo's follow (you, r3).
- The tracker has one backend, markdown: `GITHUB.md` is deleted, the tracker skill's backend list becomes the two homes (the repo, or a workspace repo over clones), and the README's and to-tickets' GitHub lines go (you, r3).
- A feature section shows its spec's status in the header (my call), from `spec.md`'s frontmatter.
- A feature with tickets is worked by `/mx:dispatch`, at any size; orient's step 3 routes tickets to dispatch and drops the by-hand loop, the README and to-tickets' closing line follow (you, r2). A feature without tickets is built by the session that grilled it, as the gate already says.
- Dispatch's tick step 1 gains: before merging a landed ticket branch, the orchestrator reads its diff against the ticket and the spec; what it finds goes back to the worker as guidance on resume, or becomes a ticket (my call).

## Testing Decisions

`dashboard.py` has no tests. The check is a dry run on this repo's tracker: claim a ticket from a second session and confirm the open tab shows it claimed, scrolled where it was, without a render command in either session; and a render of the workspace layout (tracker in a parent repo over clones) from that parent.

## Out of Scope

- implement-spec's exploration subagent and whole-feature code review: the [dispatch-implement-spec-inspo](../dispatch-implement-spec-inspo.md) ticket, untouched by this.
- A dispatch spawn mode without tmux (workers as in-process subagents): tmux panes on a host that stays awake are the better runner in every respect max cares about, and in-process subagents die with the orchestrator.

## Fog

- Whether the board should show QA state per landed ticket (demoed, findings filed): nobody can say what that state is until the review session has run a few times with the board open.
