---
status: review
priority: 1
size: XS
---

# The upload test flakes on a slow disk

## Brief

`test_the_report_keeps_every_line_it_could_not_read` writes its fixture to a temp file and reads it
back without waiting; on a loaded machine it reads an empty file about one run in forty.

## Questions

- [D1] **Should anything still cover the parser's file path?** Driving the parser from memory takes
  the flake out and leaves nothing exercising the path that opens a file; a second test over a
  committed fixture covers it and costs four seconds in the fast suite.

## What to build

The test drives the parser from memory, so nothing in it depends on how fast the disk is.

## Acceptance criteria

- [x] no test of the report touches the filesystem

## Comments

**Built on `ticket/flaky-upload-test`, not merged.** The demo is `agent/show/flaky-upload-test/demo`:
it runs the report test a hundred times under a loaded disk and the run is clean.
