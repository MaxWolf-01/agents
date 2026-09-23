---
status: done
priority: 1
size: M
blocked-by: [03, 05]
---

# Commit the import

## Brief

The slice that finally writes entries, behind a dry run that says what will be added and what will
be skipped, so a re-issued statement never doubles a month of spending.

## What to build

Turn the accepted rows into entries against an account, after a dry run that
says what will be added and what will be skipped as a duplicate.

## Acceptance criteria

- [x] property 3 holds with its expected-failure mark removed
- [x] the dry run and the commit agree on every row
