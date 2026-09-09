---
status: done
---

# The import properties, as checks

## What to build

The spec's three properties as property tests at their seams, plus the stubs
they need to collect. Two hold once the parse report exists; the third names
the slice that lifts it.

## Acceptance criteria

- [x] a generator that draws whole statements, not raw strings
- [x] each property that cannot hold yet is a strict expected failure naming its slice
