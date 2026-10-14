---
status: done
parent: csv-import
hinge: true
priority: 1
size: M
---

# Upload a statement and see what it read

## Brief

The first slice an account holder can drive: a CSV goes in and a report comes back, naming every line
the mapping could not read. Nothing is stored yet, so a wrong mapping costs nothing. A hinge: the
mapping and the commit both read the report's shape.

## Acceptance criteria

- [x] A line the mapping cannot read is reported with its number and its reason, never dropped.
- [x] csv-import#P1 and csv-import#P2 hold at the parse report.

## Comments

**Built on `ticket/upload-and-parse-report`, merged into `csv-import` on your ruling of 2026-09-17.**
