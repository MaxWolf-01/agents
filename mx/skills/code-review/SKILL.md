---
name: code-review
description: "Review the changes since a fixed point (a commit, branch or tag). Use when the user asks to review a branch or work in progress, or to \"review since X\"."
---

Review of the diff between `HEAD` and a fixed point, by two reviewers:

- **read** reads the diff, one pass per question, each pass opening its own sources only once the last is done: **correctness** (does the change work, without breaking callers, contracts, or edge cases?), **spec** (does it faithfully implement the originating ticket / issue / spec?), then **standards** (does it conform to the repo's documented standards and the smell baseline?).
- **tests** runs the suite under mutations: do the tests the diff touches enter at the agreed seams, take their expectations from an oracle, and use inputs that can discriminate a bug? It is the one reviewer that executes the tip under review, and it runs where the diff touches a test.

Their reports are read by the session or worker that owns the branch (step 5). [`review`](review) runs them (step 4).

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point: a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. If they didn't specify one, default to "since the last review": the most recent commit bearing a `Workflow-stage: review` trailer (`git log --grep='^Workflow-stage: review$' -1 --format=%H`, anchored, or a commit merely *discussing* the trailer matches); when none exists, `@{upstream}` if it resolves and differs from `HEAD`, else the merge-base with the default branch. Whichever candidate is nearest `HEAD` wins. Ask only when none produces a non-empty diff, which the script's own refusal tells you.

### 2. Identify the spec source

Look for what the work was ordered by, in this order:

1. A path, URL, or text the user passed as an argument.
2. The ticket the branch builds: `tracker context <slug>` is its ticket context, the whole order for this work, and a branch named `ticket/<slug>` names its slug.
3. Issue/PR references in the commit messages (`#123`, `Closes #45`), fetched via `gh`.
4. A specification the repo keeps outside the tracker: `docs/`, `specs/` matching the branch name.
5. If nothing is found, ask the user where it is, unless the work is session work, which never had one.

It travels to the reviewers as a file, so a fetched issue body or text the user pasted is written to one. Anything else the reviewers must not reopen goes in that file too: linked issues, a PR's prior review discussion.

Where no order was found, the review runs without one, and read judges the diff on its own terms.

### 3. What binds the review

The standards sources are the script's to gather, by what the diff touches, and the prompt it writes for each reviewer is the record of which ones bound this review. Two are this skill's own: [`SMELLS.md`](SMELLS.md), the **smell baseline**, a fixed set of code smells the standards pass applies to every diff even when the repo documents nothing; and [`TEST-SMELLS.md`](TEST-SMELLS.md), the **test-smell baseline**, read by the tests reviewer, or by read where no tests reviewer runs. The standards pass checks a glossary entry or an ADR the diff touches against its format: the agent that wrote it has just settled the mechanism behind it and reads that as the definition, and the reviewer reads it cold.

### 4. Run the reviewers

`review`, beside this file and on `PATH`, runs them. `review --help` is the manual: run it before your first review.

It takes minutes and narrates one line per reviewer, so run it where you can watch it (`/mx:tmux`). The judgment it leaves you is how hard the reviewers work, and it scales with the work:

- **`--effort medium`**, the default, for a change that needed judgment.
- **`--effort low`** for a simpler one: a few files, one idea, no contract another piece of work depends on.
- **No review** for a trivial change: one the user dictated, or one that needed no judgment (a rename, a version bump).

`--minutes` goes up for a large diff; `model-runs report --site review` shows what past rounds cost and took per reviewer and effort. For a cross-model review, run the same prompts through `/mx:codex` instead.

### 5. Aggregate

The caller aggregates: the session or worker that owns the branch, once the script has returned. Nothing about findings goes out before that, no narration as reviewers land.

Read the reports, each pass of read's on its own, and give every finding one of three dispositions:

- **Fixed**: a follow-up commit carrying `Workflow-stage: review`, never an amend, so the commit's diff is the review's measurable effect.
- **Filed**: worth acting on, too large for that commit, so it becomes a proposed ticket (`/mx:tracker`).
- **Declined**: the finding's premise is wrong, or the fix costs more than the finding is worth, and the entry says which. It lands anchored in the `Assumptions` block of the closing comment the caller writes (`` - A7 `src/importer.py:118`: the finding, and why it stands ``; ids continue from the highest already in the ticket, which is the id rule a worker carries in its contract, [`worker-prompt.md`](../dispatch/worker-prompt.md)), so the ticket's review page projects it onto the line it concerns, and the landing shows it to the user when it is theirs to rule on (`/mx:dispatch`).

Two callers hold no ticket. A bare "review this branch" anchors its declines and its index on the review page as notes. A review of a branch the caller does not own, an incoming PR, delivers every finding where the review is happening, the PR's comments or the reply: nothing there is the caller's to fix, so every finding is one of the user's calls.

Where a ticket holds the work, its closing comment carries a **finding index** under the review range: one line per finding, cited by its id qualified with the range (`review 2339177..8424220 R3`): fixed → the commit, filed → the ticket, declined → the assumption id. The agent that merges the branch reads that index, never the reports.

A review's reader is the agent that owns the branch, never the user. It fixes, files or declines each finding, and what it cannot dispose of alone (a declined finding worth a ruling, a question the review raised) it escalates through its own closing comment, under the worker contract. Findings the review fixed, per-pass summaries and verification lists stay in the reports, which die with the worktree.

A clean diff gets one line: the range, and that the reviewers came back empty.

## Why one pass per question

A change can pass any question and fail another:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks a caller → **Spec pass, Correctness fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**
- Code that is correct, conventional and asked for, under tests that would pass without it → **every pass of read comes back clean, tests fails.**

So read keeps its passes apart in its report, and each is read and disposed on its own: one ranked list would let three clean passes bury the one failure. The tests reviewer stands apart from read for another reason: it mutates and runs code in a checkout of its own, which read has no reason to hold in its context.
