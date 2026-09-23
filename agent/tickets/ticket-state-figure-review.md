---
status: proposed
priority: 3
size: XS
blocked-by: [figures-and-demos/04]
---

# The README's ticket-state figure shows the review state

## Brief

The README's ticket-state figure draws `done` as the worker's flip, the reading the review status retired, and its alt text lists four statuses where the tracker has five. Its three labels for the needs-human queue go the same way, since this feature retired it.

Cut from the review of [A `review` status: a build waiting for the user's ruling has its own state and its own group on the board](review-status.md): the figure still draws `done` as the worker's flip, the reading that ticket retired, and its alt text lists four statuses where the tracker has five. Filed rather than fixed there because the figures-and-demos feature is moving the figure pipeline while its ticket 04 waits for a ruling: the figure is edited once, at its new home.

## What to build

Add `review` between `claimed` and `done` in the ticket-state figure's source (`docs/figures/ticket-state.html` once figures-and-demos 04 has landed): the worker's last act writes it, `dispatch review` flips the feature branch's copy, and the user's accept writes `done` through the merge. Re-render both schemes with the pipeline's renderer and update the alt text in `mx/README.md`.

## Acceptance criteria

- [x] The figure names every status the tracker knows, with one writer per transition, and its alt text lists them.
- [x] Both PNGs under `mx/assets/` are re-rendered from the edited source.
- [x] Demo in the closing comment: the rendered figure, light and dark.

## Comments

**2026-09-23, board-orients 11** Built on `ticket/board-orients/11-readme-figures`, unmerged. That
ticket's brief takes this one together with its own edit of the same figure, so the source is
edited once: `review` joins the chain between claimed and done, the needs-human queue card becomes
a ticket's own `## Questions`, a third board panel names what a row asks of you, and both PNGs are
re-rendered. The figure light and dark, before and after, is the second half of
`agent/show/board-orients/11-readme-figures/figure.html`. Ruling on 11 rules on this; the status
stays `proposed` because the work sits on another ticket's branch rather than one of its own.
