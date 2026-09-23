---
status: claimed
type: research
priority: 2
size: S
---

# Where does a saved view live?

## Brief

Everything else in this feature waits on one storage answer: whether a filter set is a column the
database can query into or a table of its own, and what each costs once a view is shared.

## What to build

What each of the two stores costs when a view is shared, read out of the database's own docs and
whatever the codebase already does with filters. The answer rewrites the spec's Decisions and its
Testing Decisions, and nothing here waits on you until it lands.
