---
status: confirmed
---

# Testing in the workflow

## Problem Statement

Agents test badly by default, and telling them how does not help. Luu's 26-condition eval (danluu.com/agentic-testing, Sep 2026: Zstd in Rust, 80 runs per condition, scored on hidden tests) found that naming a technique ("use TDD", "use property-based testing", "use mutation testing") leaves the agent writing its usual unit tests inside the named framework; the TDD prompt doubled the test count and lowered correctness; tutorial-shaped testing skills scored below no instruction and raised cost. What the agents' tests missed was the same every time: inputs that cannot discriminate the bug (four identical bitstreams for a four-stream feature, a palindrome for a reversal), expected values copied from the implementation, random inputs that all hit the rejection path, and mocks of the module's own collaborators.

The workflow today does what the eval says not to do: `/mx:tdd` prescribes red-green as the loop, its reference files are tutorials, and nothing then checks what the tests can catch. `make test` proves the tests pass; the reviewer's smell baseline has no entry for tests; the spec's Properties, the human-written list of what must always and never hold, are checked by a reviewer reading a diff, not by anything that runs.

Two guarantees are conflated. A test suite can *hold the code in place* (a change in behaviour fails a test) and it can *tell the code is wrong* (the implementation disagrees with something outside it). Mutation testing measures the first and only the first: it scores the suite against the implementation, which is the thing that may be wrong (arXiv 2607.22880). The second needs an **oracle** independent of the implementation. The human's leverage is in stating the oracle, a short list to review, not in reading tests.

Sources: the Pocock interview with Martin (youtu.be/zcLPGC-tvgk, 33:41–35:23), the research snapshots `agent/research/04-mutation-crap-tooling.md`, `05-mutmut-memex-prototype.md`, `06-long-fuzz-runners.md`, `07-ratchet-gate-yapit.md` (gitignored; the two property files they measured are kept under `agent/prototypes/testing-workflow/`), Luu (above, and danluu.com/testing).

## Solution

Three independent axes per test: where it enters the system (the seam: a function, a module's public API, an endpoint, the browser; what unit, integration and end-to-end name), how its inputs are chosen (hand-picked examples, generated properties, coverage-guided fuzz), and whether the tests themselves are checked (mutation). The spec decides the first two; a tool measures the third; a reviewer reads what neither can catch.

1. **Oracle, decided in the spec.** Testing Decisions names, per seam, what independent truth the tests compare against, and disposes each Property as *executable* (a property-based check at that seam) or *reviewed* (prose the Spec reviewer checks). Executable Properties are built by one early cross-cutting ticket, blocking every slice at its seams, whose worker has the spec and the seams' interface stubs and not the implementation, because the implementation does not exist yet when its worktree is cut.
2. **Harden, per feature.** A script the plugin ships measures what a feature's tests fail to hold: the mutants in the feature's changes that no test notices (compared against the point the feature branched from, so only what the feature added counts), the changed lines nothing runs, and the changes it could not measure at all. It runs once per feature, at the review session or when the frontier empties, and its output is a report the human reads there; findings become tickets or ship knowingly, like every other review-session finding. Nothing new runs per ticket.
3. **Review.** A fourth code-review axis, **Tests**, spawned when the diff touches test files: its brief carries the test-smell file and the spec's Testing Decisions, so it checks tests against the agreed seams and oracle the way the Spec axis checks code against the spec.

The discipline goes: `/mx:tdd` becomes `/mx:testing`, short and nudge-shaped (statements that move the agent off its default failure modes, no tutorial), with no prescribed order of test and code; `tests.md` and `mocking.md` are deleted and their content becomes smells. Red-first stays named in diagnosing-bugs, where the red proves the repro.

The periodic, whole-repo view of the same three questions belongs to `/mx:improve-codebase-architecture`, which already holds that structure decides testability: logic inside decorated entry points that no mutation tool can reach, a module whose tests need a database to say anything, a seam with no property. Those are deepening opportunities, and the skill gains a testing lens and a reason to be run.

CRAP is not a gate: Martin's own experiment (`unclebob/negative-test-experiment`) found a forced CRAP threshold doubled function counts and never raised a design score. Complexity is capped by the linter's own complexity rule (ruff `C901`, off by default), which project-setup enables with its limit in the project config.

## User Stories

1. As max, I want to review a short list of properties per feature and know they run, so my attention goes to what the code must guarantee, not to test bodies.
2. As max, I want to read a feature's input generators on the review page, because a generator shows the covered space in a way hundreds of example tests never will.
3. As max, I want the Properties I wrote in grilling to become executable checks without restating them, so the spec and the suite cannot drift apart.
4. As max, I want one report per feature that says which of its changes the tests fail to hold (a deleted or weakened test included), which changed lines nothing runs, and which changes it could not measure, so I decide what to fix before the feature merges.
5. As an implementer, I want to write code and tests in whatever order fits, so no steps go to a ritual that lowers correctness.
6. As an implementer, I want the ticket loop to stay as fast as it is today, so hardening never sits between me and `done`.
7. As the worker building a feature's property tests, I want the spec's Properties and the seams' interfaces and nothing else in my tree, so my checks cannot copy the implementation's mistakes.
8. As an orchestrator, I want a build ticket that edited the properties directory sent back, so a slice cannot pass by weakening a property.
9. As a Tests reviewer, I want the smell list and the spec's Testing Decisions, so I can flag a palindromic input, an expected value computed by the code under test, or a test at a seam nobody agreed.
10. As max setting up a project, I want project-setup to wire harden, the complexity cap and the property-testing library for the project's language, so every project answers "how do I harden this" with the same target.
11. As max, I want the complexity cap in the project's config, so a project runs agent or human numbers without touching a skill.
12. As max, I want the same property tests to run for hours, coverage-guided, on idle machines, so the fuzz budget costs me nothing to set up twice.
13. As max running improve-codebase-architecture, I want untestable structure reported as a deepening opportunity, so the periodic health pass covers tests as well as modules.
14. As the diagnosing-bugs flow, I still want the regression test seen red before the fix.
15. As max, I want the testing skill short enough to read against Luu's failure list and see which line prevents which failure.

## Properties

- A test's expected value never comes from the code under test.
- Every executable spec Property runs in the suite; every reviewed one is named in the Spec reviewer's brief.
- No build ticket other than the one that builds the property tests touches the properties directory.
- Harden compares a feature against the point it branched from; what the integration branch already missed is not the feature's finding.
- A change harden could not measure is reported as such, never as clean.
- A deleted or weakened test is a change harden measures.
- No skill prose restates a threshold or a tool's mechanics; the script's `--help` is their home.
- The testing skill contains no worked example of a test; examples live in the smells file as anti-patterns with fixes.

## Decisions

- Testing Decisions in the spec gains the **oracle**: the independent truth per seam, and each Property's disposition, executable or reviewed.
- to-tickets disposes executable Properties into one early ticket, blocked by nothing, blocking every slice at its seams; its tests live in the project's properties directory (`tests/properties/` by project-setup's convention; the path the dispatch rule below keys on). It is an ordinary build ticket in the cross-cutting position to-tickets already knows; no ticket type, no name. This amends to-tickets' disposal rule: executable Properties share that one ticket instead of one capability ticket each.
- The property-tests ticket lands as its own review page, like every ticket; the generators are what the human reads there, no further mechanism.
- For a feature changing existing code, the worker sees the old code; a property encoding current behaviour is a regression net, and the properties for new behaviour come from the spec. The brief's scope and the Tests reviewer are the guards there.
- The pre-merge read in dispatch: a change under the properties directory in any build ticket other than the property-tests ticket goes back to the worker, never merges. Stated as a rule in the skill's merge step; the orchestrator already reads the whole diff.
- Harden is a project command (`make harden`, beside `check` and `test`) that calls a script the plugin ships; the script's mechanics (which lines it mutates, how it keys survivors, how it treats decorated functions, flaky fixtures and property tests, which coverage tracer it needs) are the script's own, decided by the two prototypes and stated in its `--help`, never in a skill.
- Harden runs per feature, against the fork point, at the review session or when dispatch's frontier empties; its report is read by the human there. Not per ticket, and not repeated at the feature's merge, since the review session already sits before it. The cost decides the placement: on a deployed FastAPI app with a 22-second unit suite, minutes for a feature's worth of plain logic and hours for the whole repo; on a small CLI, seconds.
- improve-codebase-architecture gains a testing lens: harden's whole-repo report and the testability smells feed its deepening opportunities.
- Prior art for what the property-tests ticket produces, kept as primary sources under `agent/prototypes/testing-workflow/`: one 70-line property file at memex's `find` seam killed two mutants that 151 example tests missed, both the seam's stated contract; three properties on yapit's cache eviction contract found a live bug on the first run and killed three mutants that 474 example tests missed.
- Code-review gains the Tests axis, spawned when the diff touches tests. Light mode adds the test-smell file to its standards sources when tests are in the diff and runs no Tests brief, since it has no Testing Decisions to check against.
- Test smells are a file beside SMELLS.md, a standards source for the Tests axis.
- `/mx:tdd` → `/mx:testing`: seams, the oracle rule, discriminating inputs, structured generation over raw randomness, logic in plain functions the decorated entry point calls, extend the existing suite; example files deleted. Every pointer to the old skill moves with it: orient (which also stops prescribing red-green there), implement, codebase-design, the README.
- Red-first named in diagnosing-bugs only.
- Complexity via the linter's rule, enabled by project-setup; CRAP nowhere.
- The tools per language are interchangeable parts behind `make harden` and the properties directory, chosen by project-setup: Hypothesis / mutmut for Python; fast-check / Stryker for JS and TS; FsCheck / Stryker.NET for C#; proptest / cargo-mutants for Rust.
- Long fuzz runs reuse the property tests: HypoFuzz on repos where its non-commercial licence allows; Atheris through Hypothesis' `fuzz_one_input` where it does not. Wired by project-setup as an optional `make fuzz`.

Deferrals: none that drop a capability; the fuzz target is optional and the suite runs the same property tests without it.

## Testing Decisions

Two seams. The harden script, at its command line (a repository and a commit range in, one report out): its oracle is the two prototype replays, whose survivors, uncovered lines and unmeasured changes are known; the Properties "harden compares a feature against the point it branched from", "a change harden could not measure is reported as such, never as clean" and "a deleted or weakened test is a change harden measures" are executable there, as tests beside the script, prior art `permissions-review/scripts/test_scan_unapproved.py`. The skills, as prose: every other Property is reviewed, by the Spec axis against this document and by the next features' review sessions read against Luu's failure list; whether the new testing skill beats the old one is not measurable at Luu's scale.

## Out of Scope

- Harden as a per-ticket gate: the yapit replay costs it at minutes per logic ticket and showed most API tickets unmeasurable by the tool; a gate that is usually blind or usually slow is neither.
- A committed list of known-missed mutants: comparing against the fork point needs no curated file.
- Executable acceptance tests from ticket criteria (Martin's Gherkin layer and QA agent): a separate layer; human QA per landed slice stays as orient has it.
- CRAP as a gate: see Solution.
- Formal methods: Luu's agents used none of eight tools effectively.
- A mechanical guard against mocking own collaborators: no observed failure in this workflow yet; it stays a smell.
- Coverage-guided fuzzing outside Python: fast-check's fuzz mode has no coverage feedback, and the .NET, Rust and Java fuzzers take hand-written targets rather than property tests; separate work when a project wants it.
- Fixes to the tools themselves: the defects the prototypes hit in mutmut and coverage.py are filed as the standalone ticket `agent/tickets/mutmut-upstream-issues.md`; the harden script works around them.
- Surviving mutants projected onto the review page: notes the human stops reading.
- Dependency-rule enforcement (a module-boundary file agents cannot violate; import-linter for Python) and an architecture viewer: architecture, not testing; the viewer proved too generic in practice on large repos.
- A separate tester agent writing a ticket's unit tests: the independence that matters is from the implementation, which the property-tests ticket's ordering gives; a second author adds nothing to it (the one pre-registered study, arXiv 2607.23002, found same-model rounds killed 78% of survivors and no gain from a different model family).
