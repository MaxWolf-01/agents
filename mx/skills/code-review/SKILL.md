---
name: code-review
description: "Review the changes since a fixed point (commit, branch, tag, or merge-base) along four axes: Correctness (does it break anything?), Standards (repo coding standards plus a smell baseline), Spec (does it match what the originating ticket/issue asked for?), and Tests (what do the tests it touches actually catch?). Runs the axes as parallel reviewers; specless work runs light, one reviewer and no spec axis. Use when the user wants to review a branch, work-in-progress changes, finished unspecced work, or asks to \"review since X\" or a \"light review\"."
---

Review of the diff between `HEAD` and a fixed point, along four axes:

- **Correctness**: does the change work, without breaking callers, contracts, or edge cases?
- **Standards**: does it conform to the repo's documented standards and the smell baseline?
- **Spec**: does it faithfully implement the originating ticket / issue / spec?
- **Tests**: do the tests it touches enter at the agreed seams, take their expectations from an oracle, and use inputs that can discriminate a bug? Spawned only when the diff touches test files.

The axes run as parallel reviewers so they don't pollute each other's context. Their reports land on disk under the range they read, and the session or worker that owns the branch acts on them (step 5).

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point: a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. If they didn't specify one, default to "since the last review": the most recent commit bearing a `Workflow-stage: review` trailer (`git log --grep='^Workflow-stage: review$' -1 --format=%H`, anchored, or a commit merely *discussing* the trailer matches); when none exists, `@{upstream}` if it resolves and differs from `HEAD`, else the merge-base with the default branch. Whichever candidate is nearest `HEAD` wins. Ask only when none produces a non-empty diff.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`, and the **range**, which names the reports' directory: `echo "$(git rev-parse --short=7 <fixed-point>)..$(git rev-parse --short=7 HEAD)"`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside the parallel reviewers.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. A path, URL, or text the user passed as an argument.
2. Issue/PR references in the commit messages (`#123`, `Closes #45`), fetched via `gh`.
3. A ticket or spec file: `agent/tickets/`, `docs/`, `specs/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is, unless the work is plainly loose in-session work that never had one.

No spec → run **light** (below): one reviewer, no Spec axis, instead of the full spawn.

### 3. Identify the standards sources

Anything in the repo that documents how code should be written: `CLAUDE.md`, `CODING_STANDARDS.md`, `CONTRIBUTING.md`, `PRINCIPLES.md`. Four files join these as standards sources, each passed by absolute path:

- [`SMELLS.md`](SMELLS.md), beside this file, the **smell baseline**: a fixed set of code smells the Standards axis applies to every diff, even when the repo documents nothing.
- [`TEST-SMELLS.md`](TEST-SMELLS.md), beside it, the **test-smell baseline**: the Tests axis's own source, and a Standards source in light mode whenever the diff touches tests.
- `/mx:writing-for-humans` (its `SKILL.md` and, beside it, [`CATALOGUE.md`](../writing-for-humans/CATALOGUE.md), the catalogue of prose tells the reviewer cites by rule id), for **every** diff: their rules bind all artifact text wherever it lives (code comments, docstrings, UI strings, help text, docs, READMEs).
- `/mx:writing-for-agents` (its `SKILL.md`), when the diff touches process documents (skills, `AGENTS.md`/`CLAUDE.md`, prompt templates, workflow conventions): a standards source for those hunks.

### 4. Spawn the reviewers in parallel

Spawn one subagent per axis, all in a single message so they run concurrently. A reviewer sees its brief, not this session; the briefs below go in verbatim; they are self-contained, which is what fresh eyes need. (When the user asks for a cross-model review, run the same briefs through `/mx:codex` instead.)

Each spawn carries an explicit model, never left to inherit this session's own: Opus by default, Sonnet by your judgment when the diff is small or trivial, never Fable unless the user names it explicitly for this review.

Every brief opens with two lines. First, delivery: *"Write your finished report to `agent/reviews/<range>/<axis>.md`, creating the directory."* The reports stay there, gitignored, for the life of the worktree: the aggregator reads files, not a chat message.

Then the discipline line: *"Read every touched file in full, plus the callers of anything changed, not just the hunks. Build the mental model before judging; a diff read in isolation lies."*

For the **Correctness brief**, include:

- The full diff command and commit list.
- The brief: "Trace the change end to end: touched files in full, callers of changed functions, changed types/protocols/contracts, related tests. Report only findings that survive three filters: (a) it's a real problem, not an artifact of reading the diff in isolation: check surrounding code and existing patterns first; (b) you can name the concrete consequence (bug, security hole, data loss, perf regression, maintenance trap); no nameable consequence, no finding; (c) the codebase doesn't already handle it. Not findings: style the change is internally consistent about, validation for inputs that can't arrive, API semantics that match existing conventions, 'what if X' where the system prevents X. Each finding: the scenario that breaks, file:line, fix."

For the **Standards brief**, include:

- The full diff command and commit list.
- The standards-source files from step 3, `CATALOGUE.md` among them, all by absolute path.
- The brief: "Read every standards-source file before judging. Then read the standards the repo never wrote down, which are the code itself: for each kind of surface the diff adds or extends (a view, a command, an error path, a module API, a test file), find the two nearest existing instances of that same kind and read them in full. They sit outside the diff and outside its call graph, so find them by kind, not by reference. Report, per file/hunk where relevant, (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any smell from SMELLS.md or rule violation from the skill files: name it and quote the hunk. A finding that the diff diverges from an existing convention cites two instances of that convention by file:line and states the answer they share; without them it is not a finding. Distinguish hard violations from judgement calls per SMELLS.md's binding rules. Skip anything tooling enforces."

For the **Spec brief**, include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep), including **Speculative Generality**: abstraction, parameters, hooks, or configurability added for needs the spec doesn't have; (c) requirements that look implemented but where the implementation looks wrong; (d) each Property the spec's Testing Decisions disposes as *reviewed*, checked against the diff by name. Quote the spec line for each finding."

For the **Tests brief**, spawned only when the diff touches test files, include:

- The diff command and commit list.
- `TEST-SMELLS.md` by absolute path, and the spec's **Testing Decisions** section (its path, or quoted in full when the spec is fetched from an issue).
- The brief: "Judge what these tests catch, not whether they pass. Read the tests in full and the code under test. Report: (a) every test-smell from TEST-SMELLS.md: name it and quote the hunk; (b) tests entering at a seam the Testing Decisions does not name, and seams it names that the diff leaves untested; (c) executable spec Properties with no check in the properties directory, and reviewed ones the diff contradicts; (d) behaviour the diff adds that no test could tell from its absence. Each finding: the test, the mutation or input it would not catch, the fix."

### 5. Aggregate

The caller aggregates: the session or worker that owns the branch, once every axis has returned. Nothing about findings goes out before that, no per-axis narration as reviewers land. Confirm each expected report file is on disk before reading: an absent report is an axis to re-run, never a clean axis.

Read the reports per axis and give every finding one of three dispositions:

- **Fixed**: a follow-up commit carrying `Workflow-stage: review`, never an amend, so the commit's diff is the review's measurable effect.
- **Filed**: worth acting on, too large for that commit, so it becomes a proposed ticket (`/mx:tracker`).
- **Declined**: the finding's premise is wrong, or the fix costs more than the finding is worth, and the entry says which. It lands anchored in the `Assumptions` block of the ticket's closing comment (`` - A7 `src/importer.py:118`: the finding, and why it stands ``; ids continue from the highest already in the ticket, per `/mx:implement`), so the ticket's review page projects it onto the line it concerns, which is where the user rules on it.

Two callers hold no ticket. A bare "review this branch" anchors its declines and its index on the review page as notes. A review of a branch the caller does not own, an incoming PR, delivers every finding where the review is happening, the PR's comments or the reply: nothing there is the caller's to fix, so every finding is one of the user's calls.

Where a ticket holds the work, its closing comment carries a **finding index** under the review range: one line per finding, fixed → the commit, filed → the ticket, declined → the assumption id. The agent that merges the branch reads that index, never the reports.

What reaches the user, from every caller: the review page; the calls only they can make (declined findings, assumptions, open questions); the next steps and blockers. Findings the review already fixed, per-axis summaries and verification lists stay in the reports, which die with the worktree. In the landing message that means the review page beside the demo, the user's calls under "I need from you" tagged `[Dn]`, and the range and the finding index under "Details, if you want them".

A clean diff gets one line: the range, and that the axes came back empty.

## Light mode

For specless work, or when the user asks for it. Steps 1 and 3 run unchanged; step 4 collapses to **one** subagent whose brief is the discipline line, the diff command, the **full commit messages** (`git log <fixed-point>..HEAD`, no `--oneline`), the standards-source files by absolute path, and the Correctness and Standards briefs joined: same filters, same citation rules, one report, written to `agent/reviews/<range>/light.md`. A diff touching tests adds `TEST-SMELLS.md` to that reviewer's standards sources and no Tests brief: light mode has no Testing Decisions to check the tests against. The commit messages are orientation over the diff: the author's account of what each commit does, never an anchor to judge it against. Model rule inverted from step 4: Sonnet by default, Opus by your judgment when the diff is complex enough to warrant it, never Fable unless the user names it explicitly. Step 5 runs as written: one report to read, the same three dispositions, the same delivery.

The fold trades axis separation for cost, which is the right trade exactly when there is no spec whose masking you'd care about.

## Why separate axes

A change can pass any axis and fail another:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks a caller → **Spec pass, Correctness fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**
- Code that is correct, conventional and asked for, under tests that would pass without it → **every other axis passes, Tests fail.**

One report per axis, read per axis, stops one axis from masking another.
