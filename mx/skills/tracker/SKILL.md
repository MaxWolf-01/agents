---
name: tracker
description: File-based issue tracker conventions — how specs, tickets, and small tasks live in agent/tasks/ and how to publish, fetch, claim, and retire them. Use when publishing or fetching a spec/ticket/task, picking work from the frontier, or when another skill says "publish to the issue tracker".
---

# Tracker

Issues for this repo live as markdown files in `agent/tasks/`. These conventions are the default — if the project's CLAUDE.md declares a different tracker (e.g. GitHub Issues), follow that instead.

## Layout

- **Feature**: one directory per feature, `agent/tasks/<feature-slug>/`
  - `spec.md` — the work order for the whole feature (written by `/mx:to-spec`)
  - `NN-<slug>.md` — tickets, numbered from `01` (written by `/mx:to-tickets`)
- **Small standalone task**: a single file `agent/tasks/<slug>.md` — ticket-shaped, no spec needed

## Ticket state

Frontmatter:

```yaml
status: open | claimed | done
blocked-by: [01, 02] # ticket numbers within the feature; omit when nothing blocks it
```

- A ticket is **unblocked** when every ticket in `blocked-by` is `done`.
- The **frontier**: open, unblocked, unclaimed tickets — what can be started right now.
- `claimed` marks a ticket a session is actively working. Set it before any work. Across parallel checkouts a claim only coordinates once it's shared: commit the claim by itself and push — to the feature's integration branch, or main for standalone tasks — before starting; if the push is rejected, pull — another session beat you to it — and pick the next frontier ticket. (With a single agent in a single checkout, claiming is optional.)
- Notes and follow-up conversation append under a `## Comments` heading at the bottom of the file.

## Publish / fetch

- "Publish to the issue tracker" → create the files above (creating the feature directory if needed).
- "Fetch the ticket" → read the ticket file **and** the feature's `spec.md` — tickets don't repeat the feature context, the spec carries it.

## Retire

Set `status: done` when a ticket completes. When the whole feature has shipped, `git rm -r agent/tasks/<feature-slug>/` — git history preserves it (`git log --diff-filter=D -- agent/tasks` finds retired work). If the repo doesn't track `agent/tasks/`, plain delete.
