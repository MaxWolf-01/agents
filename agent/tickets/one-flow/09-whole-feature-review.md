---
status: claimed
diff: [b62d85e26727d6f2fcd3c446d9faf1532e84d8d5..44729f13d2fb5f9a5b170e024bfb7b71c2fc02dc]
---

# Whole-feature review of one-flow against master

## What to build

The flow's own close-out step, not a proposal: no slice of this feature was reviewed against the whole, and that is where incoherence between slices shows. Run a full `/mx:code-review` of the `one-flow` branch against the repo's integration branch, `master`, with `agent/tickets/one-flow/spec.md` as the spec axis: the fixed point is `master`, so the range is the merge-base with `master` to the branch tip, and the reports land under `agent/reviews/<range>/`. Read the spec's Properties as the reviewed list: every one is disposed **reviewed** and each has an acceptance criterion somewhere in tickets 01 to 08. Where the slices disagree with each other (a skill that still describes what another slice retired, two homes for one rule, a pointer to a file that moved), that is the finding this pass exists for.

Dispose of every finding under the review skill's own rule: fix it on this branch as `Workflow-stage: review` commits, file it as a proposed ticket when it is too large, decline it as an anchored assumption. The plugin installed on the host predates this branch's skills; follow the branch's `code-review` skill as written.

## Acceptance criteria

- [x] Four axes ran against the merge-base with `master`, their reports are on disk under the range, and every finding has one disposition in the finding index.
- [x] `make check` and `make test` pass on the branch after the fixes.
- [x] No skill, README line or figure on the branch describes a mechanism another slice of this feature retired (the size call at the gate, `dispatch setup`, the implement skill, the standalone message, the per-batch review rule).
- [x] Demo in the closing comment: the finding index, and the commands that show the reports on disk.

## Comments

### Closing, worker on `ticket/one-flow/09-whole-feature-review`

The whole-feature review ran four axes against the tip of `master` as this branch carries it, and a second round against its own fix pass; 44 findings, every one fixed, filed or declined, in eight `Workflow-stage: review` commits. Seven of them are already merged (`f4a420d`); `dd53439`, the second round's fixes, is not.

**Demo.** From a checkout of this branch:

```
$ ls agent/reviews/*/
agent/reviews/b62d85e..44729f1/:
correctness.md

agent/reviews/e4f34a6..b62d85e/:
correctness.md  spec.md  standards.md  tests.md
```

The reports are gitignored and die with the worktree they were written in, so on your machine that listing is empty and the finding index below is what travels. What you can run anywhere:

```
$ make check
manifests parse, hooks point at executables, bin/ answers --help

$ make test
============================= 72 passed in 23.17s ==============================

$ mkdir -p /tmp/stub && printf '#!/usr/bin/env bash\nexit 0\n' > /tmp/stub/claude && chmod +x /tmp/stub/claude
$ PATH=/tmp/stub:$PATH bash agent/show/host-per-spawn/demo.sh 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -E '^   (ok|FAIL)'
   ok no copy of the scripts, no init
   ok the host holds the branch's prompt, byte for byte
   ok the re-staged runner is a new file, not the old one rewritten
   ok a cleaned-up run is forgotten, so nothing follows a ticket to a host it has left
   ok the standalone build stays off the integration branch
```

The third line is the headline fix: a re-stage used to copy over the bytes a running worker's shell was reading. Revert `copy_to` to its old one-line `cp` and that check fails, which is how I confirmed it discriminates.

The chat reviewer, end to end, one model call in and one out (about 20 s):

```
$ ./agent/prototypes/chat-review-hook/try
--- reply the user reads
Picture Quill: a TypeScript ORM that removes boilerplate in favor of clarity. ...

--- reviewer log (/tmp/chat-review-try.jsonl)
[2026-09-15T03:03:44] feedback    5194ms
  draft: What a fantastic question—it tells me you're thinking about ...
  rule 22: "What a fantastic question—..." becomes: Delete the opening; start with the description.
  [... 8 more hits ...]
[2026-09-15T03:03:49] allow  re-entry  ms
residual: none
```

`try` had no pass condition before this branch: it now exits nonzero when the hook never reached the reviewer, or when a tell the feedback quoted survives the rewrite word for word.

The figure the review re-shot, against the board it claims to show: open `mx/assets/board-feature.png`. Its header read `· workers on workbench.local` before, a label `board.py` can no longer produce.

**I need from you.**

1. `[D1]` **The chat reviewer skips print mode, and that is wider than the spec's rule.** `chat_review.py:128` returns early on `CLAUDE_CODE_SESSION_ATTENDED=0`, where the spec says it returns early "in sessions nobody reads". A `claude -p` you typed yourself is read by you. Two more things about that guard: its premise is unverified here (this host runs 2.1.243, whose binary has no such variable, which is what ticket 03's A1 recorded), and an environment variable descends into children, so an interactive session started from a print-mode one inherits the `0` and silently skips every review. Narrow the property to match the code, or narrow the guard to match the property.

2. `[D2]` **"Be specific. No generalities or platitudes" left the output style for catalogue rule 39.** Round 3 put "specific" on the list of things the generator keeps; ticket 01 moved it to the catalogue, where a reviewer applies it after the fact. Defensible (a platitude is checkable from one message) but it is a change to what you ratified, and no ticket recorded it as one.

3. `[D3]` **The release has to happen after the merge, not before.** `mx/.claude-plugin/plugin.json` is still `0.1.56` on this branch, so nothing this feature built reaches any machine, the Stop hook included. `master` already published `0.1.57`, so `make release-patch` from here would compute a version that exists. Merge first, then bump.

4. `[D4]` **A worker that finds an executable seam under a property the spec calls *reviewed* has nowhere to go.** Ticket 03's worker wrote a test file and filed it as an assumption, and the spec was amended after the fact; this pass found two more such seams (the hook's guard ladder, the tracker's queue loader) and neither got even that. Either the contract says what a worker does when this happens, or the Testing Decisions is expected to move during a build and the worker says so in its comment.

**Details, if you want them.**

5. `[D5]` **Assumptions.**

   - A1 `agent/tickets/one-flow/09-whole-feature-review.md:10`: the fixed point is `e4f34a6`, not `git merge-base master HEAD`. This clone has no `master` and no remote to fetch one from; `e4f34a6` is the tip of `master` as merged into `one-flow` at `2167e94`, and the merge-base of any `master` that descends from it with this branch is that same commit. Reverse by re-running the axes against the real ref from a checkout that has it.
   - A2 `mx/skills/dispatch/worker-prompt.md:60`: declined, the near-identical `<style>` paragraph in the worker prompt and the user `CLAUDE.md` stays in both. They are two prompts for two readers, and a worker never loads the user `CLAUDE.md` (the runner excludes it), so neither is a copy the other could stand in for. The clause that differs, the diffview notes, is the one surface a worker does not have.
   - A3 `mx/skills/writing-for-humans/CATALOGUE.md:97`: declined, rule 26 still bans "harness" and "surface", which `PRINCIPLES.md` and four skills use as terms of art. The catalogue's header already rules that a documented repo standard wins, the rule predates this feature, and the alternative is trimming a word list against one repo's vocabulary.
   - A4 `.gitignore:6`: declined, `__pycache__/` stays in the repo's own ignore file though `project-setup` says the global one covers caches. A worker host clones the repo and inherits no global ignore, which is the same reason `agent/reviews` is there.
   - A5 `mx/README.md:124`: the utilities line named `overview`, which is not a skill in this plugin, and missed `expert` and `upstream-issue`. Fixed though the line predates this feature's range: a pointer to a skill that does not exist is the shape this pass exists to catch.
   - A6 `agent/tickets/one-flow/spec.md:33`: the spec is yours, and I edited two lines of it. Both are the sweep the tracker asks for after a decision lands (rewrite the sections it touches): the dial table still carried the r2 host rule that the spec's own host-per-spawn decision supersedes, and the Testing Decisions counted one executable seam where the build turned up two. Marked inline with what they were.
   - A7 `agent/tickets/one-flow/05-standalone-dispatch.md:9`: I tombstoned another slice's finished ticket and amended four assumption bullets in three others. The same sweep rule, applied to closed records: each names the commit that settled it, and no id changed, so the review pages keep their anchors.
   - A8 `mx/skills/dispatch/dispatch:136`: `copy_to`'s remote arm is unexercised. This host has one machine, so the `scp` and `ssh mv` paths were checked by reading against the argv-over-ssh convention the script already relies on, not by running. `agent/tickets/dispatch-scripts-under-test.md` proposes `ssh localhost` as the cheap way to exercise them.

6. `[D6]` **Finding index, round one.** Four axes against `e4f34a6`; reports under `agent/reviews/e4f34a6..b62d85e/`. Fixes in `9ff8415`, `b896856`, `07a001f`, `fc8b6ea`, `038afb0`, `9f4f02e`, `44729f1`.

   - Correctness 1, a re-stage overwrote a running worker's runner and prompt in place → fixed, `9ff8415`.
   - Correctness 2, the print-mode skip disables `try`, the only end-to-end driver → fixed, `9ff8415`.
   - Correctness 3, code-review read a ticket as a spec, so a standalone worker spawned four axes where its contract says light → fixed, `b896856`; you refined it in `4cec0d3` to light by default, full by the reviewer's call.
   - Correctness 4, the README's board figure still showed the retired per-feature host → fixed, `07a001f`.
   - Correctness 5, the state-line rule was cut with no home → fixed, `b896856` → **reversed by you**, `4cec0d3`.
   - Correctness 6, four anchored assumptions contradicted the code they anchor to → fixed, `fc8b6ea`.
   - Correctness 7, rejecting a standalone proposal left its branch in the integration repo → fixed, `b896856`.
   - Standards 1, the tick branched on a `proposed` status `claim` had already overwritten → fixed, `b896856`; your `0305c78` then made the whole build wait on its ticket branch, which settles it further.
   - Standards 2, the lead figure contradicted five artefacts on where your rulings arrive → fixed, `07a001f`; the figure was rewritten again in `b56b39a`.
   - Standards 3, `agent/show/one-flow/render.py` is a byte-identical copy → filed into `render-check.md`, `fc8b6ea`.
   - Standards 4, the show report pointed at files in another checkout → fixed, `fc8b6ea`.
   - Standards 5, two near-identical style paragraphs → declined, A2.
   - Standards 6, catalogue rule 35 named this repo's own defined terms as coined labels → fixed, `b896856`; you then retired the term itself, `0305c78`.
   - Standards 7, rule 26 bans two words the repo uses as terms of art → declined, A3.
   - Standards 8, the spec's dial table carried the superseded host rule → fixed, `fc8b6ea`.
   - Standards 9, ticket 02's re-drive snippet sets git config two slices retired → fixed, `fc8b6ea`.
   - Standards 10, the tracker's standalone retire step named a commit the flow no longer produces → fixed, `b896856`.
   - Standards 11, the nested-reviewer skip returned with no log line → fixed, `9ff8415`.
   - Standards 12, `stage` leaked its setup temp dir → fixed, `9ff8415`, completed in round two.
   - Standards 13, review-pr told its caller to edit a brief code-review says goes in verbatim → fixed, `b896856`.
   - Standards 14, the dispatch description promised the feature shape for both branches → fixed, `b896856`.
   - Standards 15, `__pycache__/` in the repo ignore file → declined, A4.
   - Spec (a) A1, seven of fifteen properties reached no slice's criteria → filed, `every-property-gets-a-criterion.md`.
   - Spec (a) A2 and A3, the state line and answer-first → see Correctness 5.
   - Spec (a) A4, the platitudes rule left the keep list → `[D2]`.
   - Spec (a) A5, the board leaves a breakdown's slices out of its counts and lanes → left: it is queue entry 3, waiting on your ruling.
   - Spec (a) A6, loose work's stated review-page gate has no tool in the plugin → filed, `loose-work-review-page.md`.
   - Spec (a) A7, the plugin version is unbumped → `[D3]`.
   - Spec (c) C1, the print-mode skip narrows the property → part fixed (`try`), the rest `[D1]`.
   - Spec (c) C2, `try` disables itself → fixed, `9ff8415`.
   - Spec (c) C3, ticket 05 reads as a live record of what ticket 08 deleted → fixed, `fc8b6ea`.
   - Spec (c) C4, `[Dn]` tags are ticket-scoped for a worker and session-scoped in chat, and the relay collided them → fixed, `b896856`, sharpened in round two.
   - Spec (c) C5, the show report describes the figure with the retired host → fixed, `fc8b6ea`.
   - Spec (c) C6, the figure counted four stations against chips marking two → fixed, `07a001f`.
   - Spec (c) C7, a session building its own slice had no way to load the worker contract → fixed, `b896856`.
   - Spec (b), four unasked changes (the reviewer's model as an env var, a hostless `probe`, the staging stamp, two ignore lines) → left, each already anchored in its own slice's comment.
   - Tests (a) A1, both proposals in the board fixture were blocked, the one dimension the tests are about → fixed, `038afb0`.
   - Tests (a) A2, the demo's one assertion sat inside an `&&` list errexit does not reach → fixed, `9ff8415`.
   - Tests (a) A3, the hits-parser test built its input from its own expectation → fixed, `44729f1`.
   - Tests (b) B2, the spec named one executable seam where the build turned up two → fixed, `fc8b6ea`.
   - Tests (b) B3, `ANSWER.md` records the prototype's measurements, not the shipped hook's → fixed, `9ff8415`.
   - Tests (c) C1, `main()`'s guard ladder is the whole once-per-turn property and no test imported it → fixed, `038afb0`.
   - Tests (c) C2, `notes_of` silently dropped two of ticket 01's four calls → fixed, `9ff8415`.
   - Tests (c) C3, no rung between the properties directory and *reviewed* → `[D4]`.
   - Tests (d) D1 and D2, `try` is switched off on the next harness release and had no pass condition → fixed, `9ff8415`.
   - Tests (d) D3, nothing parsed `mx/hooks/hooks.json`, the whole of the hook's registration → fixed, `038afb0`.
   - Tests (d) D4 and D5, the queue could vanish from the page and the stamp with the suite green → fixed, `038afb0`.
   - Tests (d) D6 and D7, 424 changed lines of shell with no test, and a demo that checks the runner against a copy of itself → filed, `dispatch-scripts-under-test.md`.

7. `[D7]` **Finding index, round two.** Correctness against `b62d85e`, report at `agent/reviews/b62d85e..44729f1/correctness.md`; all nine fixed in `dd53439`. The other three axes never ran: the session hit its limit mid-review, and the report that existed was already on disk, which is the only reason this round survived at all.

   - 1, relaying renumbers a worker's `[Dn]` tags while the review page's notes cite the ticket's own, so the two surfaces you read together named one call differently.
   - 2, `.staging` was one fixed name in a scratch dir two sessions share, so a second dispatcher could publish its bytes under the first's stamp and leave a host running one version's runner under another's digest.
   - 3, the `RETURN` trap freed the setup temp dir only on the paths that return, and `die` exits; the paths that die are the ones an orchestrator retries.
   - 4, on the already-staged path `copy_to`'s status was dropped, so a corrected `--setup-cmd` that failed to land built every worktree with the old one.
   - 5, the new `mkdir` and renames went unechoed, so a stage that failed at the rename left a transcript that could not say which files had moved.
   - 6, the new `notes_of` failure named no offending bullet, on a ticket that can carry eleven.
   - 7, the demo asserted `main` is an ancestor of the ticket tip, which holds when the build lands on the integration branch: the defect the claim is worded to catch.
   - 8, the README's skill inventory missed `upstream-issue`.
   - 9, ticket 06's closing comment still told a reader to run `dispatch setup`.

8. `[D8]` **Three proposals filed**, each on the build frontier and each wanting your ruling on what it builds: `dispatch-scripts-under-test.md` (the dispatch scripts have no test and their one driver checks the runner against a copy of itself), `loose-work-review-page.md` (the loose gate has no tool inside the plugin), `every-property-gets-a-criterion.md` (to-tickets checks that every spec property lands in some slice).

9. `[D9]` **Friction.**

   - The ticket says to pin `git merge-base master HEAD`, and a worker host's clone has neither `master` nor a remote to fetch it from: only the branches dispatch pushed are there. I derived the same commit from the merge that brought master in, which worked because this feature branch has exactly one such merge. Pushing the integration branch alongside the feature branch, or naming the sha in the ticket, would have made it a lookup instead of an inference.
   - This host has no `diffview`, so `dispatch review` cannot render a page here and `build.py`'s review-page screenshot could not be re-shot with the board ones. A worker cannot see the artefact its own contract is built around.
   - The reports are gitignored, so the four that carry the reasoning behind 44 dispositions die with this worktree, and the index above is the only durable trace. That is the design, and it is worth knowing that the index is load-bearing: `cleanup` is what destroys the evidence.
   - A four-agent wave took this host's tmux server down before this ticket started, so the ticket told me to spawn two at a time. Two waves of two, nothing died, and the axes stayed independent. Whatever the four-agent failure was, it did not recur at two.
   - The session limit killed the second round mid-flight, after one of four axes. Nothing was lost, because the reviewer writes to a file rather than returning a report, and the resumed session read it off disk.
