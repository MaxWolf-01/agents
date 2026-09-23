---
status: claimed
blocked-by: [03]
priority: 1
size: S
---

# An opened ticket reads as blocks

## Brief

Opening a row shows the ticket as blocks, not a wall of text: its brief, its questions with their detail, its artefacts, what to build, the acceptance criteria as a checklist, and the comments folded away as history.

Slice of `spec.md`, building on the Decisions on an opened ticket and on artefacts from the show directory.

## What to build

A user opening a row reads, in order: the brief once, the questions each with its detail and answered ones marked answered, the artefacts (the demo's path on a copy button that shows the path, the figures in the ticket's show directory as links), what to build (or the question, for a decision ticket), the acceptance criteria as a checklist, and the comments folded until opened. A build in review shows its branch's text, closing comment included. Nothing declares artefacts in frontmatter; the show directory is read.

## Acceptance criteria

- [ ] Property, reviewed: a copy button shows what it copies.
- [ ] `test_board.py` covers the block order, a folded comments section, and artefacts read from a show directory.
- [ ] Demo: the demo tracker with a build in review and a ticket stopped on a question opened, in both schemes.
