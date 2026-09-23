---
status: review
priority: 1
size: XS
---

# The upload test flakes on a slow disk

## Brief

`test_the_report_keeps_every_line_it_could_not_read` reads back a temp file it has just written and
fails about one run in forty on a loaded machine. Built, and waiting on your ruling.

## Questions

- [D1] **Should anything still cover the parser's file path?** Driving the parser from memory takes the flake out and leaves nothing exercising the path that opens a file; a second test over a committed fixture covers it and costs four seconds in the fast suite.

## What to build

The test drives the parser from memory, with no temp file at all, so nothing in
it depends on how fast the disk is.

## Acceptance criteria

- [x] the test drives the parser from memory, with no temp file at all
