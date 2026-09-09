---
status: done
blocked-by: [01]
---

# Upload a statement and see what it read

## What to build

Upload a CSV and get a report: the rows that parsed, and every line that did
not, with its number and the reason. Nothing is stored yet.

## Acceptance criteria

- [x] a line the mapping cannot read is reported, never dropped
- [x] the two parse properties hold with their expected-failure marks removed
