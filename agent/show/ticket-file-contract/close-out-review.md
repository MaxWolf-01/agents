# Light review: 4f18476..ece4c0f (ticket-file-contract, the whole tree)

One reviewer, three briefs: correctness, standards, and the ticket's context at `/var/tmp/ticket-file-contract-context.md`.

**What I could not run.** Running `tracker`, `glossary-lint` and the suites needed approval in this session and didn't get it. So every finding below comes from reading the code, the callers and the tests, and none from a run. `glossary-lint CONTEXT.md` is still owed. I checked the glossary by hand against CONTEXT-FORMAT.md below.

Findings are ordered by consequence. Each one gives the scenario, the location and the fix.

---

## Correctness

### C1. A resumed round's finished signal is the previous round's report (high)

`mx/skills/dispatch/run-worker.sh:45` treats the run as finished when the report exists at `HEAD`:

```
reported() { git -C agent cat-file -e "HEAD:show/$slug/report.md" 2> /dev/null; }
```

`dispatch review` imports any report on the agent tip whenever the ticket is `claimed` (`mx/skills/dispatch/dispatch:620-627`). Every round after the first starts with round one's report already committed on `ticket/<slug>`. That holds for an amend, and for a red merge that resumes the worker with "rebase ... report again" (`dispatch/SKILL.md:32-33`, and `dispatch-ctl:55-57`: "The round commits a report of its own, over the one the round before it left").

What breaks:

- A resumed run whose `claude` exits nonzero before the worker writes anything hits `reported && break` (`run-worker.sh:97`). It skips its retries and writes `report=yes` (`:111`). The probe then tells the orchestrator a finished report exists.
- A resumed worker that blocks and follows `worker-prompt.md:8` ("leave the report uncommitted, since its absence is what says the run left nothing to review") can't signal it, because a report is already there.
- In both cases `reclaim` has put the ticket back to `claimed` (`dispatch:293-297`), so `dispatch review` imports round one's report a second time. Round one's closing comment lands under `## Comments` twice. If that report asked any `[Dn]` question, the import is refused with "tag Dn is already taken" (`tracker.py:1333-1339` via `caused`), and `dispatch review` exits 1 with a message that points at the tags and not at the stale report.
- `worker-prompt.md` never says a later round replaces the file with that round's comment only. A worker editing the file it wrote in round one will likely keep round one's text in it, which hits the same duplicate-tag refusal.

No check covers a resume: `test_dispatch.py` spawns once per test.

**Fix:**

1. The runner records the report's blob at start (`git -C agent rev-parse -q --verify HEAD:show/$slug/report.md`) and counts the run as reported only when the blob differs at the end.
2. `dispatch review` imports only a report whose blob differs from the last one it imported. It can keep that blob beside the run record, or read it from the `for review` commit.
3. The contract says each round's report holds that round's closing comment and new questions only, and replaces the file.
4. Add a test: resume with the report unchanged, and check it yields `report=no` and no second import.

### C2. On a local host, a worker's `tracker` write lands uncommitted in the orchestrator's live tracker (medium, P7)

`tracker_root` resolves the agent repo's main checkout from any worktree (`tracker.py:1417-1431`). `test_tracker.py:1233-1250` asserts that a worker's worktree reads, and by the same path writes, `split/agent/tickets`.

On `--host local`, the worker's worktrees are linked worktrees of the user's own two repos, and `tracker` is on the worker's PATH because the plugin is enabled. So `tracker set <slug> status=review`, `rule`, `new` or `import` run by a worker writes straight into the orchestrator's working copy. Three guards miss it:

- The commit hook refuses only staged files on a `ticket/` branch (`tracker.py:93-94`). This write is on no branch.
- `dispatch review`'s guard diffs only the agent branch (`dispatch:611-613`).
- The next `commit_ticket` for that slug (`git commit -- tickets/<slug>.md`, `dispatch:113`) sweeps the worker's edit into the orchestrator's commit under its message.

P7 ("A worker never writes a ticket file") is then enforced only by the prompt. The Testing seams quote the source seam as "nothing a worker host holds writes a ticket file", but `test_p7_no_file_a_worker_host_holds_reads_or_writes_a_ticket` (`test_tracker.py:909-921`) only checks the three staged dispatch files. The host holds the whole plugin, `mx/bin/tracker` included.

**Fix:** the write commands (`new`, `set`, `rule`, `import`, `drop`, `retire`) refuse when the working directory's own checkout, in either repo, has a `ticket/` branch out. That is the same test `ticket_branch_out` makes for `check`. Add a check that runs `tracker set` from a worker's worktree and expects the refusal.

### C3. `repos_of` treats a linked worktree and the main checkout of one repo as two repos (medium, until this repo's split)

`tracker.py:416-426`: `agent = toplevel(tracker.root)` and `code = toplevel(cwd)`, compared as paths. In a project whose `agent/` isn't split yet (the "One repo where the project's `agent/` is not one of its own yet" case the docstring promises), `tracker root` is the main checkout's `agent/tickets`. Run from the parent ticket's worktree, the two paths differ, so the function returns `[worktree, main checkout]`, which is one repo twice.

`unlanded` (`:397-405`) then checks the child's `ticket/<slug>` against the main checkout's `HEAD`, which is master, and refuses `done` with "is not merged into master" after it has correctly merged into the parent ticket's branch. This repo is in that layout now, and stays in it until the close-out split, the step the ticket orders "once this ticket's work is on master".

**Fix:** compare `git rev-parse --git-common-dir` rather than toplevels, and when both share one, return the cwd's checkout alone.

### C4. The board's watcher keys its "repo moved" on the agent repo while the page's log is the code repo's (low)

`board.py:256-265` renders `git_log(code)` with `code = project(root)`. The watcher's snapshot takes `git(repo, "rev-parse", "HEAD")` (`board.py:627`), where `repo` defaults to the agent repo (`:221`). Its docstring still says "the commit the log comes from" (`:619-620`).

As a result, a commit or merge in the code repo that touches no ticket leaves the page's commit list stale until something under the tracker moves. `changed_note` also tells the briefing session "the repo has moved on: …" with the agent repo's last commit (`:529-530`) on every ticket commit, while that session explores the code project.

**Fix:** snapshot `project(root)`'s `HEAD` (or both repos' heads), and read `changed_note`'s line from the project.

### C5. `dispatch --help` says review refuses either branch; the code checks one (low)

`dispatch:73` says "refuses either branch that wrote a ticket file". The guard at `:611-613` diffs only the agent branch's `tickets`. The code repo ignores `agent/`, so reaching it takes a `git add -f`. The help is still the reference an orchestrator reads.

**Fix:** say "the agent branch", or add the same diff over `agent/tickets` in the code repo.

### C6. Every landing prints a false "not imported" line (low)

On the second `dispatch review` after the merge, the ticket is `review` and the report is still on the branch. So `dispatch:628-629` prints "`<id>` is review, so the report on `ticket/<id>` was not imported; a report lands once, on the build that is claimed". That was already done on the first run. It appears on every landing, and after C1's fix it is the line that would hide a real skip.

**Fix:** stay silent when the status is `review` or `done`, and warn only for `open`/`proposed`.

### C7. `notes_of` reads the tracker's own file through stdin, so a refusal names `-.md` (low)

`dispatch:676` pipes `$ticket` into `tracker data -` (`:578`). For stdin, `tracker.py:156` builds `Path("-.md")`, so a refusal reads `-.md:12: …` with no file the user can open. It also skips reference checks ("nobody's to resolve"). That stdin form was for reading a ticket off a branch, and `data`'s docstring still says so (`tracker.py:133`: "as a review page does from a ticket branch"). The ticket is now always the tracker's own file.

**Fix:** `notes_of` calls `tracker data "$id"` (or the path), and the docstring drops the branch clause.

---

## Standards

Hard violations first, then judgement calls.

**S1. Hard, writing-for-humans CATALOGUE rule 13 (punctuation binds hard).** `mx/skills/dispatch/worker-prompt.md:13`, added by this diff:

> everything under `agent/show/<slug>/` -- your demo, its figures, your report -- in the second

This is a hyphen-as-dash substitute ("no parentheses, no en dashes, no hyphen-as-dash substitutes"). Rewrite it with commas or as a second sentence. The `--` pair in `dispatch-ctl:10` predates the diff; it was only rewrapped.

**S2. Judgement call: Inconsistency, two answers to "what a refusal names when a ticket arrives on stdin".**

- `tracker.py:156`, `data -`: `Path("-.md")`
- `tracker.py:510`, `import -`: `Path(called or "<stdin>")`, plus a `--called` flag

Both were added by this diff. Pick one: `--called` on both, or `<stdin>` on both. C7 removes `data -`'s only caller, which may settle it.

**S3. Stale docstrings (Conversation Residue / Restated Fact gone stale).**

- `tracker.py:1408-1410` `find_tracker`: "what the commit hook answers for, since a commit is made of one repo's staged files". The hook uses `staged_tracker` (`:1391`), and `find_tracker` is now only `tracker_root`'s fallback.
- `tracker.py:733` and `test_tracker.py:1368-1370`: `hook` accepts "a bare one included" because "The repo dispatch stages on a worker host is bare". Since r8 a worker host gets no hook (project-setup `:16`, and the ticket's amended decision), and `dispatch-ctl init` no longer calls it.
- `test_dispatch.py:283`: "One ticket end to end, the tracker in either repo". That is the `mx.tracker` shape the r8 ruling removed; the tracker is only ever the agent repo now.
- `board.py:619-620`, see C4.

**S4. Judgement call: Speculative Generality.** `tracker hook [repo]` (`tracker.py:725-744`) keeps its positional for a bare repo whose only caller, `dispatch-ctl init`, is gone. Project-setup's one install runs in the agent repo, which `tracker hook agent`, or a `cd`, covers. **Fix:** collapse it to the working directory's repo, or keep it and drop the bare-repo prose and check.

**S5. Judgement call: Implementation-Coupled Test.** `test_dispatch.py:494-500` asserts literal source strings: `'HEAD:show/$slug/report.md'` in the runner and `"reported=show/$id/report.md"` in dispatch. Renaming `$id` breaks it with no behaviour change. Behaviour tests already exercise both paths: the runner test (`:388-424`) with the real `run-worker.sh`, and the end-to-end import (`:281-345`). Only the prompt, which is prose, needs the source seam. **Fix:** keep the `worker-prompt.md` assertion and drop the two script greps.

**Glossary (CONTEXT-FORMAT.md, by hand; `glossary-lint` not run).**

- The new entries (**Agent repo**, **Parent ticket**, **Child ticket**, **Ticket context**, **Worker report**, **Call mark**) are each under 40 words and carry qualifiers in their names.
- **Agent repo** uses an `_In code_` line correctly.
- **Parent ticket**'s done rule is mechanism under "Definitions survive redesign", but the ticket's Decisions ask for exactly that clause ("the parent ticket is done once every child ticket is done and its own close-out is ruled"), so it is settled. No finding.

---

## Against what the ticket asked for

### (a) Missing or partial

**A1. Research: committed per the ticket, gitignored per four places in the diff.** The decision reads:

> `agent/` is always its own git repo ... tickets, their claim, review and done commits, show directories, prototypes and research notes are all committed there

`mx/skills/research/SKILL.md:13` agrees ("in the agent repo"). These say the opposite:

- `mx/skills/project-setup/SKILL.md:15` puts `research` in the agent repo's `.gitignore`.
- `mx/skills/orient/SKILL.md:18` and `mx/README.md:88` keep "gitignored, ephemeral".
- `claude/CLAUDE.md:37` and its copy at `worker-prompt.md:47` say "`agent/research/` investigation snapshots (gitignored)".

Either the decision is amended or those five lines change. Retire already handles both cases (`tracker.py:588-594`).

**A2. Loose work in two repos is left unstated, and one sentence is now wrong.** `mx/skills/tracker/SKILL.md:81` says: "its show directory and the prototypes it made are `git rm`'d on the branch itself, so the merge that lands the work carries the removal". In the ruled shape, the loose branch is a code-repo branch and its show directory is committed in the agent repo (`show/SKILL.md:35`: "`git -C agent` is what commits it"). A code merge can't carry an agent-repo removal. Nothing says which agent branch a loose session commits `agent/show/<branch>/` on, or what its review page ranges are (`orient/SKILL.md:32`). Whatever the answer, P8 depends on it.

**A3. The tracker skill is back above half.** The decision says "The skill shrinks to at least half its size". The prose ticket closed at A12 with "1,490 words against the 3,116 its two held, which is 48%". Measured with `wc -w`, `mx/skills/tracker/SKILL.md` was 1,535 words at `a6c11d7` and is 1,620 now: about 52% of the 3,116 baseline. The r7/r8 paragraphs (The tree, the agent repo) account for the growth.

**Not a finding, a reminder:** the ruling "The release that ships this is a major version" is outstanding. `plugin.json` is still `0.1.73`, and per CLAUDE.md the bump is `make release-major` at release time.

### (b) Built but not asked for

- S4 (`tracker hook`'s bare-repo positional).
- `dispatch-ctl`'s fuzz worktree also cuts a `fuzz/<base>` branch in the agent repo and checks it out (`dispatch-ctl:65-69`, `:411-416`, via `checkout`). The fuzz run reads no ticket and writes no report. This is harmless but unexercised: it's one more branch to clean up on every host.

### (c) Implemented, but looks wrong

- **P7**, "executable at three [seams]": the commit-check and dispatch seams hold. The source seam is narrower than its wording, and the local-host path goes around all three (C2).
- A report is described as the finished signal, but that is only true of a first round (C1).
- The claim that `tracker` supports a project "not ... one of its own yet" breaks from a linked worktree (C3).

### (d) Properties disposed as *reviewed*

The Testing seams line these come from:

> P5 and P8 are reviewed: by each child ticket's review and by this ticket's close-out.

**P5**, "No skill, script or glossary entry distinguishes tickets by kind beyond whether a ticket has child tickets and whether it needs the user in the loop."

Holds in the skills, the scripts and `CONTEXT.md`. I grepped for feature/spec/standalone/decision-ticket/legwork/`type:`/Testing Decisions across `mx/`, `claude/` and the glossary. What remains:

- The README figures' alt text (`mx/README.md:7`, `:15`, `:54`: "a standalone ticket", "a spec sliced into tickets", "One feature on the board"). This is the "README figures" point the ticket's Comments leave open.
- Test prose in `mx/skills/tracker/test_board.py`: "the build ticket" at `:1629`, `:1657`, `:1838`, and "the spec's Testing Decisions" at `:768`, `:972`, `:2288`.
- The corpus, which is historical by design (`corpus/README.md`).

**P8**, "Nothing the workflow produces is committed to the code repo: its history holds code alone."

The scripts hold it:

- `dispatch` commits only in `$agent_top` (`:113`, `:289`, `:627`, `:647`).
- `review` writes under the ignored `agent/reviews/`.
- The worker is told `git -C agent`.
- Show, prototype and research route to the agent repo.

It fails in two places:

- Loose work (A2): the retire sentence puts agent-repo files on a code branch.
- This diff itself commits about fifty files under `agent/` (show pages, demos, ticket files) to the code repo's history. The ticket settles that by the close-out split ("This repo's `agent/` is split out with its history by `git filter-repo --subdirectory-filter agent` once this ticket's work is on master"), so it is no finding. The split still has to happen before P8 is true of this repo.
