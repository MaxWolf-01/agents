---
status: open
parent: saved-views
blocked-by: [save-and-reopen-a-view, commit-the-import]
priority: 3
size: M
---

# Share a view by link

## Brief

A link that opens the view for a colleague on the same account, so two people arguing about a number
are looking at the same rows. Waits on the import too: a view filtered to one imported statement is
the case the link exists for.

## Acceptance criteria

- [ ] saved-views#P2: the link opens the same view after a rename.
- [ ] A view filtered to an imported statement opens on the same entries for the colleague.

## Questions

- [D1] **Does a shared link resolve against the entries now, or the entries when it was sent?** An entry deleted after the link goes out shows the colleague a different set than the sender saw; both surprises are defensible and which is worse is yours to say.
