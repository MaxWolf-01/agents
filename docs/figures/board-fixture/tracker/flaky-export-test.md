---
status: review
priority: 1
size: XS
---

# Steady the export test

## Brief

`test_export_round_trip` writes the export to a temp file and reads it back without waiting for the
write; on a loaded machine it reads an empty file about one run in forty, and a red suite stops every
dispatch wave behind it.

## Acceptance criteria

- [x] No test of the export touches the filesystem.
- [x] The test passes a hundred runs in a row under a loaded disk.

## Questions

- [D1] **Should anything still cover writing the export to a file?** Exporting into memory takes the flake out and leaves nothing exercising the file path; a second test over a temp directory covers it and costs two seconds in the fast suite.

## Comments

**Built on `ticket/flaky-export-test`, not merged.** Both criteria are met: `agent/show/flaky-export-test/rerun-under-load` runs the test a hundred times against a busy disk, and the run is clean.
