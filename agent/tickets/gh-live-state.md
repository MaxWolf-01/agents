---
status: proposed
blocked-by: [review-status]
---

# A `gh` link on the board carries the state of what it points at

Cut from [A `review` status: a build waiting for the user's ruling has its own state and its own group on the board](review-status.md), which renders a ticket's `gh` references as links and leaves their state to this ticket: the user's reading of a board is "this ticket maps onto these PRs and issues, and they stand thus", and a bare link makes them open each one to learn the second half.

## What to build

The board resolves each `gh` reference and shows its state on the chip: a pull request open, draft, changes requested or merged; an issue open or closed. GitHub gives issues and pull requests one number space per repository and one API endpoint, so the renderer tells them apart without being told. The lookups go out as one GraphQL query per render, and the answer is cached beside the board with a short lifetime, so the watch loop's two-second cadence makes one request rather than one per reference; no network, or no `gh` auth, leaves the chip a bare link and says so once on the page.

## Acceptance criteria

- [ ] A chip shows the state of what it points at, and a merged pull request reads as merged without opening it.
- [ ] One render makes at most one request to GitHub, and a render within the cache's lifetime makes none.
- [ ] Offline, the board still renders and the chips fall back to bare links.
- [ ] Demo in the closing comment: a board rendered against real references in two repositories, and the request count for two renders in a row.
