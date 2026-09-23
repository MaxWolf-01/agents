---
status: done
type: grilling
blocked-by: [02]
---

# What counts as the same row twice?

## Question

Banks re-issue a statement with the same rows, and two genuine coffees on one
day look identical. Same date, payee and amount is the cheap rule and it eats
the second coffee; a per-row bank id exists at some banks and not others.

Answering this rewrites the spec's third property and its Testing Decisions.

## Answer

Same date, payee and amount is the rule. The second identical charge on one day
is rare and visible in the dry run, where it can be added by hand; a rule that
depends on an id only some banks send would behave differently per bank, which
is worse than a rule that is occasionally conservative.

The per-row id path is out of scope for this feature, not rejected: it earns a
ticket the first time a bank we use starts sending one.
