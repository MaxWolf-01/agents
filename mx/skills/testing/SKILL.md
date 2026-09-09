---
name: testing
description: "What makes a test worth keeping: the seam it enters at, the oracle its expectations come from, inputs that can discriminate a bug. Use when writing or changing tests, when deciding what a piece of work should test, or when another skill routes testing work here."
---

# Testing

A suite does two separable jobs: it **holds code in place** (a change in behaviour fails a test) and it **tells code is wrong** (the implementation disagrees with something outside it). The second needs an **oracle** independent of the implementation, and that is where a suite is usually thin. Write code and tests in whichever order the work wants.

Read `CONTEXT.md` if the project has one, so test names carry the domain's words, and respect ADRs in the area you touch.

## The seam

A **seam** is where a test enters the system: a function, a module's public API, an endpoint, the browser. The spec's Testing Decisions names the seams for the work in hand; where nothing names one, propose the highest seam that still reaches the behaviour and confirm it before writing. Fewer seams across a codebase is better. `/mx:codebase-design` holds the vocabulary for arguing about where one belongs.

Logic that sits inside a decorated entry point (a route handler, a CLI command, a scheduled task) is reachable by neither a test nor a mutation tool: put it in a plain function the entry point calls, and test the plain function.

Mock what the module does not own: the network, the clock, randomness, an external service. A test that mocks the module's own collaborators is testing the mock.

## The oracle

Every expected value comes from outside the implementation: a spec sentence, a worked example, a known-good literal, an independent simpler computation, or a property that must hold whatever the input. An expectation recomputed the way the code computes it agrees with the code by construction, including when both are wrong.

Properties are the cheapest oracle to state: a spec Property already says what must always or never hold, so it becomes a check over generated inputs at its seam rather than a sentence somebody re-reads.

## The inputs

Choose inputs that can tell the bug from the fix. An input symmetric in the dimension under test (a palindrome for a reversal, four identical streams for a four-stream feature, an empty collection for an ordering rule) passes whether or not the code works.

Generate structure rather than raw randomness: draw whole valid values of the domain (a note, an order, a request), so the generator explores the space the code actually meets. Unstructured random input lands on the rejection path almost every time, and a run that always rejects proves the validator, not the feature.

Property tests live in the project's properties directory and run in the ordinary suite.

## The suite already there

Extend it: its fixtures, its helpers, its naming, its seams. A second parallel suite beside the first splits the signal, and the next agent has to read both to know what is covered.

`make harden` measures what a feature's tests fail to hold, once per feature, at the review session (`/mx:dispatch`). The script beside this skill is what it runs, and `uv run harden.py --help` is the reference for what it measures and what its report means.
