---
status: draft
---

# A property lands before the seam it tests

## Problem Statement

`/mx:to-tickets` puts the ticket that builds a feature's executable Properties first, blocked by nothing and blocking every slice at its seams, so its worker has the spec and the seams' interfaces and never the implementation. Where a Property describes behaviour that does not exist yet, its check fails by construction: on greenfield the seam's module is not there, so the suite does not even collect; at an existing seam that lacks the behaviour, the assertion fails. `/mx:dispatch` lands a ticket only on green. Neither skill says how the two meet, and the one feature that has been dispatched under the new testing skill had no such Property (its checks sat beside a script that already existed). Raised as Q12 in the testing-workflow grilling; the ticket that carried it is absorbed here.

## Solution

The property-tests ticket lands green because each property that cannot hold yet carries a **mark**: a strict expected failure that tolerates only the one exception the seam's absence produces, and names the ticket that will lift it. Where the seam does not exist, the same ticket lands its interface as a **stub** that raises the not-implemented exception, so the suite collects and the mark has something to tolerate `(you, r1)`. The slice named by a mark makes its property hold and deletes the mark: the one edit under the properties directory a slice may make. A slice does not land while a mark still names it, and a strict mark fails the slice's own run the moment its property passes, so forgetting is red. The Tests reviewer reads a strict, named mark in the property-tests ticket's diff as the property arriving ahead of its seam; every other skip or expected failure stays the Weakened Test smell.

Verified once on a live run, kept as the prototype at `agent/prototypes/property-tests-land-green/` (its `ANSWER.md` has the six states).

## User Stories

1. As the worker building a feature's property tests, I want a way to land my checks green before the behaviour they test exists, so the ordering that keeps me away from the implementation costs nothing.
2. As the worker building a feature's property tests, I want a bug in my own property to fail my run rather than pass as "expected to fail", so the check I hand the slices is one that runs.
3. As the worker of a slice, I want the properties at my seam as my oracle, red until my code is right and red again if I leave their marks in place, so the slice cannot land with a wrong seam or a stale mark.
4. As the worker of a slice, I want to know which marks are mine without reading every ticket, so lifting them is a grep.
5. As an orchestrator, I want the send-back rule for the properties directory to stay mechanical, so a slice that lifts a mark and also loosens the property beside it goes back like any other edit.
6. As an orchestrator, I want a slice that landed with its mark still in place to be red, not a note for later, so no property spends the rest of the feature tolerated.
7. As the Tests reviewer, I want to tell the property-tests ticket's marks from a weakened test, so the smell fires on the second and not the first.
8. As max, I want the marks gone by the time the feature is PR-ready, so what ships has no test that expects to fail.
9. As max, I want the mechanism's shape in one skill and its Python form in one stack file, so a second language adds a form and not a rule.

## Properties

- A property that cannot hold in the property-tests worker's tree carries a mark; a property that holds carries none.
- Every mark is strict, tolerates exactly one exception, and names exactly one ticket.
- A property is lifted by exactly one ticket.
- The suite is green at every landed ticket; dispatch's green rule has no exception.
- No slice lands while a mark in the properties directory names it.
- A slice's only change under the properties directory is the deletion of marks naming it.
- No mark survives the feature: when the frontier empties, the properties directory holds none.
- No skill prose restates the mark's language-specific form; the stack file holds it.

## Decisions

- The property-tests ticket keeps its position: first, blocked by nothing, blocking every slice at its seams `(you, testing-workflow spec)`. Landing it last is the rejected alternative (Out of Scope).
- The mark is a strict expected failure that tolerates one exception and names the ticket that lifts it `(you, r2)`. The skills say it in those words; only a stack file names a framework's spelling of it. Strict, so a property that starts passing fails the run until the mark is deleted. One tolerated exception, so a wrong implementation and a broken property body both fail rather than pass as expected: the prototype shows a plain strict mark hiding a bug in the property's own body. Named, so the slice worker greps its marks and the orchestrator checks for them.
- The tolerated exception is the one the seam's absence produces: the not-implemented exception where the seam is a stub, the assertion failure where the seam exists and lacks the behaviour `(my call)`. The second is weaker: a wrong implementation at an existing seam fails the same way the missing behaviour did, so the mark hides it until the landed-ticket check below.
- Where a seam does not exist, its interface lands as a stub that raises the not-implemented exception, transcribed from the spec's Decisions, in the property-tests ticket `(you, r1)`. A stub is what makes the suite collect: a missing module errors at collection, where no mark reaches.
- The slice named by a mark makes the property hold and deletes the mark. Dispatch's send-back rule for the properties directory gains this one exception: a diff under it that is nothing but deleted marks naming the ticket merges; anything else goes back unmerged as before `(you, r2)`. The orchestrator applies it in the pre-merge read it already makes `(you, r2)`; a script that classifies the hunks is the upgrade for the first time a read is seen missing an edit.
- A slice does not land while a mark names it: the orchestrator's landing step checks the properties directory for the ticket's number, and a hit is red `(my call)`. This is the guard for the existing-seam case, where the mark cannot tell a wrong implementation from a missing one.
- To-tickets assigns each executable property one lifting slice, in the property-tests ticket's body, alongside the seam and the interface it tests; the marks carry that assignment into code, and the slice reads its marks `(my call)`. A property no single slice can make hold is a slicing signal: merge the slices or split the property at the seam; a mark never names two tickets.
- The slice worker's instruction lives in `/mx:implement`, since every worker loads it: the marks naming your ticket are your oracle; make them hold, then delete them `(my call)`.
- The Weakened Test smell keeps its wording and gains the boundary: a strict mark tolerating one exception and naming its lifter, in the property-tests ticket's own diff, is the property arriving ahead of its seam; any other skip or expected failure is the smell `(my call)`.
- Homes `(my call)`: the shape (a property ahead of its seam carries a mark; what a mark is) in `/mx:testing`; the pytest form (`xfail(strict=True, raises=..., reason=...)`, module-level `pytestmark` when a file shares one lifter) in project-setup's `PYTHON.md`; the stub and the property-to-slice assignment in `/mx:to-tickets`; the send-back exception and the landed-ticket check in `/mx:dispatch`; the slice's instruction in `/mx:implement`; the smell boundary in `TEST-SMELLS.md`.

Deferrals: none.

## Testing Decisions

One seam: the skills, as prose. Every Property is reviewed, by the Spec axis against this document. The mechanism itself is verified by the prototype's run, not by a test in this repo: a test of it would test pytest.

## Out of Scope

- Landing the property-tests ticket last: it gives up the independence the ordering exists for, and it takes the properties away from the slice workers, who are the ones a red property helps.
- A separate suite target that dispatch's green ignores until the seams exist: "until the seams exist" has no mechanical reading, the flip is a human's, and the testing skill has the property tests in the ordinary suite.
- A mark whose condition reads the tracker (skip while ticket `NN` is open): it ties test code to the tracker's file layout, and the strict mark already reports the moment it should go.
- A Node form of the mark: no project on that stack has a properties directory yet; the stack file gains one when the first does.

## Fog

None.
