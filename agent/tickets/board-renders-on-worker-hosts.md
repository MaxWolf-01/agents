---
status: proposed
priority: 4
size: XS
---

# The board renders on a worker host

## Brief

On a dispatch worker host, `board` stops with "no tracker at …/agents.git/agent/tickets". The repo's main checkout there is a bare repo with no tracker, so a worker can't see the tracker it is working from.

Cut from two workers' friction on 2026-09-22 and 2026-09-23: figures-and-demos 06, which parsed its queue through `load_needs_human` instead, and board-orients 01, which skipped the render the tracker conventions ask for after a ticket change.

## What to build

When the repo's main checkout is bare, `board` reads the tracker from the worktree it runs in.

## Acceptance criteria

- [ ] `board --no-watch --no-open`, run inside a worktree of a bare repo, renders that worktree's tracker.
- [ ] Run from a non-bare checkout, it still reads the main checkout's tracker.
