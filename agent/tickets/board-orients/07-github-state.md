---
status: claimed
blocked-by: [05]
priority: 3
size: XS
---

# Live state on GitHub links

## Brief

A GitHub link on a ticket shows whether its pull request is open, a draft, merged or waiting on changes, or its issue open or closed, without opening it.

Slice of `spec.md`, building on the Decision on GitHub state.

## What to build

The board resolves every `gh` reference in one GraphQL query per render; GitHub gives issues and pull requests one number space per repository, so the board tells them apart without being told. The answer is cached beside the board with a short lifetime, so the watcher makes one request per lifetime rather than one per reference. A link shows its state in its own look and says it in words on hover. No network or no `gh` auth leaves the links bare and says so once on the page.

## Acceptance criteria

- [ ] The no-request-on-an-unchanged-render and render-without-GitHub checks from 01 pass and their annotations are gone.
- [ ] Property, reviewed: every mark on a row explains itself on hover in words.
- [ ] A merged pull request reads as merged without opening it.
- [ ] Demo: a board rendered against real references in two repositories, and the request count for two renders in a row.
