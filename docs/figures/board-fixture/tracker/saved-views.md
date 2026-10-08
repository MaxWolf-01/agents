---
status: claimed
priority: 2
size: L
---

# Save a filtered view

## Brief

The same three filters get retyped every month, and there is no way to hand a colleague the view you
are looking at. This is the whole of keeping one: name the filters, get them back from a list, and
send them by link to anyone on the same account.

## User stories

1. As an account holder, I want to name the filters I am looking at, so that I do not retype them next month.
2. As an account holder, I want to reopen a saved view, so that the same question gets the same answer.
3. As an account holder, I want to send a view to a colleague, so that we are looking at the same rows.
4. As an account holder, I want a reload to keep my filters, so that a stray refresh costs me nothing.

## Properties

- P1 A reopened view restores every filter it was saved with, the date range included.
- P2 A view's link survives a rename of the view.

## Decisions

- A view is a named filter set, not a stored result: two people opening the same link see the same query against the entries as they stand. (you, r1)
- The filter bar's state is one value the page can write, read and compare; saving and sharing are built on it. (my call)
- How the list of views looks is ruled in front of a prototype. (open → view-list-shape)
- Where a filter set is stored. (open → view-storage-research)

## Testing seams

The view store's public API, once `view-storage-research` says what it is, with the filter set that
went in as the oracle; the filter value is tested where the filter bar reads it.

## Out of scope

- Sharing outside the account: the entries are not shared, so a link that crossed accounts would open on nothing.

## Fog

- Whether a view should ever carry a sort as well as filters: nobody has asked for it yet.

## Acceptance criteria

- [ ] Every child ticket is built and merged into this ticket's branch.
- [ ] saved-views#P1 and saved-views#P2 hold on the whole branch.
