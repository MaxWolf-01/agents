---
status: confirmed
---

# Save a filtered view

## Problem Statement

The same three filters get retyped every month, and there is no way to hand a
colleague the view you are looking at.

## Solution

Name the filters you are looking at and get them back from a list. A saved view
opens by link for anyone on the same account.

## User Stories

1. As an account holder, I want to name the filters I am looking at, so that I
   do not retype them next month.
2. As an account holder, I want to reopen a saved view, so that the same
   question gets the same answer.
3. As an account holder, I want to send a view to a colleague, so that we are
   looking at the same rows.

## Properties

- A reopened view restores every filter it was saved with, including the dates.
- A view's link survives a rename.

## Decisions

- A view is a named filter set, not a stored result: two people opening the same
  link see the same query against the entries as they stand.
- Where the filter set is stored is the one open question; `01` answers it.

## Testing Decisions

One seam, the view store's public API, once `01` says what it is. The oracle is
the filter set that went in.

- A reopened view restores every filter: **executable**, at the store's API.
- A link survives a rename: **reviewed**, checked against each diff.

## Out of Scope

- Sharing outside the account: the entries themselves are not shared, so a link
  that crossed accounts would open on nothing.
