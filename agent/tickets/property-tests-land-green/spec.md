---
status: draft
---

# A property lands before the seam it tests

## Problem Statement

`/mx:to-tickets` puts the ticket that builds a feature's executable Properties first, blocked by nothing and blocking every slice at its seams, so its worker has the spec and the seams' interfaces and never the implementation. Where a Property describes behaviour that does not exist yet, its check fails by construction: on greenfield the seam's module is not there, so the suite does not even collect; at an existing seam that lacks the behaviour, the assertion fails. `/mx:dispatch` lands a ticket only on green. Neither skill says how the two meet, and the one feature that has been dispatched under the new testing skill had no such Property (its checks sat beside a script that already existed). Raised as Q12 in the testing-workflow grilling.

## Solution

The property-tests ticket lands green because each property that cannot hold yet is an **expected failure**: strict, naming the ticket that will lift it, and at a stub tolerating only the not-implemented exception. Where a function or module seam does not exist, the same ticket lands its interface as a **stub** that raises that exception, so the suite collects `(you, r1)`. The slice named by an expected failure makes its property hold and deletes the annotation: the one edit under the properties directory a slice may make. A slice does not land while an expected failure still names it, a strict annotation fails the slice's own run the moment its property passes, and none survives to the feature's PR-ready report. The Tests reviewer reads a strict, named expected failure in the property-tests ticket's diff as the property arriving ahead of its seam; every other skip or expected failure stays the Weakened Test smell.

The stub branch and the existing-seam branch were each run live, kept as the prototype at `agent/prototypes/property-tests-land-green/` (its `ANSWER.md` has the states).

## User Stories

1. As the worker building a feature's property tests, I want a way to land my checks green before the behaviour they test exists, so the ordering that keeps me away from the implementation costs nothing.
2. As the worker building a feature's property tests, I want a bug in my own property at a stubbed seam to fail my run rather than pass as "expected to fail", so the check I hand the slices is one that runs.
3. As the worker of a slice, I want the properties at my seam as my oracle, red until my code is right and red again if I leave their annotations in place, so the slice cannot land with a wrong seam or a stale annotation.
4. As the worker of a slice, I want to know which expected failures are mine without reading every ticket, so lifting them is a grep.
5. As an orchestrator, I want the send-back rule for the properties directory to stay mechanical, so a slice that lifts an expected failure and also loosens the property beside it goes back like any other edit.
6. As an orchestrator, I want a slice whose expected failure is still in place to be red, not a note for later, so no property spends the rest of the feature tolerated.
7. As the Tests reviewer, I want to tell the property-tests ticket's expected failures from a weakened test, so the smell fires on the second and not the first.
8. As max, I want the expected failures gone by the time the feature is PR-ready, so what ships has no test that expects to fail.
9. As max, I want the mechanism's shape in one skill and its Python form in one stack file, so a second language adds a form and not a rule.

## Properties

- A property that cannot hold in the property-tests worker's tree is an expected failure; a property that holds is not.
- Every expected failure is strict and names exactly one ticket; at a stub it tolerates exactly one exception.
- A property is lifted by exactly one ticket.
- The suite is green at every landed ticket; dispatch's green rule has no exception.
- No slice lands while an expected failure in the properties directory names it.
- A slice's only change under the properties directory is the deletion of expected failures naming it.
- No expected failure survives the feature: when the frontier empties, the properties directory holds none.
- No skill prose restates the expected failure's language-specific form; the stack file holds it.

## Decisions

- The property-tests ticket keeps its position: first, blocked by nothing, blocking every slice at its seams `(you, testing-workflow spec)`. Landing it last is the rejected alternative (Out of Scope).
- The annotation is a strict expected failure naming the ticket that lifts it `(you, r2)`. The skills say it in those words; only a stack file names a framework's spelling of it. Strict, so a property that starts passing fails the run until the annotation is deleted. Named, so the slice worker greps its expected failures and the orchestrator checks for them. The glossary word is expected failure; the mark is the provenance tag on a spec call and stays that.
- At a stub the expected failure tolerates only the not-implemented exception, so a wrong implementation and a broken property body both fail rather than pass as expected: the prototype shows a plain strict annotation hiding a bug in the property's own body `(you, r2)`. At a seam that exists without the behaviour, or a wire seam with no route, it tolerates any exception `(my call, review)`: such a seam fails in several ways across the generated space (the prototype's second run: an assertion on some inputs, an index error on others, which Hypothesis reports as one exception group that no single tolerated type matches), so naming one type leaves the property-tests ticket red by construction. The landed-ticket check below is the guard for that branch.
- Where a seam does not exist, its interface lands as a stub that raises the not-implemented exception, transcribed from the spec's Decisions, in the property-tests ticket `(you, r1)`. A stub is what makes the suite collect: a missing module errors at collection, where no mark reaches.
- The slice named by an expected failure makes the property hold and deletes the annotation. Dispatch's send-back rule for the properties directory gains this one exception: a diff under it that is nothing but deleted expected failures naming the ticket merges; anything else goes back unmerged as before `(you, r2)`. The orchestrator applies it in the pre-merge read it already makes `(you, r2)`; a script that classifies the hunks is the upgrade for the first time a read is seen missing an edit.
- A slice does not land while an expected failure names it: the orchestrator greps the properties directory of the ticket branch's tree for the ticket's number, since an annotation the worker never touched is absent from its diff, and a hit goes back to the worker `(my call)`. This is the guard for the existing-seam branch, where the annotation cannot tell a wrong implementation from a missing one.
- None survives the feature: when the frontier empties, the same grep over the feature branch runs before harden, and a hit goes back to the ticket it names `(my call, review)`. A ticket renumbered, split or reset after the annotation was written is never caught by the per-landing check.
- To-tickets assigns each executable property one lifting slice, in the property-tests ticket's body, alongside the seam and the interface it tests; the annotations carry that assignment into code, and the slice reads its own `(my call)`. A property no single slice can make hold is a slicing signal: merge the slices or split the property at the seam; an expected failure never names two tickets.
- The slice worker's instruction lives in `/mx:implement`, since every worker loads it: the expected failures naming your ticket are your oracle; make them hold, then delete them `(my call)`.
- The Weakened Test smell keeps its wording and gains the boundary: a strict expected failure naming its lifter, in the property-tests ticket's own diff, is the property arriving ahead of its seam; any other skip or expected failure is the smell `(my call)`.
- Homes `(my call)`: the shape (what an expected failure is, when a property is one) in `/mx:testing`; the pytest form (`xfail(strict=True, raises=..., reason=...)`, module-level `pytestmark` when a file shares one lifter) in project-setup's `PYTHON.md`; the stub and the property-to-slice assignment in `/mx:to-tickets`; the send-back exception, the landed-ticket check and the frontier-empty check in `/mx:dispatch`; the slice's instruction in `/mx:implement`; the smell boundary in `TEST-SMELLS.md`; the glossary term in `CONTEXT.md`; and one clause in the spec format, so Decisions lists the interfaces of modules to be built as well as modified, which is what a stub is transcribed from.

## Testing Decisions

One seam: the skills, as prose. Every Property is reviewed, by the Spec axis against this document. The mechanism itself is verified by the prototype's run, not by a test in this repo: a test of it would test pytest.

## Out of Scope

- Landing the property-tests ticket last: it gives up the independence the ordering exists for, and it takes the properties away from the slice workers, who are the ones a red property helps.
- A separate suite target that dispatch's green ignores until the seams exist: "until the seams exist" has no mechanical reading, the flip is a human's, and the testing skill has the property tests in the ordinary suite.
- An expected failure whose condition reads the tracker (skip while ticket `NN` is open): it ties test code to the tracker's file layout, and the strict annotation already reports the moment it should go.
- A Node form of the expected failure: no project on that stack has a properties directory yet; the stack file gains one when the first does.
