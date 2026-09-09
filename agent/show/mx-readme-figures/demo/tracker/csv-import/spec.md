---
status: confirmed
---

# Import a bank statement

## Problem

Entries are typed in by hand, so a month of spending takes an evening and the
numbers drift from the bank's.

## Solution

Upload a CSV, map its columns onto date, payee and amount once per bank, see
every line the mapping could and could not read, and commit the import.

## Properties

- Every accepted row carries a date, a payee and an integer amount in cents.
- A line is either accepted or reported, never both and never neither.
- Importing the same statement twice adds no entry the second time.

## Testing decisions

The three properties above are **executable**, at the `parse_report` and
`commit_import` seams; they build ahead of the slices, from this spec.
