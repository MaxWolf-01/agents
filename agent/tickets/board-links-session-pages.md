---
status: proposed
parent: session-page
blocked-by: [session-renderer, spec-page-renderer]
priority: 3
size: XS
---

# The board links each listed session's page and each feature's spec page

## Brief

The board links each listed session's page and each feature's spec page, where one has been rendered.

Slice of `session-page`, building on its Decisions under Around it: the board, and the build starting once `board-orients` has merged.

## What to build

On the board as `board-orients` rebuilds it, which lists the sessions that touched a ticket (from `Session:` commit trailers) with a button copying the resume command: each listed session whose session page exists gets a link opening it, and each feature's row links its spec page when one has been rendered. A session with no page, or a feature with no rendered spec page, shows no link. Starts only after `board-orients` has merged into the integration branch.

## Acceptance criteria

- [ ] At the board's loader seam: a session with a page carries its link, one without carries none; a feature with a rendered spec page carries its link, one without carries none.
- [ ] The links follow `board-orients`' rules for marks: each explains itself on hover, and a copy control shows what it copies.
- [ ] Demo: the board rendered from a fixture tracker with one session page and one spec page, opened, both links followed.
