---
status: open
priority: 2
size: L
---

# CSV import

## Brief

Statements arrive as CSV, one layout per bank, and every import is re-mapped by hand. The importer reads a statement, maps its columns to the ledger's fields, and remembers the mapping per bank.

## User stories

1. As an accountant, I want to import a statement, so that its rows reach the ledger.
2. As an accountant, I want the mapping remembered per bank, so that the second import asks nothing.

## Properties

- P1 A row that fails to map is reported with its line, never dropped.
- P2 Importing the same statement twice leaves the ledger as one import did.

## Decisions

- The mapping is stored per bank, keyed by the statement's header row. (you, r2)
- Duplicate detection compares date, amount and description. (my call)

## Testing seams

The seam is `importer.read_statement`, whose oracle is a captured statement and the ledger it should produce.

- P1: executable, over generated statements at that seam.
- P2: reviewed.

## Out of scope

OFX and QIF, which no bank here exports.

## Acceptance criteria

- [ ] Every child ticket is done, and this ticket's close-out is ruled.

## Comments
