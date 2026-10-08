---
status: done
parent: csv-import
needs-user: true
priority: 1
size: S
---

# Settle the duplicate rule

## Brief

The duplicate rule decides whether a re-issued statement doubles your month or eats your second coffee
of the day. Which surprise is worse is a judgment, so it is settled with you before the commit is built.

## Acceptance criteria

- [x] The rule is written into the parent ticket's Decisions, and csv-import#P3 reads against it.

## Questions

- [D1] **Same date, payee and amount, or a per-row bank id?** The cheap rule eats a second genuine coffee on one day; an id only some banks send would behave differently per bank.
  - Ruled 2026-09-16: same date, payee and amount; the per-row id earns a ticket the first time a bank we use sends one.
