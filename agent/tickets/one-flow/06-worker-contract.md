---
status: done
blocked-by: [04, 05]
---

# The worker's whole contract lives in the worker prompt; implement is deleted

## What to build

The implement skill's process moves into the worker prompt, the file the dispatch runner appends to every worker's system prompt in place of the user CLAUDE.md, and the implement skill directory is deleted. A worker then starts with its whole contract in context and no skill to load. The contract: read the ticket and its spec; read before writing (the files changed, their callers, the tests covering them); the expected failures naming the ticket in the properties directory are the oracle, made to hold then deleted; typecheck and single test files as you go, the full suite once at the end; the blast radius is the worktree and a missing system dependency is a blocker to report, never to solve; a decision made alone is an assumption, recorded with an anchored id; inherited framing is an assumption too; run the review (light without a spec, full with one) and aggregate its reports per ticket 04, with the finding index; close into the ticket's closing comment in the landing shape the spec's Decisions define, so the orchestrator relays it unchanged: one outcome line; the demo, as steps a stranger can run (the command, the path, the URL, what to look for), never performed by the worker, since on a host it can open nothing for the user; the orchestrating session performs them; "I need from you", the calls only the user can make, numbered and tagged `[Dn]`; "Details, if you want them", tagged in the same numbering: the assumptions block, the finding index, the friction hit. The orchestrator's duties (sorting friction, filing proposals, merging) and the chat duties (relaying the closing, opening the demo and the review page) are not in it.

Every pointer to the implement skill is repointed to the worker prompt or removed: the dispatch skill's worker contract line, orient, to-tickets, code-review, the README, the upstream sync skill's mapping (implement now maps onto the worker prompt).

## Acceptance criteria

- [x] The implement skill directory is gone; `rg '/mx:implement'` across the repo finds nothing.
- [x] The worker prompt carries the contract above and nothing addressed to a reader other than the worker.
- [x] The closing comment's required parts are named in the prompt: demo, action items, assumptions, finding index, friction.
- [x] Property, reviewed: the implement skill addresses only the worker (now: the worker prompt addresses only the worker).
- [x] Property, reviewed: every landing is demonstrated as the thing itself before the user is asked to read code.
- [x] Demo in the closing comment: the worker prompt as a worker receives it (the runner's assembled system prompt for a toy ticket), and this ticket's own closing comment written under the new contract.

## Comments

### Closing comment

A worker's whole contract is now the prompt the dispatch runner appends to it, `mx/skills/dispatch/worker-prompt.md`; the implement skill is deleted and every live pointer to it is repointed or gone. Three commits on `ticket/one-flow/06-worker-contract`, `03e4508`, `a72add7` and `83b4673`, unmerged.

**Demo.** Two parts: what a worker receives, and what three of them did with it.

The runner's assembled invocation for a toy ticket, driven through the real `run-worker.sh` with a stub standing in for the harness, which records its argv and stdin instead of running:

```
$ PATH=/tmp/toy/bin:$PATH bash run-worker.sh message.md agent/tickets/warm-preset.md sonnet toyrun
-p
--permission-mode
bypassPermissions
--model
sonnet
--settings
  {
    "claudeMdExcludes": ["/home/agent/.claude/CLAUDE.md"],
    "autoMemoryEnabled": false
  }
--append-system-prompt
  <9661 bytes, written to /tmp/toy/appended-system-prompt.md>
--session-id
5cc1ec02-362d-4f6c-8147-dd15ac230e91
--- stdin (the ticket message) ---
Work the ticket at agent/tickets/warm-preset.md.
You own only this ticket and this worktree; the branch it was cut from and other tickets belong to the orchestrator.
Your final act, once the implementation is committed and verified: set `status: done` in the ticket's frontmatter and commit.

$ diff <(cat mx/skills/dispatch/worker-prompt.md) <(cat /tmp/toy/appended-system-prompt.md; echo)
$                       # the appended text is the file on this branch, byte for byte
```

The contract reaches the worker as system prompt, and the message is three lines about one ticket: no skill to load, and nothing in the message that could be skipped.

Then the same runner with the real harness, three `sonnet` workers on a throwaway repo whose ticket asks for a second preset in a shell script (`/tmp/toylamp{,2,3}`, one per prompt revision). Each implemented, self-reviewed, ticked its acceptance criteria, closed in the landing shape and flipped `done`. The second one's whole comment, as the orchestrator would relay it:

```
Landed on this branch, not merged: `lamp warm` prints `255 197 143`, the no-arg usage
line reads `usage: lamp cool|warm`, and the README names both presets.

**Demo:**
    $ ./lamp warm
    255 197 143
    $ ./lamp
    usage: lamp cool|warm
    $ echo $?
    1

**I need from you:**
- [D1] The ticket asks for "the RGB of a warm white" without pinning a value. I picked
  `255 197 143` (a warm-white tone, by the same eyeballing the existing `cool` preset's
  `156 200 255` used) - worth a ruling if a specific value or measurement source matters.

**Details, if you want them:**
- [D1] Assumption: exact warm-white RGB triple is not specified anywhere ...
- Self-review (`/mx:code-review`, light mode, against merge-base `99aca22`): 0 Correctness
  findings, 0 Standards findings. No follow-up commit needed.
```

That worker held nothing but the prompt above and its three-line message. Two clauses in the prompt come from watching these runs rather than from a reviewer: the first worker ran the full four axes on a spec-less ticket (code-review's step 2 reads a ticket file as a spec source), so the mode is now keyed on `spec.md` sitting beside the ticket, which is what runs 2 and 3 then chose; the first worker also tagged nothing, so both lists name their tags. What did not converge is the assumption discipline: run 1 wrote an anchored `A1` bullet on the line it chose, run 2 wrote the same call as prose under its tag, run 3 made the same unpinned choice and recorded nothing. See `[D6]`.

To re-drive on this host: the three toy trees and their run dirs are in `/tmp`, the stub is `/tmp/toy/bin/claude`, and `bash /tmp/toylamp3-run/run-worker.sh /tmp/toylamp3-run/message.md agent/tickets/warm-preset.md sonnet run4` from a fresh copy of the tree repeats a run.

**I need from you**

1. `[D1]` Whether the landing shape keeps two homes. Verified: this worker host sets no output style, so a worker here reads the shape only in the prompt, which is why the prompt states it; on a machine holding your `~/.claude`, `run-worker.sh` excludes the user `CLAUDE.md` and not the output style, so a local worker would hold both statements of one shape. They agree as of `a72add7`, tag rule included. Keep the two agreeing copies, or exclude the output style in `run-worker.sh` so the prompt is the only home? I could not probe the local case here, see `[D6]`. A1.
2. `[D2]` Three edits outside the ticket's pointer list, each because removing a pointer left the sentence around it false: orient's step 3 lost the gate's size call, dispatch's opening lost the no-tickets build, and dispatch's landing step now relays the worker's comment instead of composing its own announcement. Ticket 07 owns the neighbouring prose (grilling's gate, the README's flow lines), so these three arrive early. A3, A4, A5.
3. `[D3]` Two declined findings, A6 and A8, and the reading of acceptance criterion 1 in A2: `rg '/mx:implement'` still matches five lines, four of them records of history and one the README figure ticket 07 regenerates.

**Details, if you want them**

4. `[D4]` **Assumptions.**

   - A1 `mx/skills/dispatch/worker-prompt.md:33`: the landing shape is written into the prompt rather than pointed at `claude/output-styles/max.md:10`, its home for chat. A worker on an isolated host can reach no file of yours, so the copy is what makes the shape reachable at all; ticket 04's A3 predicted this third site. See `[D1]`.
   - A2 `agent/tickets/one-flow/06-worker-contract.md:16`: criterion 1 is ticked as "no live document points at the deleted skill". The five remaining matches are this criterion quoting its own command, ticket 04's finding index (the accurate record of a landed round), `agent/show/one-flow/what-changes.html` (this feature's own before-and-after figure), `agent/show/dispatch-ctl-absorb/orchestrator-ticket-lifecycle.sh` (A8), and `agent/show/mx-readme-figures/main-flow.html`, whose rendered `mx/assets/main-flow.png` the README embeds and ticket 07 regenerates.
   - A3 `mx/skills/dispatch/SKILL.md:10`: the clause routing a feature without tickets to an in-session build is deleted, where the ticket named only the worker-contract line. Both of orient's arms pointed at the deleted skill, so the size call went with them, and this line is the same statement in the skill orient routes to. `mx/skills/grilling/SKILL.md:55` and `mx/README.md:80` still carry it and are 07's.
   - A4 `mx/skills/dispatch/SKILL.md:38`: the landing step becomes "relay the worker's closing comment as it stands, and open the demo it names beside the review page", per the spec's landing decision. The prompt promises the worker exactly that, and the old sentence had the orchestrator compose the announcement from the ticket's What-to-build instead.
   - A5 `mx/skills/orient/SKILL.md:30`: step 3 is no longer a branch. Its "No" arm was `/mx:implement` right here, so removing the pointer removed the size call, which is 07's subject; what is left is to-tickets, then dispatch, then a pointer to the contract.
   - A6 `mx/skills/dispatch/worker-prompt.md:19`: declined, the blocker's definition stays beside the blast radius instead of moving up to the protocol at `:8`. One always-loaded file, ten lines apart, and the preamble's subject is the two channels; the third site now says "blocker", so the word is what ties them.
   - A7 `mx/skills/dispatch/worker-prompt.md:33`: "tick the acceptance criteria your work meets" is an addition the ticket did not ask for. Nothing said who ticks them, and dispatch's pre-merge read is the party an unticked box speaks to.
   - A8 `agent/show/dispatch-ctl-absorb/orchestrator-ticket-lifecycle.sh:30`: declined, the frozen lifecycle script keeps `Load /mx:implement`. Its first line is the tombstone the tracker's Supersede rule asks for, and its ticket paths (`agent/tasks/`) are equally of that era.

5. `[D5]` **Finding index.** `/mx:code-review` since `f2e6ed4`, three axes (the diff touches no test file), reports under `agent/reviews/f2e6ed4..03e4508/`. Fixes in `a72add7` unless noted.

   - Correctness 1, Standards H4: the in-session build kept a route in three documents while its process was deleted → fixed for `dispatch/SKILL.md`, A3; grilling and the README are 07's, A5.
   - Correctness 2: a `DISPATCH_RUNNER` replacement's documented obligations never named the contract file, which used to travel in the ticket message as a skill load → fixed, in `dispatch-ctl`'s env doc.
   - Correctness 3: the scratch dir stages the runner and the prompt once per feature branch, so a stale prompt now reads exactly like no contract → punted, see `[D6]`.
   - Correctness 4: "worker prompt" named both the contract and the per-ticket message, inside one `--help` → fixed, the latter is the ticket message in `dispatch`, `run-worker.sh` and the skill.
   - Correctness 5, Standards J5: the `Addressed:` line lost the clause saying it is parsed, and its failure is the one silent case in the file → fixed.
   - Correctness 6, Spec S1, Standards H1: the `[Dn]` tags had no continuity rule, so a resumed worker's second comment restarts at D1 → fixed.
   - Correctness 7, Standards H2: the landing shape has two homes, and the premise for the copy was unverified → probed as far as this host allows, declined, A1, `[D1]`.
   - Correctness 8, Spec S2: code-review's step 5 gave the worker a second Details list, with a review page only the orchestrator can render → fixed, it names the orchestrator's message; the worker's comment stops where the spec stops it, and the relay is A4.
   - Standards H3: two answers for what the user sees at a landing → fixed, A4.
   - Standards J1: the `status: done` flip shared the contract's "committed and verified" trigger with nothing saying it comes last, where the machinery reads the flip as "finished" → fixed, the close paragraph ends on it.
   - Standards J2: the blocker concept across three sites in one file → partly fixed, the third says "blocker"; the definition stays, A6.
   - Standards J3: code-review pointed a chat-side reader at a worker's system prompt without saying what to take → fixed, it names the id rule.
   - Standards J4: the Details bullet carried a list, a parenthetical list and a nested triad in one sentence → fixed, friction is its own sentence.
   - Standards J5: the assumption rule lost the reason to obey it under pressure → fixed.
   - Standards J6: a prohibition on something the worker cannot do ("not yours to read") → fixed, "not there to read".
   - Standards nits: a relative clause hung off a possessive → fixed; `dispatch:282` wraps at 83 characters → declined, cosmetic, that file enforces no width.
   - Spec S5: "against the commit your branch cut from" named a fixed point the worker is not given, where code-review's own default resolves to an earlier ticket's review commit → fixed, the merge-base command and the branch shape, plus the per-round range.
   - Spec S6: "tick the acceptance criteria" is unasked → kept, A7.
   - Spec S7: "a reply naming a tag expands that one entry" addressed the relaying session, the clause criterion 2 points at → fixed, cut.
   - Spec S3: criterion 1's residue → A2. Spec S4: this ticket's own bookkeeping → fixed here.
   - From driving it rather than from a reviewer: the review mode is keyed on `spec.md` beside the ticket, and both lists name their tags (`a72add7`); the Details slot names the anchored form where it lists the block (`83b4673`).

6. `[D6]` **Friction.**

   - The one-flow scratch dir on this host still holds the pre-06 runner and prompt: `dispatch setup` stages them once per feature branch (ticket 05's A2 defends that isolation), and `run-worker.sh` only checks that the prompt file exists. Ticket 07's worker would therefore spawn with the old prompt and a message that no longer says "Load /mx:implement": a worker with no contract, and no reading that says so. Re-run `dispatch setup` with no arguments before the next spawn. What would fix it: `dispatch prompt` already reaches the host once per ticket and could re-copy both files, or `setup` could print the version it staged.
   - I could not verify whether a worker on your own machine loads the output style, which is what leaves `[D1]` open: probing it needs a Claude config dir holding an output style, and a scratch `CLAUDE_CONFIG_DIR` on this isolated host has no credentials ("Not logged in"). What I could check is this host: no `outputStyle` key, no `output-styles/` directory.
   - The installed plugin here is 0.1.56, so `/mx:code-review` loaded the pre-04 skill: one chat message, word caps, reports under `agent/research/`, deleted after reading. I ran the branch's version from the file instead. Every worker on this feature after 04 meets this, the three toy workers included, so what they demonstrate is the prompt and not the aggregation rule.
   - Three toy runs produced three levels of assumption discipline (an anchored bullet, prose under a tag, nothing at all) for the same unpinned choice, while the landing shape reproduced every time. Prose is doing all the work there; the enforceable rung is the landing, where `dispatch review` renders the notes and can see a ticket whose diff has judgment in it close with zero anchored bullets.
   - The worklog stayed empty in two of the three runs and held one line in the third. Ticket 05 filed the same observation; this is n=3 for it.
   - Writing a scratch file to `/tmp/closing.md` failed with "permission denied" on a stale file another host user left there in September, and the failed write plus the pre-existing file reads like a successful one to anything that does not check. Worker scratch outside the worktree wants the run id in its path.
