---
status: claimed
---

# A `review` status: a build waiting for the user's ruling has its own state and its own group on the board

Ruled by the user on 2026-09-16 while working the Helferline tracker, where five builds sat in the board's folded "done" group with nobody having ruled on them: since 0.1.58 a build waits on its ticket branch for the ruling, and the status set had no word for that wait, so `claimed` and `done` each covered two things.

## What to build

- `review` joins the status set (`/mx:tracker`, MARKDOWN.md): the worker's last act sets it instead of `done`; the orchestrator sets it on the feature branch when it renders the review page. `done` keeps one meaning: the user accepted and the branch merged. `review` unblocks nothing, as `claimed` does not.
- The board groups `review` tickets under **needs my review**, beside the needs-human queue; the queue then carries only what the user must do beyond reading the review page.
- A `gh` frontmatter field, a list of `owner/repo#number` references, holds the pull requests and issues a ticket produced or tracks, however many repositories they span; the board renders each as a link on the ticket's row. Resolving each reference's live state (open, merged, changes requested) is a later ticket.
- The four outcomes of a ruling read against the new state: accept writes `done`, amend takes the ticket back to `claimed` while the worker revises, redo resets it to `open`, reject deletes it.
- The dispatch scripts write the flips they own (`dispatch claim`, `dispatch review`, the runner's retry check), and the dispatch and tracker skills describe the flow in the new terms.

## Acceptance criteria

- [x] The board renders a `review` ticket in a **needs my review** group placed right after the queue, in its own colour in rows and graph, and a ticket blocked on it stays blocked until it is `done`.
- [x] A ticket with `gh: [owner/repo#1, other/repo#2]` shows both as links to GitHub on its row.
- [x] `dispatch claim` takes a `review` ticket back to `claimed`; `dispatch review` writes `review` on an unmerged branch and `done` with the range on a merged one.
- [x] The worker contract, the runner and the dispatch skill name `review` as the worker's last act, and no skill still describes `done` as the worker's flip.
- [x] `make test` and `make check` pass.
- [x] Demo in the closing comment: a board rendered with a `review` ticket and a `gh` list, and the two `dispatch review` flips in a throwaway repo.

## Comments

The status, the board group, the `gh` links and the script flips are on `ticket/master/review-status`, nothing merged; two proposed tickets ride with it.

**Demo**, on this machine:

- `bash /var/tmp/rs-board.sh`, then open `/var/tmp/rs-board.html`: a demo tracker with every state. "needs my review" sits under "needs me" with two pink rows, each carrying its `gh` pills after the title; the blocker chip on `05-export` is pink because it waits on a build in review; `d` on a row opens its review page and never a `gh` link.
- `bash /var/tmp/rs-smoke.sh`: the flips in a throwaway repo. The transcript ends in a first-parent log reading `claim thing`, `thing for review`, `claim thing`, `thing for review`, `thing landed`, and the ticket's frontmatter shows `status: done` with its `diff:` range; a further `dispatch review` adds no commit, and `dispatch claim` on the done ticket is refused.
- `bash /var/tmp/rs-notes.sh`: `[1,2]` twice, the page's notes carrying the assumption the worker wrote only on its branch, before and after the merge.
- `bash agent/show/host-per-spawn/demo.sh` (needs tmux, about a minute): the stub worker flips `review`, the runner's status line reads `status=review`, the run exits, the standalone build stays off the integration branch.

**I need from you**

- [D1] Release. After the merge, `make release-patch` and push: worker hosts and other machines run the plugin from the marketplace, and a board on the old version refuses a `review` ticket. This checkout's `board` and `dispatch` read the master copy, so here the merge alone is enough.
- [D2] Migration. Builds waiting for a ruling that still say `claimed`: in this repo, `figures-and-demos` 01 and 04 (its queue holds both rulings); in the Helferline workspace, `nps` 02, 04, 08 and 10. From each feature's worktree, on the new plugin, `dispatch review <ticket>` flips it and re-renders; the tickets that are yours to touch there are not this branch's.
- [D3] A research ticket's answer lands `review`, not `done` (A7): my reading of "done means you ratified it", since nobody has read the answer; the human-in-the-loop types stay `done`. The cost is one more flip, a line in chat written as `done` by the session that relays it.
- [D4] A resume takes a `review` ticket back to `claimed` by itself, on both copies (A6), rather than an explicit `dispatch claim` before every resume. Implicit, so the orchestrator cannot forget it; the claim commit shows in both logs.

**Details, if you want them**

- [D5] Assumptions, one per call:
  - A1 `mx/skills/tracker/board.py:90`: the needs-my-review group sits right after the queue and before the frontier, unfolded: both are the user's stations, the frontier is the agents'.
  - A2 `mx/skills/tracker/board.py:740`: a feature with a ticket in review lights its chip's dot with an empty queue too, since the dot means "needs you".
  - A3 `mx/skills/tracker/board.py:686`: a `gh` pill links the issues URL for pull requests and issues alike; GitHub redirects a pull request's number to its pull page. The state on the pill is the gh-live-state ticket.
  - A4 `mx/skills/tracker/board.py:808`: review is pink, beside the queue's red as the second group that is yours; the `gh` pill is dashed where the review-page pill is solid.
  - A5 `mx/skills/dispatch/dispatch:446`: `dispatch review` writes the status itself, following the branch: `review` while unmerged, `done` with the range once merged, one commit named `<id> landed`; the orchestrator types no flip.
  - A6 `mx/skills/dispatch/dispatch:361`: a resume claims a review ticket again here, and `dispatch-ctl` does the same in the worker's worktree (`dispatch-ctl:314`), so the runner's retry and the orchestrator's read can trust the flip of the new round.
  - A7 `mx/skills/tracker/MARKDOWN.md:33`: a research ticket's answer waits in `review`; the accept is written as `done` by the session that relays it, there being no branch to merge.
  - A8 `CONTEXT.md:71`: the Ruling entry names the four outcomes on any build (it read "a proposed ticket lands or is deleted", stale since 0.1.58), and the Orchestrator entry (line 89) writes `done` on the accept rather than judging it.
  - A9 `agent/show/host-per-spawn/demo.sh:46`: the stub worker flips `review`. The figures-and-demos feature deletes this file, so whichever merges second sees a modify/delete, resolved by deleting.
  - A10 `mx/skills/dispatch/dispatch:476`: the page's notes come from the branch tip while unmerged; this branch's copy of the ticket predates the worker's comment, so every earlier pre-merge page carried no notes. A defect from before this ticket, found while rendering this one.
- [D6] Finding index, light review of `fde7e44..57ccf07`: 1 fixed 9c01bb6 (`d` skipped the review page for a `gh` link); 2 fixed 9c01bb6 (`--help` reflow); 3 fixed 9c01bb6 (the worktree half of a resume); 4 fixed 9c01bb6 (a research answer's exit to `done`); 5 fixed 9c01bb6 (`Sequence[str]` default); 6 fixed 9c01bb6 (`review` defined once); 7 fixed 9c01bb6 (defined as finished work, not a build); 8 filed as the ticket-state-figure-review ticket, blocked on figures-and-demos 04, which is moving the figure pipeline; 9 fixed 9c01bb6 (the demo stub); 10 fixed 9c01bb6 (the classDef test pins the colour tokens); 11 fixed 9c01bb6 (a ticket linked by title).
- [D7] Friction: the dispatch scripts have no test harness, so every flip was verified by hand in throwaway repos (the three scripts under `/var/tmp`), and `dispatch-ctl resume` had to be driven against a fake scratch dir up to the point where it dies on a missing prompt. The dispatch-scripts-under-test ticket names the gap; `ticket_status`, `set_status`, `reclaim` and the notes source join its list. `uvx ty` catches a type error `make check` does not; the seven diagnostics it reports on master are older than this branch.
- [D8] Left: the README's ticket-state figure still draws `done` as the worker's flip (filed, D6 finding 8), and the `gh` pill carries no state (filed as gh-live-state, blocked on this ticket).
