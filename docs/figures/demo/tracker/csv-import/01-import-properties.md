---
status: done
---

# The import properties, as checks

## What to build

The spec's three properties as property tests at their seams, with a generator
that draws whole statements, and the stubs the seams need so the suite
collects. Each property that cannot hold yet lands as an expected failure
naming the slice that lifts it.

## Acceptance criteria

- [x] a generator that draws whole statements, not raw strings
- [x] `parse_report` and `commit_import` exist as stubs, so the suite collects
- [x] properties 1 and 2 name `02`, property 3 names `04`
