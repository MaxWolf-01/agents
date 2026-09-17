---
status: confirmed
---

# Import a bank statement

## Problem Statement

Entries are typed in by hand, so a month of spending takes an evening, and the
numbers drift from the bank's without anyone noticing which is wrong.

## Solution

Upload the bank's CSV. Say once per bank which column is the date, the payee
and the amount. See every line the mapping could and could not read, then
commit the accepted ones as entries.

## User Stories

1. As an account holder, I want to upload my bank's CSV, so that a month of
   spending does not have to be typed in.
2. As an account holder, I want to see which lines could not be read and why,
   so that I can fix the mapping instead of losing the rows.
3. As an account holder, I want the mapping remembered per bank, so that the
   next statement arrives already mapped.
4. As an account holder, I want a dry run before the import, so that I can see
   what will be added and what will be skipped.
5. As an account holder, I want a re-issued statement to add nothing, so that
   my entries do not double.

## Properties

- Every accepted row carries a date, a payee and an integer amount in cents.
- A line is either accepted or reported, never both and never neither.
- Importing the same statement twice adds no entry the second time.

## Decisions

- The importer owns parsing and reports; the account owns entries. They meet at
  `parse_report`, which returns the accepted rows and the rejected lines
  together, so the screen can show one upload whole.
- Amounts are integer cents. A float amount would round differently on the way
  in and on the way out, and the glossary's Entry is an integer amount.
- The mapping is a plain column-name-to-field dict, kept per bank.

## Testing Decisions

One seam: `parse_report`, the highest point that still reaches parsing, plus
`commit_import` for the duplicate rule. The oracle is this spec's Properties
and the statements in the fixtures, never the parser's own output.

- Every accepted row carries a date, a payee and an amount: **executable**, at
  `parse_report`.
- A line is either accepted or reported: **executable**, at `parse_report`.
- The same statement twice adds no entry: **executable**, at `commit_import`.

## Out of Scope

- OFX and QIF: every bank we have gives CSV, and a second parser doubles the
  surface the properties have to hold across.
- Currency conversion: an account holds one currency, decided in `decisions/`.
