---
status: draft
---

# The board as the standing view of every ticket session

## Problem Statement

The board (`dashboard.py`: every feature, its dependency graph, the needs-human queue, the review-page links) is the overview max wants whenever tickets exist, including a single session working them in sequence: "to have the overview of what tickets exist without having to constantly check in terminal". Today it is rendered only by `dispatch review`, after a landing; a session running `/mx:implement` per ticket, or a grilling claiming a decision ticket, never renders it, and the tracker skill that defines the tickets does not know the board exists.

## Solution

The board is a tracker artefact, not a dispatch one: the script moves to the tracker skill, the tracker's markdown backend says when it renders, and the open tab stays current on its own. A session that fetches a ticket renders the board once, which opens the tab the first time (you, ticket) and starts a watcher that re-renders on every change under the tracker directory, so the tab stays current whoever writes: this session, another, a merge, a hand edit (you, r1). Dispatch keeps calling the same script from the same place.

## User Stories

1. As max working tickets in sequence in one session, I want the board open in a tab and current, so that I see which tickets exist and where each stands without checking the terminal.
2. As max with two sessions on one repo, I want one board both keep current, so that neither session's view lies about the other's claims.
3. As a session starting on a ticket (`/mx:implement`, a grilling claiming a decision ticket), I want the board rendered when I fetch the ticket, so that the tab opens once and stays.
4. As dispatch, I want the same script and the same page as every other ticket session, so that the board is one thing.
5. As a reader of the board, I want a feature's spec status (draft or confirmed) beside its tickets, so that a spec-only feature (grilled, not yet ticketed) is visible rather than an empty section.

## Properties

- The board renders from disk alone; any writer's render is correct, last writer wins.
- A change to tracker state is on the board within seconds without an agent's action (you, r1).
- One board per checkout: a worktree's board shows that branch's tickets; the main checkout's board is the integration view (my call).

## Decisions

- `dashboard.py` moves to the tracker skill as `board.py`, the glossary's word; `dispatch review` calls it there (my call).
- The tracker's markdown backend carries the rule: fetching a ticket renders the board (`--open auto` opens the tab only when the file is new) and ensures the watcher runs; one command does both, idempotent, like `diffview --serve` (you, r1).
- The watcher (`board.py --watch`) polls the tracker directory for changes every few seconds and re-renders on one; it serves the page on localhost so the tab's stamp poll reaches it, and exits after fifteen minutes without a poll, i.e. once no tab is open (my call). A page opened from the file path keeps working, only without the live reload.
- Output path `~/Downloads/board/<project>.html`, replacing `dispatch-dashboard/` (my call).
- The GitHub backend has no board of its own: GitHub's issue views are the board there (my call).
- A feature section shows its spec's status in the header (my call), from `spec.md`'s frontmatter.
- The serial ticket loop itself stays as orient describes it, the human running `/mx:implement` per ticket in a fresh window; a dispatch spawn mode for local subagents in worktrees, upstream implement-spec's shape without the tmux and host machinery, is (open → Q2): a sibling feature, or folded into this one.

## Testing Decisions

`dashboard.py` has no tests. The check is a dry run on this repo's tracker: claim a ticket from a second session and confirm the open tab shows it claimed without a render command in either session.

## Out of Scope

- implement-spec's exploration subagent and whole-feature code review: the [dispatch-implement-spec-inspo](../dispatch-implement-spec-inspo.md) ticket, untouched by this.
- The GitHub backend: nothing to build, its UI is the board.

## Fog

- Whether the board should show QA state per landed ticket (demoed, findings filed): nobody can say what that state is until the review session has run a few times with the board open.
