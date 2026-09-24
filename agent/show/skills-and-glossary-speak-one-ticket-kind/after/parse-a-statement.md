---
status: proposed
parent: csv-import
priority: 2
size: M
---

# Parse a statement into ledger rows

## Brief

Reading one bank's CSV and writing its rows to the ledger, building on the seam the parent ticket's Testing seams names.

## Acceptance criteria

- [ ] `csv-import#P1` holds at that seam: a row that fails to map is reported with its line.
- [ ] A second import of one file leaves the ledger as the first did.

## Comments
