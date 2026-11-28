---
name: code-review
description: "Review the changes since a fixed point (a commit, branch or tag). Use when the user asks to review a branch or work in progress, or to \"review since X\"."
---

Review of the diff between `HEAD` and a fixed point, by two reviewers:

- **read** reads the diff in one pass per question, each pass opening its own sources only once the last is done: **correctness** (does the change work, without breaking callers, contracts, or edge cases?), **spec** (does it faithfully implement the originating ticket / issue / spec?), then **standards** (does it conform to the repo's documented standards and the smell baseline?), then **grug** (what in the diff should not exist?).
- **tests** runs the suite under mutations: do the tests the diff touches enter at the agreed seams, take their expectations from an oracle, and use inputs that can discriminate a bug? It is the one reviewer that executes the tip under review, and it runs where the diff touches a test.

## Process

### 1. Pin the fixed point

The fixed point is whatever the user named, passed to `review`; where they named none, `review` takes "since the last review" itself (`review --help`).

### 2. Identify the spec source

Look for what the work was ordered by, in this order:

1. A path, URL, or text the user passed as an argument.
2. The ticket the branch builds, whose slug a branch named `ticket/<slug>` names: `tracker context <slug>` is the whole order for this work.
3. Issue/PR references in the commit messages (`#123`, `Closes #45`), fetched via `gh`.
4. A specification the repo keeps outside the tracker: `docs/`, `specs/` matching the branch name.
5. Failing those, ask the user, unless a session did the work without a ticket, so it never had one.

The spec reaches the reviewers as a file: write a fetched issue body or pasted text to one, together with anything else the reviewers must not reopen (linked issues, a PR's prior review discussion).

### 3. What binds the review

The script gathers the standards sources by what the diff touches, and the prompt it writes for each reviewer records which ones bound this review. Two are this skill's own: [`SMELLS.md`](SMELLS.md), the **smell baseline**, which the standards pass applies to every diff even when the repo documents nothing; and [`TEST-SMELLS.md`](TEST-SMELLS.md), the **test-smell baseline**, read by the tests reviewer, or by read where no tests reviewer runs. The standards pass checks a glossary entry or an ADR the diff touches against its format, because its author reads it through the mechanism it has just settled, and only the reviewer reads it cold.

### 4. Run the reviewers

`review`, beside this file and on `PATH`, runs them. `review --help` is the manual: run it before your first review.

It takes minutes and narrates one line per reviewer, so run it where you can watch it (`/mx:tmux`). Your judgment is how hard the reviewers work, scaled to the work:

- **`--effort medium`**, the default, for a change that needed judgment.
- **`--effort low`** for a simpler one: a few files, one idea, no contract another piece of work depends on.
- **No review** for a trivial change: one the user dictated, or one that needed no judgment (a rename, a version bump).

`--minutes` goes up for a large diff; `model-runs report --site review` shows what past rounds cost and took per reviewer and effort. For a cross-model review, run the same prompts through `/mx:codex` instead.

### 5. Aggregate

The caller, the session or worker that owns the branch, aggregates once the script has returned, and reports nothing about findings before then.

Read the reports, each pass of read's on its own, and give every finding one of three dispositions:

- **Fixed**: a follow-up commit carrying `Workflow-stage: review`, never an amend, so the commit's diff is the review's measurable effect. A bug is fixed once a run shows it: its failing test, which stays as its regression test, or the lightest run that can (a command and its output, a skill's step done as written). A fix corrects or removes.
- **Filed**: worth acting on and not this commit's, so it becomes a proposed ticket (`/mx:tracker`): too large for it; a bug no run shows, with the steps that would; a fix that would add a guard, an abstraction or a test for behaviour the spec does not name; a module boundary.
- **Declined**: the finding's premise is wrong, or the fix costs more than the finding is worth, and the entry says which. It goes, anchored, in the `Assumptions` block of the caller's closing comment (`` - A7 `src/importer.py:118`: the finding, and why it stands ``; ids continue from the highest already in the ticket, the id rule of the worker contract, [`worker-prompt.md`](../dispatch/worker-prompt.md)), so the ticket's review page projects it onto its line, and the landing shows it to the user when it is theirs to rule on (`/mx:dispatch`).

Two callers hold no ticket. A bare "review this branch" anchors its declines and its index on the review page as notes. A review of a branch the caller does not own, an incoming PR, delivers every finding where the review is happening, in the PR's comments or the reply: nothing there is the caller's to fix, so every finding is one of the user's calls.

Where a ticket holds the work, its closing comment carries a **finding index** under the review range: one line per finding, cited by its id qualified with the range (`review 2339177..8424220 R3`): fixed → the commit, filed → the ticket, declined → the assumption id. The agent that merges the branch reads that index, never the reports.

A review's reader is the agent that owns the branch, never the user. What it cannot dispose of alone (a declined finding worth a ruling, a question the review raised) it escalates through its own closing comment, under the worker contract. Fixed findings, per-pass summaries and verification lists stay in the reports, which die with the worktree.

A clean diff gets one line: the range, and that the reviewers came back empty.

## Why one pass per question

A change can pass one question and fail another: code that follows every standard can implement the wrong thing; code that does exactly what the issue asked can break a caller, or the project's conventions; code that is correct, conventional and asked for can sit under tests that would pass without it, so every pass of read comes back clean and tests fails.

So read keeps its passes apart in its report, and each is read and disposed of on its own: one ranked list would let three clean passes bury the one failure. The tests reviewer stands apart from read for another reason: it mutates and runs code in a checkout of its own, which read has no reason to hold in its context.
