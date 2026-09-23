---
status: done
priority: 2
size: XS
diff: [74212f1fe06eac36917516d3b7f85a2af2396a1b..b905885989b6be41ca2b14fa037572eb64294560]
---

# A moved ticket keeps its sessions

## Brief

A ticket file that moves keeps the sessions that worked on it under its old path. Moves happen: a standalone ticket grilled into a feature, a feature's ticket leaving it (board-orients 15 became `debrief-ticket` on 2026-09-23), an opened ticket moved out when its feature retires. Today `session_log` in `mx/skills/tracker/board.py` keys each session by the path a commit changed, so a moved ticket lists only the sessions after the move. Asked for by the user on 05's D3: git records the rename, so following it costs nothing.

## Questions

- [D1] **Which moves the board follows is git's guess at how alike two files are, at its default half.** `-M` is what the ticket asks for, and it pairs a delete with an add only where over half the file survives. So a commit that both moves a ticket and rewrites more than half of it carries nothing, silently, and a commit that retires one short ticket while filing another can read as one move and hand the new ticket the retired one's sessions. Lowering the threshold buys the first and costs more of the second; ticket files are short and share their frontmatter and headings, so the pairing has little to go on. The default stands until you say otherwise (A4).
  - Ruled 2026-09-23: git's default threshold, as built.

## What to build

`session_log`'s one pass over the repo reads renames as well as names (`git log --all --reverse --name-status -M` reports a move as `R<score>\t<old>\t<new>`, checked on `debrief-ticket`), and the sessions recorded under an old path carry over to the new one, through a chain of moves too. No git call per ticket.

## Acceptance criteria

- [x] A ticket moved once, and one moved twice, lists the sessions that committed on it under every earlier path, at the loader seam, in a fixture repo that commits, moves and commits again.
- [x] The session list still comes from one git call over the repo.
- [x] Demo: `debrief-ticket` opened on the board lists the board-orients sessions that filed and ruled on 15.

## Comments

A ticket that moved keeps every session that worked on it under an earlier path, through a chain of moves, out of the same one pass over the repo. On branch `ticket/board-orients/18-sessions-follow-moves`, not merged. My calls for you are this ticket's `## Questions`.

**Demo**

    /home/agent/repos/dispatch/agents-board-orients-18-sessions-follow-moves/agent/show/board-orients/18-sessions-follow-moves/demo

walks this repo's own `debrief-ticket`, which left board-orients on 2026-09-23: git's record of the move, what the board's loader now reads for the ticket, and the board rendered from a clone of this branch. Run here:

    This ticket moved on 2026-09-23: it was filed inside the feature board-orients as its slice 15, and
    left the feature to stand on its own. What git wrote down for that commit, which is the whole of
    what the board has to go on:

        2026-09-23 board-orients: the user's rulings on 13's questions, and 15 leaves the feature
        
        R090	agent/tickets/board-orients/15-debrief-ticket.md	agent/tickets/debrief-ticket.md

    The old path on the left, the new one on the right. Until this slice the board keyed a session by
    the path its commit changed, so the ticket on the right kept none of the sessions that worked on it
    under the path on the left, and read as work nobody had touched. Now the move carries them over,
    and this is what the board's loader reads for agent/tickets/debrief-ticket.md:

        70c7b682-6f05-4244-a254-42af2dbe28cb  2026-09-23  (no transcript here)
        cc5b897d-a2a6-4c88-837a-706a2cc34270  2026-09-23  (no transcript here)

    The first filed the ticket and the second moved it. The board lists the ones this machine holds a
    transcript of, with the title the transcript gives them, because those are the ones it can hand you
    a command that resumes: a session that ran on another host is left out.
    /home/agent/repos/dispatch/agents-board-orients-18-sessions-follow-moves/agent/show/board-orients/18-sessions-follow-moves/out/board.html

    Open the page above and find "The debrief is a ticket". It sits in blocked while its blocker,
    retro-semi-automated, is open, and in the frontier once that is ruled away. Click it.
    It has no *sessions on this machine* block. Both sessions above ran on another machine, so there is
    nothing here to resume, and the board lists nothing rather than a command that would fail. On the
    machine they ran on, the block is there with both.

    figure.html beside this script is that block before and after, side by side, on a demo tracker whose
    sessions every machine can name.

The board's row shows that block only on the machine those two sessions ran on, which is yours, not this worker host: the spec's Property leaves off a session with no transcript here, and there is no honest way to show one. So the walkthrough ends at the loader's own reading on this host, and the figure carries the rendered block:

    /home/agent/repos/dispatch/agents-board-orients-18-sessions-follow-moves/agent/show/board-orients/18-sessions-follow-moves/figure.html

is the sessions block before and after, side by side, on a demo tracker whose build in review leaves the feature it was grilled into: the before panel lists the session that moved it and nothing else, the after panel lists the two that filed and claimed it under the old path as well, each with a numbered note. Both panels are the board's own markup under the board's own stylesheet, so hovering a date says what the board says.

**Details, if you want them**

- [D2] Assumptions
  - A1 `mx/skills/tracker/board.py:1267`: the carry copies the old path's sessions rather than moving them off it, because a rename is one branch's fact and the walk is over every ref at once; popping emptied the session list of a ticket the main checkout still holds at the old path, which is worse than the bug this ticket fixes. The review's correctness and spec axes disagreed on this, the first asking for the copy and the second for the pop with the cost written down.
  - A2 `mx/skills/tracker/board.py:1264`: a file arriving at a path a move emptied, by being created there or moved there, starts with its own sessions alone; that is what the copy costs, and it is the case the pop used to cover.
  - A3 `mx/skills/tracker/board.py:1261`: a log line naming no file is skipped. A trailer whose value runs on to an indented line puts one there, which `--name-only` read as a filename and `--name-status` would crash the whole render on.
  - A4 `mx/skills/tracker/board.py:1255`: `-M` at git's default threshold, which is what the ticket names, so the moves it does not follow go unfollowed (D1).
  - A5 `mx/skills/tracker/board.py:1247`: a move onto a path an earlier file was deleted from still inherits that file's sessions. Treating a delete like a move away would lose the sessions of a ticket deleted on one branch and live on another, which is a configuration this tracker really has.
  - A6 `mx/skills/tracker/board.py:1233`: "oldest session first" is the order the walk inserts in, which a commit cherry-picked back over an older date can invert. It predates this slice and is not fixed here.
  - A7 `mx/skills/tracker/test_board.py:1638`: the one-call criterion is checked by counting the calls through `board.git`, a seam the spec's Testing Decisions does not name; the GitHub cost claim beside it is counted at the `gh` executable instead. The Decisions gain "the board reads the log once per render, counted at `board.git`" when this lands.
  - A8 `mx/skills/tracker/board.py:51`: the board's `--help`, the one place in the shipped tree that describes how sessions are found, gains the moved-path clause. The ticket asked for no documentation.
  - A9 `agent/show/board-orients/18-sessions-follow-moves/demo:20`: the demo renders the board from a clone of this branch, since the board renders its repo's main checkout and `debrief-ticket` exists on no main checkout until this feature merges.
  - A10 `agent/show/board-orients/18-sessions-follow-moves/figure.py:37`: the figure's before and after is the demo tracker with its build in review moved out of `csv-import`, not `debrief-ticket`, because no machine but yours can name the two sessions the real ticket carries.
- [D3] Findings, from `/mx:code-review` over `74212f1..7866a65`, four axes, reports in `agent/reviews/74212f1..7866a65/`
  - Fixed in 46be744: the old path emptied repo-wide by a rename on any ref (correctness 1, tests D1, spec c1), which is A1; a log line with no tab taking the render down (correctness 4); the figure counting four sessions and showing three (standards 1); the demo's count sentence and its "the one" where two are listed (standards 2); the demo printing a confident empty result where the ticket has moved again or the checkout is detached (standards 3); `sessions()` returning the empty string where the board's markup moved under it (standards 4); `sessions.py` inlining the path walk its siblings name (standards 8); `|| true` hiding a failed `git branch` (standards 9); "all three" with nothing to count (standards 10); the `SESSION_LOG` comment's stranded colon clause (standards 6); the decision-against in the docstring, now the invariant a refactor has to keep (standards 11); the demo sending the reader to the frontier for a blocked row (spec a1); the board's `--help` (spec a3), which is A8; the one-call check pinning every git call rather than counting the log (tests A1); three transcripts sharing one title (tests A2); a carried session with no transcript here (tests C1); a move nobody's session made (tests D3); a span the walk has to widen backwards (tests D4).
  - Fixed in fa5444f, found by mutating the two lines the carry turns on rather than by the review: a ticket moved onto a path another left had no check (tests D5), and the bookkeeping that made a path stop counting as emptied had no case at all.
  - Declined, with the reason in the assumption it stands on: the similarity threshold and the moves it drops or invents (correctness 2, tests D2) → A4 and D1; a commit on the old path the walk reaches after the move (correctness 3) → the docstring says it; the order two sessions are listed in (correctness 5) → A6; a destination path a deleted file once held (spec c2) → A5; the seam the one-call check enters at (tests B1) → A7; the span tuple spreading to a third site (standards 12) → the `Session` dataclass is where it would go, and no slice here touches it; naming `worked` twice with two meanings (standards 5) → the local is gone, so the parameter stands alone; the demo's board row on a host without the transcripts (spec a2) → said in the Demo line above.
- [D4] Friction
  - The board cannot render this repo's tracker on a worker host, which [The board renders on a worker host](../board-renders-on-worker-hosts.md) already records: the main checkout here is the bare repo the worktrees hang off. The demo has to clone the branch to render at all, which turned out to be right for another reason (A9), but I found that out by watching `board` stop.
  - A demo for a slice whose subject is this repo's own sessions cannot show its own subject on the host that builds it, because the sessions that did the work are the user's. I spent a while looking for an honest way around it before accepting that the figure is the artefact that carries the render and the demo carries the reading. A ticket whose demo depends on the user's own machine state is worth naming as such when it is cut.
  - Two review axes returned opposite recommendations on the same finding, one asking for the copy and the other for the pop, each having worked through the other's option and rejected it. Reading both was what settled it, since each had ruled out a combination the other had not tried; a review that reconciled its axes before reporting would have handed me one of the two wrong answers.
  - The review's Tests axis found five behaviours the checks could not tell from their absence, and mutating the code by hand afterwards found two more that its own fixes had left open. Both passes were cheap and neither was `make harden`, which is the orchestrator's per feature: a single-file mutation run a worker could point at its own diff would have found all seven in one go.
