---
status: done
blocked-by: [03, 05]
---

# Commit the import

## What to build

Turn the accepted rows into entries against an account, after a dry run that
says what will be added and what will be skipped as a duplicate.

## Acceptance criteria

- [x] property 3 holds with its expected-failure mark removed
- [x] the dry run and the commit agree on every row
