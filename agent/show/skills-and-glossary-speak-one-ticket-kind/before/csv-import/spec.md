---
status: draft
---

# CSV import

## Problem Statement

Statements arrive as CSV, one layout per bank, and every import is re-mapped by hand.

## Solution

The importer reads a statement, maps its columns to the ledger's fields, and remembers the mapping per bank.

## User Stories

1. As an accountant, I want to import a statement, so that its rows reach the ledger.
2. As an accountant, I want the mapping remembered per bank, so that the second import asks nothing.

## Properties

- P1 A row that fails to map is reported with its line, never dropped.
- P2 Importing the same statement twice leaves the ledger as one import did.

## Decisions

- The mapping is stored per bank, keyed by the statement's header row. (you, r2)
- Duplicate detection compares date, amount and description. (my call)

## Testing Decisions

The seam is `importer.read_statement`, whose oracle is a captured statement and the ledger it should produce.

- P1: executable, over generated statements at that seam.
- P2: reviewed.

## Out of Scope

OFX and QIF, which no bank here exports.
