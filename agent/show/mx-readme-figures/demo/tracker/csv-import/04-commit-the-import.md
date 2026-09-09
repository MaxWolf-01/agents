---
status: open
blocked-by: [03, 05]
---

# Commit the import

## What to build

Turn the accepted rows into entries against an account, after a dry run that
says what will be added and what will be skipped as a duplicate.

## Acceptance criteria

- [ ] the duplicate property holds with its expected-failure mark removed
- [ ] the dry run and the commit agree on every row
