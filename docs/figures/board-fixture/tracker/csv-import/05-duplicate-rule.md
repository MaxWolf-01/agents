---
status: done
type: grilling
priority: 1
size: S
blocked-by: [02]
---

# What counts as the same row twice?

## Brief

The duplicate rule decides whether a re-issued statement doubles your month or eats your second
coffee of the day. Which surprise is worse is a judgment, so it was settled with you before `04`
was built.

## Questions

- [D1] **Same date, payee and amount, or a per-row bank id?** The cheap rule eats a second genuine
  coffee on one day; an id only some banks send would behave differently per bank. Answering this
  rewrites the spec's third property and its Testing Decisions.
  - Ruled 2026-02-21: same date, payee and amount.

## Answer

Same date, payee and amount is the rule. The second identical charge on one day is rare and
visible in the dry run, where it can be added by hand; a rule that depends on an id only some
banks send would behave differently per bank, which is worse than a rule that is occasionally
conservative.

The per-row id path is out of scope for this feature, not rejected: it earns a ticket the first
time a bank we use starts sending one.
