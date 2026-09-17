---
status: open
---

# The upload test flakes on a slow disk

## What to build

`test_the_report_keeps_every_line_it_could_not_read` writes its fixture to a
temp file and reads it back without waiting; on a loaded machine it reads an
empty file about one run in forty.

## Acceptance criteria

- [ ] the test drives the parser from memory, with no temp file at all
