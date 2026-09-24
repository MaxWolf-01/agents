---
status: claimed
parent: ticket-file-contract
blocked-by: [tracker-command-and-commit-check]
priority: 1
size: L
---

# Every script goes through the tracker command, and the live tracker is converted

Child ticket of `ticket-file-contract`, building on its Decisions: one kind of ticket with a parent ticket and slugs as ids (you, r1 and r2), ticket files on the parent ticket's branch (you, r2), close-out at every parent ticket (you, r2), properties read through the ancestry (you, r2), the review reading the ticket plus its ancestry (you, r1), no decision tickets and one field for tickets that need the user (you, r3), the tracker converted by a worker rather than a script (you, r2), and shipped work left for the parent ticket's final cleanup (you, r5).

## Brief

This ticket builds on master after board-orients has merged, which reworked the board, the tracker and dispatch (its queue file among them); read what it landed before the list below, which was written against the master before it, and treat any item it already settled as settled.

The scripts that read or write ticket files move onto the `tracker` command from `tracker-command-and-commit-check` and onto the new model, and the live tracker is converted in the same branch, so no commit has scripts and tracker disagreeing.

- `board.py`: one ticket kind in place of the Feature and Standalone classes; the parent-ticket tree shown where the feature grouping was; the slug as a row's id; the spec-status chip and the absorbed-standalone filter gone; the worktree override generalised to "the branch a parent ticket is built on". It renders nested lists the way the writers write them (CommonMark's three-space nesting; the parent ticket's incident).
- `dispatch`, `dispatch-ctl`, `run-worker.sh`: the feature-or-standalone case detection goes; a ticket branch `ticket/<slug>` is cut from the branch dispatch runs on, which is the parent ticket's; every status read and write goes through `tracker`; `spawn` refuses a ticket that needs the user, in place of refusing a `type`; `notes_of` takes `tracker`'s Assumptions; a review page lives at `agent/diffviews/<slug>.html`; the fuzz run and the close-out helpers take a parent ticket where they took a feature. `dispatch-ctl` wires the commit check into the repo it stages on a worker host.
- `property_coverage.py`: every executable property has a check; a citation `<slug>#P<n>` resolves or is refused.
- code-review's `review`: `--spec` takes `tracker`'s context for a ticket; nothing in it keys on a `spec.md`.
- The conversion, with judgment: each feature's `spec.md` becomes a top-level ticket named after the feature, its `NN-slug.md` tickets become child tickets with descriptive slugs, and every `blocked-by` and cross-reference is rewritten to slugs. A feature that has shipped with every ticket done is left as it is: the parent ticket's final cleanup commit retires it. Tickets filed on master in the old format after this branch was cut are converted when this ticket's parent merges.

## Acceptance criteria

- [ ] No script under `mx/` reads or writes a ticket file itself: every read and write goes through `tracker` (`ticket-file-contract#P2`).
- [ ] The board renders the converted tracker: parent tickets with their children, the dependency graph by slug, the review pages linked; a before and after of the board is the demo.
- [ ] `dispatch` runs one ticket end to end on a throwaway repo in the new layout: claim, spawn, the `review` flip read from the ticket branch, the review page, the landing.
- [ ] `ticket-file-contract#P4`: the worker's brief and the review's `--spec` come from the same context assembly.
- [ ] `ticket-file-contract#P5`, reviewed: no script branches on a kind of ticket beyond having child tickets and needing the user.
- [ ] Every file under `agent/tickets/` passes `tracker`'s check.

## Comments
