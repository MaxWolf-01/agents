---
status: proposed
---

# The row-limit guard is untested

Cut from the harden report for this feature: the guard that stops an upload
past 20k rows survives every mutant, so no test tells it from its absence. A
test at the parse seam pins it; worth a ticket because the limit is the only
thing standing between an upload and the request timeout.

## Acceptance criteria

- [ ] a statement one row over the limit is refused, with the limit in the message
