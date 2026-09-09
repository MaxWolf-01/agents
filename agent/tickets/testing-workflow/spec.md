---
status: draft
---

# Testing in the workflow

## Problem Statement

Agents test badly by default, and telling them how does not help. Luu's 26-condition eval (danluu.com/agentic-testing, Sep 2026: Zstd in Rust, 80 runs per condition, scored on hidden tests) found that naming a technique ("use TDD", "use property-based testing", "use mutation testing") leaves the agent writing its usual unit tests inside the named framework; the TDD prompt doubled the test count and lowered correctness; tutorial-shaped testing skills scored below no instruction and raised cost. What the agents' tests missed was the same every time: inputs that cannot discriminate the bug (four identical bitstreams for a four-stream feature, a palindrome for a reversal), expected values copied from the implementation, random inputs that all hit the rejection path, and mocks of the module's own collaborators.

The workflow today does what the eval says not to do: `/mx:tdd` prescribes red-green as the loop, its reference files are tutorials, and nothing then checks what the tests can catch. `make test` proves the tests pass; the reviewer's smell baseline has no entry for tests; the spec's Properties, the human-written list of what must always and never hold, are checked by a reviewer reading a diff, not by anything that runs.

Two guarantees are conflated. A test suite can *hold the code in place* (a change in behaviour fails a test) and it can *tell the code is wrong* (the implementation disagrees with something outside it). Mutation testing measures the first and only the first: it scores the suite against the implementation, which is the thing that may be wrong (arXiv 2607.22880). The second needs an **oracle** independent of the implementation: a property from the spec, a worked example, a reference implementation, a round trip, a model. The human's leverage is in stating the oracle, a short list to review, not in reading tests.

Sources: the Pocock interview with Martin (youtu.be/zcLPGC-tvgk, 33:41–35:23), `agent/research/04-mutation-crap-tooling.md` (Martin's experiment against CRAP as a gate; mutmut 3.7 incremental runs; arXiv 2607.05139 on tests that saw faulty code; 2607.23002 on the mutation-guided kill loop), Luu (above, and danluu.com/testing).

## Solution

Three independent axes per test: where it enters the system (the seam), how its inputs are chosen (examples, generated properties, coverage-guided fuzz), and whether the tests themselves are checked (mutation). The spec decides the first two; a tool runs the third; a reviewer reads what neither can catch. The human sees three small things per ticket: the property list, the gate's verdict as one number, the reviewers' findings.

1. **Oracle, decided in the spec.** Testing Decisions names, per seam, what independent truth the tests compare against, and disposes each Property as *executable* (a property-based check at that seam) or *reviewed* (prose the Spec reviewer checks). Executable Properties are built by the feature's **properties ticket**: one early cross-cutting capability ticket, blocking every slice at its seams, whose worker has the spec and the seams' interface stubs and not the implementation, because the implementation does not exist yet when its worktree is cut. `(you, r3)`
2. **Hardening gate, run by a tool.** `make harden` runs mutation testing and exits non-zero on survivors over the project's threshold; the implementer runs it before the done flip and kills survivors; the orchestrator runs it again at merge. It proves the tests hold the code; it is billed as exactly that. `(you, r3)` on placement; threshold `(open → Q4)`
3. **Review.** A fourth code-review axis, **Tests**, spawned when the diff touches test files: its brief carries the test-smell file and the spec's Testing Decisions, so it checks tests against the agreed seams and oracle the way the Spec axis checks code against the spec. `(you, r4)`

The discipline goes: `/mx:tdd` becomes `/mx:testing`, short and nudge-shaped (statements that move the agent off its default failure modes, no tutorial), with no prescribed order of test and code; `tests.md` and `mocking.md` are deleted and their content becomes smells. `(you, r2)` Red-first stays named in diagnosing-bugs, where the red proves the repro. `(you, r2)`

CRAP is not a gate: Martin's own experiment (`unclebob/negative-test-experiment`) found a forced CRAP threshold doubled function counts and never raised a design score. Complexity is capped where it already is: the linter's complexity rule (ruff `C901`), its limit in the project config. `(you, r3)`

## User Stories

1. As max, I want to review a short list of properties per feature and know they run, so my attention goes to what the code must guarantee, not to test bodies.
2. As max, I want to read a feature's input generators on the review page, because a generator shows the covered space in a way hundreds of example tests never will.
3. As max, I want the Properties I wrote in grilling to become executable checks without restating them, so the spec and the suite cannot drift apart.
4. As max, I want one number per ticket on the board (surviving mutants, or pass) that says the tests hold the code, billed as exactly that.
5. As an implementer, I want to write code and tests in whatever order fits, so no steps go to a ritual that lowers correctness.
6. As an implementer, I want one command that names the mutants my tests missed, so I never guess what to cover.
7. As an implementer, I want the mutation run to touch only what I changed, so hardening a ticket takes seconds.
8. As the properties-ticket worker, I want the spec's Properties and the seams' interfaces and nothing else in my tree, so my checks cannot copy the implementation's mistakes.
9. As an orchestrator, I want "green" at merge to include the gate, and I want an implementation ticket that edited the properties directory sent back, so a slice cannot pass by weakening a property.
10. As a Tests reviewer, I want the smell list and the spec's Testing Decisions, so I can flag a palindromic input, an expected value computed by the code under test, or a test at a seam nobody agreed.
11. As max setting up a project, I want project-setup to wire the gate, the complexity cap and the property-testing library for the project's language, so every project answers "how do I harden this" with the same target.
12. As max, I want thresholds and the complexity cap in the project's config, so a project runs agent or human numbers without touching a skill.
13. As max, I want suppressed mutants visible in the diff with a stated reason, so the escape hatch is reviewable.
14. As max, I want the same property tests to run for hours, coverage-guided, on idle machines, so the fuzz budget costs me nothing to set up twice.
15. As the diagnosing-bugs flow, I still want the regression test seen red before the fix.
16. As max, I want the testing skill short enough to read against Luu's failure list and see which line prevents which failure.

## Properties

- A test's expected value never comes from the code under test.
- Every executable spec Property runs in the suite; every reviewed one is named in the Spec reviewer's brief.
- A mutant is killed, or suppressed in the diff with a reason.
- An implementation ticket's diff never touches the properties directory.
- No skill prose restates a threshold; the gate's exit code is the verdict.
- The testing skill contains no worked example of a test; examples live in the smells file as anti-patterns with fixes.

## Decisions

- Testing Decisions in the spec gains the **oracle**: the independent truth per seam, and each Property's disposition, executable or reviewed. `(you, r3)`
- to-tickets disposes executable Properties into the **properties ticket**, blocked by nothing, blocking every slice at its seams; its tests live in the project's properties directory. `(you, r3)`; name `(my call)`
- For a feature changing existing code, the worker sees the old code; a property encoding current behaviour is a regression net, and the properties for new behaviour come from the spec. The brief's scope and the Tests reviewer are the guards there. `(you, r5)`
- The pre-merge read in dispatch: a change under the properties directory in an implementation ticket goes back to the worker, never merges. Stated as a rule in the skill's merge step; the orchestrator already reads the whole diff. `(you, r4)`
- The hardening gate is a project command (`make harden`, beside `check` and `test`); mutation only, incremental where the tool supports it. `(you, r3)`
- Gate before the done flip and at merge. `(you, r3)`
- Code-review gains the Tests axis, spawned when the diff touches tests, Opus by default. `(you, r4)`
- Test smells are a file beside SMELLS.md, a standards source for the Tests axis. `(you, r2)`
- `/mx:tdd` → `/mx:testing`: seams, the oracle rule, discriminating inputs, structured generation over raw randomness, extend the existing suite; example files deleted. `(you, r2)`
- Red-first named in diagnosing-bugs only. `(you, r2)`
- Complexity via the linter's rule; CRAP nowhere. `(you, r3)`
- Thresholds live in project config; the template ships a survivor threshold decided by a prototype run. `(open → Q4)`
- The tools per language are interchangeable parts behind `make harden` and the properties directory, chosen by project-setup: Hypothesis / mutmut for Python; fast-check / Stryker for JS and TS; FsCheck / Stryker.NET for C#; proptest / cargo-mutants for Rust. `(my call)`

Deferrals: the long-running fuzz runner (HypoFuzz over the existing property tests is the candidate) defers to a research round; if nobody decides, the property tests still run in the suite and nothing is lost but the idle-machine budget.

## Testing Decisions

The skills' own testable surface is the project-setup template and any script under `make harden`; prior art `permissions-review/scripts/test_scan_unapproved.py`. Whether the new testing skill beats the old one is not measurable at Luu's scale; the check is the next features' review sessions, read against Luu's failure list.

## Out of Scope

- Executable acceptance tests from ticket criteria (Martin's Gherkin layer and QA agent): a separate layer; human QA per landed slice stays as orient has it.
- CRAP as a gate: see Solution.
- Formal methods: Luu's agents used none of eight tools effectively.
- A mechanical guard against mocking own collaborators: no observed failure in this workflow yet; it stays a smell.
- Surviving mutants projected onto the review page: notes the human stops reading; the board carries one number per ticket instead.
- Dependency-rule enforcement (a module-boundary file agents cannot violate, Martin's `dependency-checker`; import-linter for Python) and an architecture viewer: architecture, not testing; the viewer proved too generic in practice on large repos.
- A separate tester agent writing a ticket's unit tests: independence comes from the properties ticket's ordering, not from a second author (arXiv 2607.23002 found no gain from a different model).

## Fog

- The long fuzz runner: tool, licence, where it runs, how findings come back.
- What the gate does on a greenfield first ticket with no suite.
- Whether a red gate at merge routes back to the worker or to a fresh worker.
