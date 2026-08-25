---
name: code-review
description: Review the changes since a fixed point (commit, branch, tag, or merge-base) along three axes — Correctness (does it break anything?), Standards (repo coding standards plus a smell baseline), and Spec (does it match what the originating task/issue asked for?). Runs the axes as parallel reviewers; specless work runs light — one reviewer, no spec axis. Use when the user wants to review a branch, work-in-progress changes, finished unspecced work, or asks to "review since X" or a "light review".
---

Three-axis review of the diff between `HEAD` and a fixed point:

- **Correctness** — does the change work, without breaking callers, contracts, or edge cases?
- **Standards** — does it conform to the repo's documented standards and the smell baseline?
- **Spec** — does it faithfully implement the originating task / issue / spec?

The axes run as parallel reviewers so they don't pollute each other's context; this skill aggregates their findings.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point — a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. If they didn't specify one, default to "since the last review": the most recent commit bearing a `Workflow-stage: review` trailer (`git log --grep='^Workflow-stage: review$' -1 --format=%H` — anchored, or a commit merely *discussing* the trailer matches); when none exists, `@{upstream}` if it resolves and differs from `HEAD`, else the merge-base with the default branch. Whichever candidate is nearest `HEAD` wins. Ask only when none produces a non-empty diff.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here — not inside three parallel reviewers.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. A path, URL, or text the user passed as an argument.
2. Issue/PR references in the commit messages (`#123`, `Closes #45`) — fetch via `gh`.
3. A task or spec file: `agent/tasks/`, `docs/`, `specs/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is — unless the work is plainly loose in-session work that never had one.

No spec → run **light** (below): one reviewer, no Spec axis, instead of the full spawn.

### 3. Identify the standards sources

Anything in the repo that documents how code should be written: `CLAUDE.md`, `CODING_STANDARDS.md`, `CONTRIBUTING.md`. Three files join these as standards sources, each passed by absolute path:

- [`SMELLS.md`](SMELLS.md), beside this file — the **smell baseline**: a fixed set of code smells the Standards axis applies to every diff, even when the repo documents nothing.
- `/mx:writing-for-humans` (its `SKILL.md`) — for **every** diff: its rules bind all artifact text, wherever it lives — code comments, docstrings, UI strings, help text, docs, READMEs.
- `/mx:writing-for-agents` (its `SKILL.md`) — when the diff touches process documents (skills, `AGENTS.md`/`CLAUDE.md`, prompt templates, workflow conventions): a standards source for those hunks.

### 4. Spawn the reviewers in parallel

Spawn one subagent per axis, all in a single message so they run concurrently. A reviewer sees its brief, not this session; the briefs below go in verbatim — they are self-contained, which is what fresh eyes need. (When the user asks for a cross-model review, run the same briefs through `/mx:codex` instead.)

Each spawn carries an explicit model, never left to inherit this session's own: Opus by default, Sonnet by your judgment when the diff is small or trivial, never Fable unless the user names it explicitly for this review.

Every brief opens with two lines. First, delivery: *"Write your finished report to `agent/research/code-review-<axis>.md`."*

Then the discipline line: *"Read every touched file in full, plus the callers of anything changed — not just the hunks. Build the mental model before judging; a diff read in isolation lies."*

**Correctness brief** — include:

- The full diff command and commit list.
- The brief: "Trace the change end to end: touched files in full, callers of changed functions, changed types/protocols/contracts, related tests. Report only findings that survive three filters: (a) it's a real problem, not an artifact of reading the diff in isolation — check surrounding code and existing patterns first; (b) you can name the concrete consequence — bug, security hole, data loss, perf regression, maintenance trap; no nameable consequence, no finding; (c) the codebase doesn't already handle it. Not findings: style the change is internally consistent about, validation for inputs that can't arrive, API semantics that match existing conventions, 'what if X' where the system prevents X. Each finding: the scenario that breaks, file:line, fix. Under 400 words."

**Standards brief** — include:

- The full diff command and commit list.
- The standards-source files from step 3 — repo docs, `SMELLS.md`, and the skill files — all by absolute path.
- The brief: "Read every standards-source file before judging. Report — per file/hunk where relevant — (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any smell from SMELLS.md or rule violation from the skill files: name it and quote the hunk. Distinguish hard violations from judgement calls per SMELLS.md's binding rules. Skip anything tooling enforces. Under 400 words."

**Spec brief** — include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep) — including **Speculative Generality**: abstraction, parameters, hooks, or configurability added for needs the spec doesn't have; (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

### 5. Aggregate

The review is one message, written after every axis has returned. Nothing about findings goes out before that — no per-axis narration as reviewers land, no "Correctness came back clean, waiting on the others".

Read the axes' report files, then delete them: their content lives in this message from here on.

That last message is the only one that reliably gets read: the reader skims to the end of the turn, copies the review to another agent to act on, or — when this skill runs as a sub-agent — receives only the final message. So it has to stand alone. Every finding, its reasoning, and the fixed point it was reviewed against belong in it; don't reference an earlier message as if it were read.

Present the reports under `## Correctness`, `## Standards`, and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings — the axes are deliberately separate (see _Why separate axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes — that's the reranking the separation exists to prevent.

A clean diff gets a short review. Report the axes as they came back; empty is a valid result.

Accepted findings land as a **follow-up commit**, never an amend — the commit's diff is the review's measurable effect. The session that wrote the work applies them when it's still around; any session can otherwise.

## Light mode

For specless work, or when the user asks for it. Steps 1 and 3 run unchanged; step 4 collapses to **one** subagent whose brief is the discipline line, the diff command, the **full commit messages** (`git log <fixed-point>..HEAD`, no `--oneline`), the standards-source files by absolute path, and the Correctness and Standards briefs joined — same filters, same citation rules, one report under 600 words. The commit messages are orientation over the diff: the author's account of what each commit does, never an anchor to judge it against. Model rule inverted from step 4: Sonnet by default, Opus by your judgment when the diff is complex enough to warrant it, never Fable unless the user names it explicitly. Aggregate verbatim under `## Review`; the follow-up-commit rule applies as-is.

The fold trades axis separation for cost, which is the right trade exactly when there is no spec whose masking you'd care about.

## Why separate axes

A change can pass any axis and fail another:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks a caller → **Spec pass, Correctness fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking another.
