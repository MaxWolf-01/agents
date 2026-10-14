---
status: review
parent: csv-import
blocked-by: [map-columns-to-fields, duplicate-rule]
priority: 1
size: M
---

# Commit the import

## Brief

The slice that finally writes entries, behind a dry run that says what will be added and what will be
skipped, so a re-issued statement never doubles a month of spending. Builds on the duplicate rule as
ruled: same date, payee and amount.

## Acceptance criteria

- [x] csv-import#P3 holds at the account.
- [x] The dry run and the commit agree on every row.

## Questions

- [D1] **Should the dry run name the entry each skipped row matched?** It says how many rows it skips today; naming the match costs a lookup per row and lets you spot a genuine second coffee before committing.

## Comments

**Built on `ticket/commit-the-import`, merged into `csv-import` for its close-out.** Both criteria are met; the dry run reports skipped rows as a count.
