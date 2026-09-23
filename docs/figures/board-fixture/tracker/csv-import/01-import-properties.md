---
status: done
priority: 2
size: S
---

# The import properties, as checks

## Brief

The spec's three properties become tests before anything implements them, so every later slice
lands against a check that already exists and says which slice lifts it.

## What to build

The spec's three properties as property tests at their seams, with a generator
that draws whole statements, and the stubs the seams need so the suite
collects. Each property that cannot hold yet lands as an expected failure
naming the slice that lifts it.

## Acceptance criteria

- [x] a generator that draws whole statements, not raw strings
- [x] `parse_report` and `commit_import` exist as stubs, so the suite collects
- [x] Property P1, executable: at `parse_report`, lifted by `02`
- [x] Property P2, executable: at `parse_report`, lifted by `02`
- [x] Property P3, executable: at `commit_import`, lifted by `04`
