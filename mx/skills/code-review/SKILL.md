---
name: code-review
description: Review the changes since a fixed point (commit, branch, tag, or merge-base) along three axes — Correctness (does it break anything?), Standards (repo coding standards plus a smell baseline), and Spec (does it match what the originating task/issue asked for?). Runs the axes as parallel sub-agents and reports them side by side. Use when the user wants to review a branch, work-in-progress changes, or asks to "review since X".
---

Three-axis review of the diff between `HEAD` and a fixed point:

- **Correctness** — does the change work, without breaking callers, contracts, or edge cases?
- **Standards** — does it conform to the repo's documented standards and the smell baseline?
- **Spec** — does it faithfully implement the originating task / issue / spec?

The axes run as parallel sub-agents so they don't pollute each other's context; this skill aggregates their findings.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point — a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. If they didn't specify one, ask for it.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here — not inside three parallel sub-agents.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. A path, URL, or text the user passed as an argument.
2. Issue/PR references in the commit messages (`#123`, `Closes #45`) — fetch via `gh`.
3. A task or spec file: `agent/tasks/`, `docs/`, `specs/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

### 3. Identify the standards sources

Anything in the repo that documents how code should be written: `CLAUDE.md`, `CODING_STANDARDS.md`, `CONTRIBUTING.md`.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below — a fixed set of code smells (Fowler, _Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation — and, like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name** — a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code** — the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy** — a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps** — the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain concept that deserves its own type, including flag `bool`s a two-constructor variant would make self-describing at call sites. → give the concept its own small type.
- **Repeated Switches** — the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change** — one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality** — abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man** — a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest** — a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.
- **Dishonest Types** — code lying to the type checker: `as any`, non-null assertions on nullables, `T[]` holding nulls. → make the type tell the truth; if it can't, the design is off.
- **Defensive Padding** — try/except "just in case", or validation for inputs the system already guarantees. → delete it; let impossible failures be loud.
- **Narrating Comments** — comments restating the next line, meta-commentary, fluff. → delete; comment only non-obvious behaviour, warnings, complex algorithms.
- **Representable Illegal States** — the type permits states the domain forbids: fields that must co-occur but are individually optional, a status field plus booleans that can contradict it, a list that must never be empty. → encode the invariant in the type; make illegal states unrepresentable.
- **Catch-all Match** — a `_`/default arm on a closed set of variants, so adding a variant compiles silently instead of erroring at every site that must handle it. → enumerate the cases; reserve the catch-all for genuinely open sets.

### 4. Spawn the sub-agents in parallel

Send a single message with three `Agent` tool calls. Use the `general-purpose` subagent for all three.

Every brief opens with the same discipline line: *"Read every touched file in full, plus the callers of anything changed — not just the hunks. Build the mental model before judging; a diff read in isolation lies."*

**Correctness sub-agent prompt** — include:

- The full diff command and commit list.
- The brief: "Trace the change end to end: touched files in full, callers of changed functions, changed types/protocols/contracts, related tests. Report only findings that survive three filters: (a) it's a real problem, not an artifact of reading the diff in isolation — check surrounding code and existing patterns first; (b) you can name the concrete consequence — bug, security hole, data loss, perf regression, maintenance trap; no nameable consequence, no finding; (c) the codebase doesn't already handle it. Not findings: style the change is internally consistent about, validation for inputs that can't arrive, API semantics that match existing conventions, 'what if X' where the system prevents X. Each finding: the scenario that breaks, file:line, fix. Under 400 words."

**Standards sub-agent prompt** — include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, **plus the smell baseline pasted in full** — the sub-agent has no other access to it.
- The brief: "Report — per file/hunk where relevant — (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls — documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."

**Spec sub-agent prompt** — include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report.

### 5. Aggregate

Present the reports under `## Correctness`, `## Standards`, and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings — the axes are deliberately separate (see _Why separate axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes — that's the reranking the separation exists to prevent.

A clean diff gets a short review. Report the axes as they came back; empty is a valid result.

## Why separate axes

A change can pass any axis and fail another:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks a caller → **Spec pass, Correctness fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking another.
