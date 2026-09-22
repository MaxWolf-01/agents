---
status: review
---

# A script launches the code-review axes; the skill keeps only the judgment

Cut from the user's review of the one-flow branch (C7): the code-review skill is long because it carries the four reviewer briefs word for word and the mechanics around them (pin the fixed point, compute the range, write the delivery and discipline lines, spawn, wait for the report files). Every caller copies that boilerplate into subagent prompts by hand.

## What to build

A script beside the skill, `review <fixed-point> [--axes correctness,standards,spec,tests] [--spec <path>] [--light]`, that does the mechanics: resolves the fixed point, computes the merge-base range, writes each axis's brief from a template file beside the skill (one file per axis, the delivery and discipline lines included, the standards sources and the spec path substituted), runs the axes as `claude -p` reviewers two at a time with an explicit model, and returns when every report exists under `agent/reviews/<range>/`, naming an axis whose report is missing. The skill shrinks to what needs judgment: which fixed point, where the spec is, light or full, and step 5's dispositions. `make check` runs the script's `--help`; the briefs are the templates, so a change to a brief is one file.

## Acceptance criteria

- [x] `review <fixed-point>` from a branch produces the four report files (or one, with `--light`) and exits nonzero naming a missing one.
- [x] The skill's step 4 is one paragraph pointing at the script; the brief texts exist once, in the templates.
- [x] Demo in the closing comment: one run on a toy branch, the report directory listed, and the skill's line count before and after.

## Comments

`review` beside the code-review skill launches the axes and the skill keeps the judgment: the script resolves the fixed point, pins the range, composes each brief from `briefs/`, runs the axes as `claude -p` reviewers two at a time on an explicit model, and exits nonzero naming an axis that left no report; the skill goes from 113 lines to 81 and the brief texts exist once, in the templates. On branch `ticket/master/review-launcher` (`a4db42a`, `4d24795`, `d7ed489`, `4d583c0`), not merged. The plugin version is not bumped, so this reaches other machines only after a release from the integration branch.

**Demo.** Every transcript below is a real run of the script on this branch; the two runs need `claude` and cost tokens (roughly 6 minutes for the light one, 25 for the axes).

1. A light run over the last commit, one reviewer:

        $ mx/bin/review HEAD~1 --light --model sonnet
        review: 4d24795..d7ed489, light on sonnet, 2 at a time; reports in /home/agent/repos/dispatch/agents-master-review-launcher/agent/reviews/4d24795..d7ed489
        + claude -p --model sonnet --permission-mode manual --allowedTools Read Grep Glob Bash(git *) Edit(//home/agent/.../agent/reviews/4d24795..d7ed489/**) < .../briefs/light.md > .../light.log
        review: the light reviewer exited 0
        /home/agent/repos/dispatch/agents-master-review-launcher/agent/reviews/4d24795..d7ed489/light.md

   The last line is stdout, the report to read; the rest is narration. That report is this branch's round-three review.

2. The report directory, one per range, the briefs the reviewers read beside the reports:

        $ ls agent/reviews/4d24795..d7ed489
        briefs  light.log  light.md

3. The full axes, with this ticket as the spec (three axes, since the diff touches no test files; a test-touching diff adds the fourth):

        $ mx/bin/review "$(git merge-base HEAD master)" --spec agent/tickets/review-launcher.md
        review: 7123d63..a4db42a, correctness, standards, spec on opus, 2 at a time; reports in .../agent/reviews/7123d63..a4db42a
        review: the standards reviewer exited 0
        review: the spec reviewer exited 0
        review: the correctness reviewer exited 0
        .../agent/reviews/7123d63..a4db42a/correctness.md
        .../agent/reviews/7123d63..a4db42a/standards.md
        .../agent/reviews/7123d63..a4db42a/spec.md

4. The refusals, which cost nothing to see:

        $ mx/bin/review HEAD                                   # exit 1
        review: git diff 4d583c0... 4d583c0... is empty; nothing to review
        $ mx/bin/review not-a-ref                              # exit 1
        review: not-a-ref does not resolve in /home/agent/repos/dispatch/agents-master-review-launcher

5. A reviewer that leaves no report, shown on a toy repo with a stub in place of `claude` (the only way to see this path without killing a real reviewer):

        $ review HEAD~1 --light                                # exit 1
        review: d0fdcca..91e1079, light on sonnet, 2 at a time; reports in /tmp/toy2/agent/reviews/d0fdcca..91e1079
        review: the light reviewer exited 1
        review: the light axis left no report at /tmp/toy2/agent/reviews/d0fdcca..91e1079/light.md; its output is /tmp/toy2/agent/reviews/d0fdcca..91e1079/light.log
        review: re-run what is missing, before HEAD moves: review d0fdcca1eb2925b75e93abeca469106ccbba0282 --axes light --model sonnet

6. The skill, before and after:

        $ git show 7123d63:mx/skills/code-review/SKILL.md | wc -lw
        113 2139
        $ wc -lw mx/skills/code-review/SKILL.md
        81 1353
        $ wc -l mx/skills/code-review/review mx/skills/code-review/briefs/*.md | tail -1
        263 total

**I need from you**

- [D1] The standards sources are read at the repo's root and nowhere else, with no flag to add one (A3). A repo with `docs/style.md` or a package-level `CLAUDE.md` beside the code gets reviewers that never see it. Worth a `--standards` flag, a glob, or is root-only the right line?
- [D2] `--out` is gone, so a review run in a throwaway clone writes its reports inside that clone and they die with it (A5). The prose the ticket deleted told the caller to put them in a checkout that survives. Leave it, or wire `/mx:review-pr` to a flag next time it is touched?
- [D3] The reviewers' permission mode is fixed in the script, not a knob (A4): allowed to read, to run git, to write in the report directory, nothing else. Probed on this host: `auto` denies every tool in print mode, `acceptEdits` lets a reviewer edit the tree its siblings are reading. A reviewer that wants `rg` or `cat` loses a turn to a denial and falls back to Read/Grep. Keep it fixed?
- [D4] Acceptance criterion 1 says four reports from `review <fixed-point>`; a bare run gives two (A7). `--spec` is what adds the Spec axis, and a test-touching diff the Tests axis. Should a specless run get a Tests axis at all (it has no Testing Decisions to check against, which is why light mode folds the test-smell baseline into its one reviewer instead)?
- [D5] The script has no test (A9). `make check` reaches `--help`, which is what this ticket asked for; `touches`, `bullets` and `render` are exactly the text-in/text-out seam `dispatch-scripts-under-test` was filed over, and that ticket names only `dispatch` and `dispatch-ctl`. Worth an edge on it?

**Details, if you want them**

- [D6] `Assumptions`

  - A1 `mx/skills/code-review/SKILL.md:36`: step 3 folded into the script, since the ticket's list of what the skill keeps does not name it. What stays under that heading is a pointer to what binds a review, for a reader disposing findings in step 5, not a step the caller runs; it keeps the number because `worker-prompt.md` and `/mx:review-pr` both name "step 5".
  - A2 `mx/skills/code-review/briefs/preamble.md:1`: the delivery and discipline lines live in one preamble template rather than in each axis file, so no line of brief text is written twice; the light brief is preamble + correctness + standards + a note of its own, which is why the fold carries no copy of either brief.
  - A3 `mx/skills/code-review/review:112`: five filenames at the repo root are the whole of a repo's own standards sources, and there is no flag to add one. Declined the review's `--standards` finding as unexercised; the skill and `--help` now say root-only, so a caller in a repo it does not fit can see it.
  - A4 `mx/skills/code-review/review:30`: `--permission-mode manual` with allow rules for reading, git and the report directory, fixed in the script rather than inherited from the session or taken from an env knob.
  - A5 `mx/skills/code-review/review:7`: no `--out`, against the usage line I first shipped: nothing in the repo passed it, and the failure path forgot to print it. A PR review's reports now live in the clone the review ran in.
  - A6 `mx/skills/code-review/SKILL.md:48`: the model stays the skill's judgment (`--model`), which the ticket's list of what the skill keeps does not name either; the script defaults it (Opus, Sonnet under `--light`) so a caller that says nothing still gets an explicit model.
  - A7 `agent/tickets/review-launcher.md:15`: the criterion is ticked for the substance, not the count: `review <fixed-point>` runs correctness and standards, `--spec` adds the Spec axis, and a diff touching test files adds the Tests axis.
  - A8 `mx/skills/review-pr/SKILL.md:17`: the prior PR discussion travels inside the spec file now, since the briefs are fixed templates. Declined a `--context` flag; that skill's step 3 says so and the Spec brief tells the reviewer a point the discussion settled is not a finding.
  - A9 `mx/skills/code-review/review:1`: no test for the script, `make check`'s `--help` as the ticket asked.

- [D7] Findings, three rounds. Round one ran the full axes against `7123d63..a4db42a` with this ticket as the spec; rounds two and three ran light over each round's own fixes, since by then the diff was the review's own.

  Round one, `7123d63..a4db42a`, 28 findings, fixed in `4d24795`:

  - the reviewers got `git diff <fixed-point>...HEAD`, resolved minutes later in their own processes, so a caller committing meanwhile moved the diff out from under them → fixed, both ends pinned once
  - `acceptEdits` auto-approved every write, so the report-directory rule narrowed nothing and concurrent reviewers could edit the tree they were reading → fixed, `manual`, probed
  - inheriting `DISPATCH_PERMISSION_MODE` handed a dispatch worker's review `auto`, which denies every tool in print mode: every review on a non-isolated host would have come back empty → fixed with the same change
  - commit messages were substituted into the brief and then rescanned for placeholders → fixed, the check reads the templates and the commits go in last
  - a specless full run got less test scrutiny than `--light` → fixed, the test-smell baseline reaches whoever reads the tests when no Tests axis runs
  - an earlier run's report on disk read as this run's → fixed, expected reports go before the reviewers start
  - a relative `--spec` resolved against the repo root, not the caller's cwd → fixed
  - the uncommitted-work warning saw tracked files only → fixed, `git status --porcelain`, the reports excluded
  - `*.brief.md` sat among the reports, so an aggregator globbing `*.md` read the briefs as reports → fixed, `briefs/` under the range
  - the process-document test missed output styles and commands → fixed, then narrowed again in round two
  - the `claude -p` line was never echoed, where both dispatch scripts echo what they run → fixed
  - `--out` and `REVIEW_PERMISSION_MODE` unexercised → fixed, both dropped (A5)
  - `/mx:review-pr` promised its reviewers the prior discussion and the fixed templates left no channel → fixed, the spec file is the channel (A8)
  - the skill's step 3 fold had lost the condition on the test-smell baseline and stated the opposite of the script → fixed, bullets again
  - eleven prose findings across the skill and the briefs (a usage line and model defaults cached off `--help`, the preamble forbidding what the allow rules prevent, unintroduced baselines, a decision-against, duplicated statements of the light fold, the frontmatter still saying "parallel") → fixed
  - no `--standards` escape hatch → declined, A3
  - the allow rule's `//abs/path` form read as a doubled-slash bug, and a missing `Write(...)` rule → declined: that is this setup's absolute-path form (`claude/settings.json`), and the CLI refuses `Write(...)` rules because `Edit(...)` covers every file-editing tool; probed
  - step 3 numbered among the steps while containing no step → declined, A1
  - the axis questions appearing in both the skill's overview and the brief headings → declined, the overview case `SMELLS.md` allows

  Round two, `a4db42a..4d24795`, light on Opus, 9 findings and 6 judgement calls, fixed in `d7ed489`:

  - `TEST-SMELLS.md`'s own first line still told a Standards reviewer the baseline binds it "in light mode", the rule round one replaced, in a file the reviewer is told to read in full → fixed
  - the Standards brief listed its baselines by filename and left the test-smell one out of the report instruction → fixed
  - it sent the reviewer to `SMELLS.md` for a hard-versus-judgement split that lives in the prose catalogue → fixed
  - `render` catted its parts without checking they exist, so a renamed `preamble.md` bought a truncated brief and a full reviewer session → fixed
  - the placeholder guard scanned the concatenation and blamed one file → fixed, per part
  - the guard's allowed-placeholder list was a copy of the substitutions below it → fixed, only the commit messages are held back now
  - the printed re-run command was the caller's fixed point, which re-resolves → fixed, the merge-base, and it says to re-run before HEAD moves
  - `--help` carried the probe that chose the permission mode → fixed, the probe is in the commit message
  - the process-document test matched any repo's `src/agents/` or `briefs/` → fixed, this workflow's surfaces only
  - six prose calls (an aphorism, a 55-word step 4, a stale locative, prose restating the line under it, a property where an action belonged) → fixed

  Round three, `4d24795..d7ed489`, light on Sonnet: correctness clean, one standards finding, the test-smell bullet still naming the Standards axis as its only other reader → fixed, `4d583c0`.

- [D8] Friction

  - This host has no `python3`. An inline edit script written as a `python3` heredoc failed with "command not found" and, because the shell reported only that line, looked at first like it had applied; the next read of the file caught it. `~/HOST.md` lists `uv` and not `python3`, which is accurate, and a worker reaching for a scripting language reads that list as what is there rather than what is not.
  - `job probe` prints every job this host has ever run, ninety-odd lines from other features' sessions, so reading my own status is a `grep` away. A filter, or a prune of finished jobs, would make the one line I want the answer.
  - `claude --allowedTools` is variadic: with the prompt as an argument after it, the flag swallows the prompt and the CLI fails with "Input must be provided either through stdin or as a prompt argument". The brief goes in on stdin, which is what `run-worker.sh` already does; worth knowing for the next `claude -p` launcher.
  - A review takes 6 to 25 minutes, over this session's own 600-second tool ceiling, so every round runs under `job` and needs two or three waits. Nothing broke; it is the shape of the loop, and `job wait --deadline` is what makes it legible.
