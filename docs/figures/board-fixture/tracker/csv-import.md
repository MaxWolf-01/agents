---
status: review
priority: 1
size: L
---

# Import a bank statement

## Brief

Entries are typed in by hand, so a month of spending takes an evening and the numbers drift from the
bank's without anyone noticing which side is wrong. This is the whole of reading the bank's CSV in
instead: upload it, see every line it could and could not read, and commit the accepted ones.

## User stories

1. As an account holder, I want to upload my bank's CSV, so that a month of spending does not have to be typed in.
2. As an account holder, I want to see which lines could not be read and why, so that I can fix the mapping instead of losing the rows.
3. As an account holder, I want the mapping remembered per bank, so that the next statement arrives already mapped.
4. As an account holder, I want a dry run before the import, so that I can see what will be added and what will be skipped.
5. As an account holder, I want a re-issued statement to add nothing, so that my entries do not double.

## Properties

- P1 Every accepted row carries a date, a payee and an integer amount in cents.
- P2 A line of the statement is either accepted or reported with its reason, never both and never neither.
- P3 Importing the same statement twice adds no entry the second time.

## Decisions

- The importer owns parsing and the report; the account owns entries. They meet at the parse report, which carries the accepted rows and the rejected lines together, so the screen can show one upload whole. (you, r1)
- Amounts are integer cents, as the glossary's Entry is: a float would round one way on the way in and another on the way out. (you, r1)
- A mapping is a plain column-to-field table, kept per bank and corrected on the report screen. (my call)
- A row is the same row twice when its date, payee and amount match. (you, duplicate-rule)

## Testing seams

One seam, the parse report, the highest point that still reaches parsing; the commit is tested at the
account, for the duplicate rule. The oracle is the statements in the fixtures and the properties above,
never the parser's own output.

## Out of scope

- OFX and QIF: every bank we use gives CSV, and a second parser doubles the surface the properties have to hold across.
- Currency conversion: an account holds one currency.

## Acceptance criteria

- [x] Every child ticket is built and merged into this ticket's branch.
- [x] The full suite is green on the branch, and the close-out review has read the whole tree.
- [ ] You have driven an import of a real statement end to end.

## Comments

**Closed out 2026-09-24, on `csv-import`, not merged.** All four child tickets are in, the suite is
green, and the review one level up found one gap: nothing tested the dry run's already-settled branch,
fixed on the branch. The close-out filed `blank-column-reason`.
