---
name: testing
description: "Use when writing or changing tests, deciding what a piece of work should test or which checks a change has to pass, or when another skill routes testing here: the job a test does, the seam it enters at, the oracle its expectations come from, inputs that can discriminate a bug."
---

# Testing

A test earns its place by one of three jobs:

1. **It holds a behaviour the user relies on**, at a seam the next agent will touch, so that agent's change cannot break it unnoticed. It states the behaviour, never the bytes or the internals: a test that fails on a refactor that kept the behaviour is a defect of the test.
2. **It is the regression test for a bug that reached the user or a live run.** A bug a reviewer only imagined earns no test.
3. **It states an invariant of a seam**, as a property test, where stating it is how the seam gets clear.

A test doing none of them is deleted. A new test is seen red before it is kept: run before the code that makes it pass, or, where that code came first, run once with it broken on purpose. A test that flakes is fixed or deleted the day it flakes: a suite that sometimes fails for no reason gets rerun until it passes, and its failures stop being read.

Test names carry the domain's words, as the project's `GLOSSARY.md` has them.

## Two kinds of run

**The fast suite** is `make test`: it touches nothing outside the checkout and a scratch directory of its own, with no browser, desktop, network or sleeps. A test that runs the project's own script as a subprocess in that scratch directory belongs in it. It runs on every change, and the three jobs live in it.

**Full-path checks** drive the real thing end to end: a browser on the page, tmux, the real desktop, the paid API, the VPN. They stay out of `make test`, behind a target of their own (`make test-full-path`), and run deliberately, on a host that has what they drive: before a release, and on a change that reaches their path. A change reaches the full-path checks in the test files that exercise what it touched.

## Coverage

Where the project measures it (`make coverage`), a change reaches its review with every line the fast suite can run, run. A line no clean, fast test reaches is a finding about the code: the time, network, disk or process it reaches for is passed in, however large that refactor is. An exclusion is for a line the measurement cannot see, and names the test that holds it.

## The seam

A **seam** is where a test enters the system: a function, a module's public API, an endpoint, the browser. Where nothing names one for the work in hand, propose the highest seam that still reaches the behaviour and confirm it before writing. Fewer seams across a codebase is better. `/mx:codebase-design` holds the vocabulary for arguing about where one belongs.

Logic inside a decorated entry point (a route handler, a CLI command, a scheduled task) is testable, by calling it directly or driving the framework's test client, but every test of it pays that setup. Put the logic in a plain function the entry point calls, and test that.

Mock what the module does not own: the network, the clock, randomness, an external service. A test that mocks the module's own collaborators is testing the mock.

## The oracle

Every expected value comes from outside the implementation: a sentence of the ticket, a worked example, a known-good literal, an independent simpler computation, or a property that must hold whatever the input. An expectation recomputed the way the code computes it agrees with the code by construction, including when both are wrong.

## Property tests

A slice writes one where a generator over the seam's inputs beats hand-picked examples. An invariant the code already asserts is a property with its oracle written, and a generator over its inputs turns it into a test.

The repertoire, by name and not as its boundary: property and metamorphic tests, model-based tests (a small reference model as the oracle), differential tests against the previous version, deterministic simulation (time and I/O behind an interface, every run from one seed), mutation to see a test fail. Reach for the lightest one that can falsify the claim.

An invariant that cannot be stated cleanly, or whose test needs heavy fakes, is a sign the seam is wrong: a finding for `/mx:improve-codebase-architecture`, not a reason for more test code. A ticket's Properties are prose the reviewer checks each diff against, and turn into checks only by this route.

## The inputs

Choose inputs that can tell the bug from the fix. An input symmetric in the dimension under test (a palindrome for a reversal, four identical streams for a four-stream feature, an empty collection for an ordering rule) passes whether or not the code works.

Generate structure rather than raw randomness: draw whole valid values of the domain (a note, an order, a request), so the generator explores the space the code actually meets. Unstructured random input lands on the rejection path almost every time, and a run that always rejects proves the validator, not the feature.

## The suite already there

Extend it: its fixtures, its helpers, its naming, its seams. A second parallel suite beside the first splits the signal, and the next agent has to read both to know what is covered.
