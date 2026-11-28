---
name: diagnosing-bugs
description: Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or reports something broken/throwing/failing/slow.
---

# Diagnosing Bugs

A discipline for hard bugs. Skip a phase only with an explicit justification.

## Redact

**Redact every secret** in a command, output or artifact before you show it: write `<REDACTED>` in its place. Build loops against env vars, so a credential stays in the environment and out of what you show. Captured artifacts carry auth headers: quote only the lines that carry the signal.

If the redacted output is not enough to diagnose the bug, say so and ask the user.

## Phase 1: Build a feedback loop

**This is the skill**; the rest is mechanical. Bisection, hypothesis-testing and instrumentation all consume a **tight** pass/fail signal that goes red on _this_ bug, and the cause follows from it.

### Building one

Reach for the lightest loop that can go red on this bug: a replayed capture, a throwaway harness around the one code path, a property or fuzz loop, a `git bisect run` harness between two known states, a differential run of two versions or configs, or whatever else can. A loop that needs a human's hands drives them with `scripts/hitl-loop.template.sh`, and comes last.

### Non-deterministic bugs

Aim for a **higher reproduction rate**, not a clean repro: loop the trigger 100×, parallelise, add stress, narrow timing windows, inject sleeps. A 50%-flake bug is debuggable and a 1% one is not, so keep raising the rate until it is debuggable.

### When you genuinely cannot build a loop

Stop, say so explicitly, and list what you tried. Ask the user for (a) access to an environment that reproduces it, (b) a redacted captured artifact (HAR file, log dump, core dump, screen recording with timestamps), or (c) permission to add temporary production instrumentation.

### Completion criterion: a tight loop that goes red

Phase 1 is done when you can name **one command** (a script path, a test invocation, a curl) that you have **already run at least once**, with its invocation and redacted output shown, and that is:

- [ ] **Red-capable**: it drives the actual bug code path and asserts the **user's exact symptom**, so it goes red on this bug and green once fixed. It must be able to _catch this specific bug_, not merely run without erroring.
- [ ] **Deterministic**: same verdict every run (for a flaky bug, a pinned, high reproduction rate).
- [ ] **Fast**: seconds, not minutes.
- [ ] **Agent-runnable**: it runs unattended; a human enters the loop only via `scripts/hitl-loop.template.sh`.

No red-capable command, no Phase 2.

## Phase 2: Reproduce + minimise

Confirm:

- [ ] The loop produces the failure mode the **user** described, not a different failure nearby.
- [ ] The failure reproduces across runs (for a non-deterministic bug, at a rate high enough to debug against).
- [ ] You have captured the exact symptom (error message, wrong output, slow timing), so later phases can verify that the fix addresses it.

### Minimise

Once it's red, shrink the repro to the **smallest scenario that still goes red**: cut inputs, callers, config, data and steps **one at a time**, re-running the loop after each cut.

Done when **every remaining element is load-bearing**: removing any one of them makes the loop go green.

## Phase 3: Hypothesise

Generate **3–5 ranked hypotheses** before testing any of them; a single hypothesis anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state the prediction it makes.

> Format: "If <X> is the cause, then <changing Y> will make the bug disappear / <changing Z> will make it worse."

A hypothesis whose prediction you cannot state is a vibe: discard or sharpen it.

**Show the ranked list to the user before testing**: their domain knowledge may re-rank it ("we just deployed a change to #3") or rule some out. If the user is AFK, proceed on your ranking rather than wait.

## Phase 4: Instrument

Each probe maps to a specific prediction from Phase 3. **Change one variable at a time.**

Prefer a **debugger or REPL** where the env supports one (one breakpoint beats ten logs); otherwise, **targeted logs** at the boundaries that distinguish hypotheses.

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`, so cleanup is a single grep.

**Perf branch.** For a performance regression, establish a baseline measurement (timing harness, `performance.now()`, profiler, query plan) and bisect, instead of logging.

## Phase 5: Fix + regression test

The fix goes at the cause Phase 4 confirmed: the place the wrong state is made, however far that is from where it surfaced.

Write the regression test **before the fix**, if there is a **correct seam** for it: one where the test exercises the **real bug pattern** as it occurs at the call site. A test at a seam too shallow for that (a single-caller test when the bug needs multiple callers, a unit test that cannot replicate the chain that triggered the bug) gives false confidence.

**If no correct seam exists, that itself is the finding**: the architecture is preventing the bug from being locked down. Note it and flag it for the post-mortem.

If a correct seam exists, the minimised repro becomes a test at it, seen red before the fix and green after, and the Phase 1 loop goes green on the original, un-minimised scenario.

## Phase 6: Cleanup + post-mortem

Required before declaring done:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop)
- [ ] Regression test passes (or the absence of a seam is documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` the prefix)
- [ ] Throwaway prototypes deleted (or moved to a clearly-marked debug location)
- [ ] The commit or PR message states the hypothesis that turned out correct, so the next debugger learns

**Then ask: what would have prevented this bug?** If the answer involves architectural change (no good test seam, tangled callers, hidden coupling), hand off to `/mx:improve-codebase-architecture` with the specifics. Make that recommendation **after** the fix is in, when you know the most.
