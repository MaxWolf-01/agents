---
status: open
type: grilling
---

# How the property-tests ticket lands green before its seams exist

`/mx:to-tickets` puts the ticket that builds a feature's executable Properties first, blocked by nothing, so its worker never sees the implementation. On greenfield work its checks call seams that are still stubs, so the ticket is red by construction, and `/mx:dispatch` lands a ticket only on green. Neither skill says how that resolves.

## Question

- Do the checks land marked expected-to-fail, strict, one mark per seam naming the slice that lifts it, so a slice that forgets to lift its mark fails its own run and the Weakened Test smell gets that one exception?
- Or does the ticket land last, after every slice at its seams, giving up the independence the ordering was chosen for?
- Or something outside both: a separate suite target that dispatch's green ignores until the seams exist?

Raised as Q12 in the testing-workflow grilling; recommendation at the time was the first.
