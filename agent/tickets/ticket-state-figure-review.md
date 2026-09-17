---
status: proposed
blocked-by: [figures-and-demos/04]
---

# The README's ticket-state figure shows the review state

Cut from the review of [A `review` status: a build waiting for the user's ruling has its own state and its own group on the board](review-status.md): the figure still draws `done` as the worker's flip, the reading that ticket retired, and its alt text lists four statuses where the tracker has five. Filed rather than fixed there because the figures-and-demos feature is moving the figure pipeline while its ticket 04 waits for a ruling: the figure is edited once, at its new home.

## What to build

Add `review` between `claimed` and `done` in the ticket-state figure's source (`docs/figures/ticket-state.html` once figures-and-demos 04 has landed): the worker's last act writes it, `dispatch review` flips the feature branch's copy, and the user's accept writes `done` through the merge. Re-render both schemes with the pipeline's renderer and update the alt text in `mx/README.md`.

## Acceptance criteria

- [ ] The figure names every status the tracker knows, with one writer per transition, and its alt text lists them.
- [ ] Both PNGs under `mx/assets/` are re-rendered from the edited source.
- [ ] Demo in the closing comment: the rendered figure, light and dark.
