---
status: review
---

# to-tickets checks that every spec Property lands in some slice's criteria

Cut from the whole-feature review of one-flow (Spec axis, A1): the spec disposes every Property as *reviewed*, which makes the slices' acceptance criteria the place a property is checked, and seven of one-flow's fifteen Properties reached no slice. Twelve `Property, reviewed` criteria exist across tickets 01 to 08: one names something that is not a spec Property, one Property is claimed twice, and four (reads cold, the landing-message shape, the per-slice review page, the unratified-call chain) were left to nobody. All seven hold on the branch, and two of the pass's confirmed defects sit inside that gap.

## What to build

`/mx:to-tickets` ends with a check a script can run: every Property in the spec's `## Properties` is named by at least one ticket's acceptance criteria, and every `Property, reviewed` criterion quotes a Property that exists. Where a property genuinely belongs to no single slice, the breakdown says so in the same place rather than leaving it absent, since an absent property and an unsliceable one read the same today.

## Acceptance criteria

- [ ] A breakdown whose slices miss a Property fails the check, naming the property.
- [ ] A criterion naming a property the spec does not have fails it too.
- [ ] The check runs where to-tickets publishes, and the skill says the breakdown is not finished until it passes.
- [ ] Demo in the closing comment: the check run against one-flow's own spec and tickets, before and after.
