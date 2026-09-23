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

`review` beside the code-review skill launches the axes and the skill keeps the judgment: the script resolves the fixed point, pins the range, composes each brief from `briefs/`, runs the axes as `claude -p` reviewers two at a time on an explicit model, and exits nonzero naming an axis that left no report; the skill goes from 113 lines to 81 and the brief texts exist once, in the templates. On branch `ticket/master/review-launcher` (`1922f9b`, `0047995`, `274c595`, `8d7908e`), not merged. The plugin version is not bumped, so this reaches other machines only after a release from the integration branch.

**Demo.** *Superseded by the amend round's demo at the bottom of this ticket: the axes no longer run two at a time and the Tests axis now runs in a checkout, so the transcripts below are this round's record and not what the script prints today. The steps still run.*

Every transcript below is a real run of the script on this branch; the two runs need `claude` and cost tokens (roughly 6 minutes for the light one, 25 for the axes).

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
  - A3 `mx/skills/code-review/review:146`: five filenames at the repo root are the whole of a repo's own standards sources, and there is no flag to add one. Declined the review's `--standards` finding as unexercised; the skill and `--help` now say root-only, so a caller in a repo it does not fit can see it.
  - A4 `mx/skills/code-review/review:30`: `--permission-mode manual` with allow rules for reading, git and the report directory, fixed in the script rather than inherited from the session or taken from an env knob.
  - A5 `mx/skills/code-review/review:7`: no `--out`, against the usage line I first shipped: nothing in the repo passed it, and the failure path forgot to print it. A PR review's reports now live in the clone the review ran in.
  - A6 `mx/skills/code-review/SKILL.md:49`: the model stays the skill's judgment (`--model`), which the ticket's list of what the skill keeps does not name either; the script defaults it (Opus, Sonnet under `--light`) so a caller that says nothing still gets an explicit model.
  - A7 `agent/tickets/review-launcher.md:15`: the criterion is ticked for the substance, not the count: `review <fixed-point>` runs correctness and standards, `--spec` adds the Spec axis, and a diff touching test files adds the Tests axis.
  - A8 `mx/skills/review-pr/SKILL.md:17`: the prior PR discussion travels inside the spec file now, since the briefs are fixed templates. Declined a `--context` flag; that skill's step 3 says so and the Spec brief tells the reviewer a point the discussion settled is not a finding.
  - A9 `mx/skills/code-review/review:1`: no test for the script, `make check`'s `--help` as the ticket asked.

- [D7] Findings, three rounds. Round one ran the full axes against `7123d63..a4db42a` with this ticket as the spec; rounds two and three ran light over each round's own fixes, since by then the diff was the review's own.

  Round one, `7123d63..a4db42a`, 28 findings, fixed in `0047995`:

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

  Round two, `a4db42a..4d24795`, light on Opus, 9 findings and 6 judgement calls, fixed in `274c595`:

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

  Round three, `4d24795..d7ed489`, light on Sonnet: correctness clean, one standards finding, the test-smell bullet still naming the Standards axis as its only other reader → fixed, `8d7908e`.

- [D8] Friction

  - This host has no `python3`. An inline edit script written as a `python3` heredoc failed with "command not found" and, because the shell reported only that line, looked at first like it had applied; the next read of the file caught it. `~/HOST.md` lists `uv` and not `python3`, which is accurate, and a worker reaching for a scripting language reads that list as what is there rather than what is not.
  - `job probe` prints every job this host has ever run, ninety-odd lines from other features' sessions, so reading my own status is a `grep` away. A filter, or a prune of finished jobs, would make the one line I want the answer.
  - `claude --allowedTools` is variadic: with the prompt as an argument after it, the flag swallows the prompt and the CLI fails with "Input must be provided either through stdin or as a prompt argument". The brief goes in on stdin, which is what `run-worker.sh` already does; worth knowing for the next `claude -p` launcher.
  - A review takes 6 to 25 minutes, over this session's own 600-second tool ceiling, so every round runs under `job` and needs two or three waits. Nothing broke; it is the shape of the loop, and `job wait --deadline` is what makes it legible.

---

The amend round. Ruled by you: the two-at-a-time cap is gone, and every selected axis starts at once. Built for you to rule on: the Tests reviewer gets a checkout of its own, `agent/reviews/<range>/checkout`, a worktree of the pinned tip that the script adds before that reviewer starts and removes when it ends, whichever way it ends. It starts there, mutates code there, runs the project's test command there; the tree you work in and the trees the other axes read are not writable by any reviewer. On the same branch (`45c39cb`, `04c97f6`, `1e100d4`), still not merged, still unreleased. The ruling reached me relayed rather than as page comments, so this round marks none of them resolved.

**The allow rules**, which you asked to be told. Every reviewer: `Read`, `Grep`, `Glob`, the read-only git subcommands named in the script's `git_reads` list, and `Edit` under `agent/reviews/<range>/**`, on `--permission-mode manual`, which refuses everything else without asking. The Tests reviewer also gets the test targets named in `runners` (`make test`, `make check`, `nix develop -c make test`, `pytest`, `npm test`, `node --test`, `cargo test`, `go test`, and `uv run`/`uvx`, the two standing exceptions `/mx:permissions-review` names), plus `git restore`, which reaches only the checkout it stands in. Its checkout sits **inside** its report directory, so the one `Edit` rule covers both the code it mutates and the report it writes, and everything outside that directory stays unwritable. Named by subcommand and test target rather than by tool, because `/mx:permissions-review`'s bar is that a wildcard over anything that runs code allows everything; the first cut of this used `make *`, `python3 *` and eleven more like them, and the review caught it.

**Demo**, all of it real output from this branch's script.

1. The Tests axis with its checkout, on a toy repo whose one test asserts `add(1, 2) is not None` against `def add(a, b): return a + b`, with a spec naming the seam and one executable property (`/tmp/calc`, two commits, `make test` = `PYTHONPATH=. uv run --with pytest pytest -q`):

        $ review HEAD~1 --axes tests --spec spec.md --model sonnet
        + git worktree add --detach /tmp/calc/agent/reviews/60d2279..a8ed1ab/checkout a8ed1ab...
        review: 60d2279..a8ed1ab, tests on sonnet; reports in /tmp/calc/agent/reviews/60d2279..a8ed1ab
        + (cd /tmp/calc/agent/reviews/60d2279..a8ed1ab/checkout && claude -p --model sonnet --permission-mode manual --allowedTools ... < .../briefs/tests.md > .../tests.log)
        review: the tests reviewer exited 0
        review: the Tests reviewer's checkout is removed
        /tmp/calc/agent/reviews/60d2279..a8ed1ab/tests.md

   and the report it left, which is the point of the checkout:

        **Mutation evidence** (run from this checkout, `calc.py` restored with `git restore` after each):
        - Mutated `add` to `return a - b` (wrong operator) → `make test` still reports `1 passed`.
        - Mutated `add` to `return 0` (ignores both arguments) → `make test` still reports `1 passed`.

   `git status` in the toy repo afterwards: clean. `git worktree list`: one entry, the repo itself.

2. Every axis at once, stubbed so the timing is the only thing measured (four axes, each stub sleeping three seconds):

        $ time review fb5d592~1 --spec agent/tickets/review-launcher.md
        review: 685e1bc..cf5b230, correctness, standards, spec, tests on opus; reports in .../agent/reviews/685e1bc..cf5b230
        ... 3.2s total, where the cap made it 6s

3. The refusals the round added, both from this worktree:

        $ review <base> --axes tests --spec <spec>          # with a checkout already there
        review: .../checkout is already there, from a review of <range> still running or killed; when none is running: git worktree remove --force .../checkout
        $ review <base> --axes tests --spec <spec>          # with a typo in briefs/tests.md
        review: briefs/tests.md asks for {{NOPE}}, which this script does not substitute
        # and no checkout is left behind by that one

4. The boundary, probed with a live reviewer session in a checkout made exactly as the script makes one, given exactly the rules above:

        1. Read ../../../PRINCIPLES.md              → ran, quoted "# Workflow principles"
        2. Edit the checkout's Makefile             → ran
        3. make check                               → ran
        4. Write into the worker's tree             → blocked
        5. touch /tmp/probe-escaped                 → blocked
        6. git restore Makefile                     → ran
        7. git commit -am probe                     → blocked
        8. git stash list                           → blocked

   Afterwards: no `PROBE-ESCAPED.md`, no `/tmp/probe-escaped`, and `git status` in the worker's tree showed only my own edits.

**I need from you**

- [D9] The Tests axis runs the tip's own test files and build recipes; that is what running a suite is, and the checkout bounds where the code sits rather than what it can reach (A13). `/mx:review-pr` now says to leave the axis off an incoming PR unless you would run that PR's suite on this machine anyway. Is that the right line, or should the axis be barred from an untrusted tip outright, or only run on an isolated host?
- [D10] A fresh checkout holds what the commit holds and no reviewer can install into it, so a suite needing `npm install` or `uv sync` gets reported rather than run (A12). `dispatch-ctl` solves the same problem by running the project's setup command in every worktree it makes. Should the script do that too, at the cost of a build per Tests axis?
- [D11] `git restore` is a state mutation, which the permissions bar says never to allowlist; it is in the Tests reviewer's rules because it is how a mutation is undone between runs, and it cannot reach past the checkout the reviewer stands in (A11). Keep it?
- [D12] A checkout already at the path now refuses the run, naming the recovery, because a live review and a killed one look identical from here (A14). The cost is a manual `git worktree remove` after a killed run. Worth a lock file that tells them apart?

**Details, if you want them**

- [D13] `Assumptions`, continuing from A9

  - A10 `mx/skills/code-review/review:227`: the script owns the checkout's whole life, where the ruling had the reviewer create it: a reviewer that dies mid-run would otherwise leave a worktree registered in your repo, and the removal would have to live here anyway. It is added after the briefs render, so a template error costs nothing, and removed by the same subshell that ran the reviewer.
  - A11 `mx/skills/code-review/review:64`: the Tests reviewer's extra rules are the test targets by name plus `uv run`/`uvx`, and `git restore`. Supersedes A4 for this axis: "nothing else" now means nothing outside that list, and the list runs the tree's own code by design.
  - A12 `mx/skills/code-review/briefs/tests.md:12`: the checkout is the commit as committed, and a suite that cannot run without an install is a line in the report rather than an install the reviewer performs.
  - A13 `mx/skills/review-pr/SKILL.md:18`: an incoming PR's Tests axis is the caller's call, taken in `/mx:review-pr` rather than by a rule in the script, since only the caller knows whether that tip is one they would run tests from.
  - A14 `mx/skills/code-review/review:233`: a checkout already at the path refuses the run instead of being removed, because removing it blind would pull the tree out from under a reviewer still using it.

- [D14] Findings, two rounds over the amend, both light on Opus since the diff is the review's own.

  Round one, `4d583c0..268ac52`, eight findings, fixed in `04c97f6`:

  - `runners` allowlisted thirteen tools by wildcard (`make *`, `python3 *`, `node *`, ...), which `/mx:permissions-review` names as equivalent to allowing everything, so the containment the checkout exists for did not hold and an incoming PR's Makefile would have run on your machine → fixed, both lists name subcommands now, `Bash(git *)` included
  - a checkout left by a killed run was removed blind, which would have pulled the tree out from under a live reviewer of the same range → fixed, it refuses and names the recovery
  - `drop_checkout` reported removal whichever way it went, so a checkout still standing read as gone → fixed, three outcomes, git's reason included
  - the checkout is never set up, so a suite needing an install had nowhere to get it → the brief says so, A12, and D11 is the open half
  - `--help` pointed at a `runners` list it does not print → fixed, it names where the list is
  - the Tests brief carried five prose tells and a restore with no reason → fixed, rewritten with the why
  - the axis overview carried the mechanism → fixed, it carries what the caller needs instead
  - this ticket's first comment describing the script two versions back → fixed, its demo is marked superseded above and this round carries the current one

  Round two, `268ac52..4e06139`, four findings and two nits, fixed in `1e100d4`:

  - `Bash(git grep *)` was still arbitrary code execution, in every reviewer, in your worktree: `git grep -O<cmd>` hands the command to a shell. Probed here → fixed, the entry is gone and searching is the Grep tool's
  - six rules had only their starred form, and a trailing glob wants an argument, so bare `pytest`, `cargo test` and `go test` were denied: the axis would have lost its mutation evidence to a denial → fixed, both forms
  - a brief that fails to render left an orphan checkout, which the new refusal then made permanent for every later run → fixed, the checkout comes after the briefs
  - running a suite runs the author's build files, and nothing a caller reads said so → fixed in `--help`, the skill and `/mx:review-pr`, and D10 is the open half
  - "a mutation the suite passes" read backwards, and `runners` had lost its locative → fixed

  Not re-argued: `git diff --output=<path>` writes outside the report directory, which `claude/settings.json` already grants globally, and the axis overview naming what the Tests axis does, which round one of the first build declined as the overview case.

- [D15] Friction, this round

  - The two rounds of review on the amend cost two more `claude -p` fleets and about 25 minutes, and each round's fixes are what the next round reads. The thing that made them pay was the reviewer probing live (`git grep -O` is not something a reading of the list would have caught), which is the same reason the Tests axis now gets a checkout.
  - `/mx:permissions-review` holds the bar this round twice failed against, and nothing pointed at it from where the rules were being written: it is a skill about scanning transcripts for prompts, so neither `/mx:orient` nor the code-review skill mentions it, and a worker writing an allowlist finds it only by having read it before. Its Safety bar section is the part that binds anyone writing a permission rule anywhere.

---

The rebase round. `master` moved: every-property-gets-a-criterion landed there and edited the Spec reviewer's brief inside the skill, which this branch had already moved into `briefs/spec.md`. Rebased onto `7176f6e`, nine commits replayed, one conflict, in the skill's steps 3 and 4 where this branch's fold had replaced the text master edited. Three of master's edits landed on text this branch moved, and all three are settled:

- "checked against the diff by name" is now "by its id", in `briefs/spec.md`, which is where that brief lives.
- Master's fifth standards source, `CONTEXT-FORMAT.md` and `ADR-FORMAT.md` when the diff touches a glossary (`CONTEXT.md`, `CONTEXT-MAP.md`) or an ADR (`decisions/`), with `glossary-lint` on every touched glossary: the script gathers both files behind that same test, the Standards brief carries the instruction, the skill's step-3 list carries the bullet and its why, and the Standards and light reviewers get `glossary-lint` in their allow rules when the test fires and not otherwise (A15).
- "a `/tmp` clone" became "a fresh clone" in the delivery line, a sentence this branch deleted along with `--out` (A5). The decision it carries still stands where master put the rest of it, `/mx:review-pr` step 2, which this branch leaves alone. Nothing to carry.

The commits are the same work at new SHAs: the lists above name the rebased ones, and each round's range label is the pre-rebase range its reviewers actually read, kept as the record of what was reviewed.

`master` then moved twice more while this round ran, `6cf0250` and `7093bf7`, both of them the render-lint-html-overlap ticket and neither touching a file this branch touches. This branch sits on `7176f6e` rather than chasing a branch that moves, and `git merge-tree master HEAD` reports the merge clean.

**Demo.** The verification, all of it from this worktree after the rebase:

        $ make check
        manifests parse, hooks point at executables, bin/ answers --help
        $ make test
        128 passed in 24.44s            # master's glossary-lint and property-coverage tests included

        $ review <a range touching CONTEXT.md> --spec agent/tickets/review-launcher.md    # claude stubbed
        review: 6603216..8294d82, correctness, standards, spec, tests on opus; reports in .../agent/reviews/6603216..8294d82
        $ grep FORMAT.md .../briefs/standards.md
        - .../mx/skills/domain-modelling/CONTEXT-FORMAT.md
        - .../mx/skills/domain-modelling/ADR-FORMAT.md
        $ grep -o 'Bash(glossary-lint[^)]*)' .../standards.log
        Bash(glossary-lint) Bash(glossary-lint *)
        $ grep -c glossary-lint .../correctness.log
        0
        $ grep -c 'by its id' .../briefs/spec.md
        1

        $ review HEAD~1 --light                                                           # claude stubbed
        $ grep -c glossary-lint .../light.log     # a range touching no glossary and no ADR
        0

   The Tests axis in that first run took its checkout and gave it back, as it does on any range: `git worktree list` afterwards holds this worktree and nothing of the review.

**I need from you**: nothing new. D9 to D12 stand as they were.

**Details, if you want them**

- [D16] `Assumptions`, continuing from A14

  - A15 `mx/skills/code-review/review:59`: `glossary-lint` reaches the Standards and light reviewers as an allow rule, gated on the same test that adds the two format files, and it is the one command outside git and the test targets any reviewer may run. It reads and reports, the workflow owns it, and the axis handed a format it checks by hand should not be denied the mechanical half of it.

- [D17] Friction

  - A ticket comment that names commits goes stale the moment the branch is rebased, and this one named nine. Nothing catches that: the review page renders from `diff:` ranges the orchestrator writes, and the prose around them is on its own. Rewriting them by hand is what this round did.

**2026-09-23** Ruled by the user on review, from the calls page (`~/Downloads/show/review-launcher-calls/`):

- D113, replacing D58: one review of a range runs at a time, held by a `flock` on `agent/reviews/<range>/.lock` that the kernel releases when the run and its reviewers die. A checkout under a range whose lock is free belongs to a dead run and is removed at the next start, so a killed or crashed review never blocks a later one. `test_review.py` holds it.
- D114: a reviewer starts from none of the caller's setup (`--setting-sources ""`, no MCP servers, no skills, no auto-memory, the five file and shell tools).
- D115: every reviewer runs Opus, `--effort high` by default; `--effort` is the knob the skill leaves the caller. The other unattended launches move together in `unattended-launch`.
- D116: the skill's description carries only its triggers.
