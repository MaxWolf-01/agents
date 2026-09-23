---
status: open
priority: 3
size: M
blocked-by: [02, csv-import/04]
---

# Share a view by link

## Brief

A link that opens the view for a colleague on the same account, so two people arguing about a
number are looking at the same rows.

## Questions

- [D1] **Does a shared link resolve against the entries now, or the entries when it was sent?** An entry deleted after the link goes out shows the colleague a different set than the sender saw; both surprises are defensible and which one is worse is yours to say.

## What to build

A link that opens the view for someone else on the same account.

## Acceptance criteria

- [ ] the link survives a rename of the view
- [ ] Property P2, reviewed: a view's link survives a rename
- [ ] a view filtered to an imported statement opens on the same entries
