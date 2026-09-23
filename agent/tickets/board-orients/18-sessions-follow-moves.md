---
status: claimed
priority: 2
size: XS
---

# A moved ticket keeps its sessions

## Brief

A ticket file that moves keeps the sessions that worked on it under its old path. Moves happen: a standalone ticket grilled into a feature, a feature's ticket leaving it (board-orients 15 became `debrief-ticket` on 2026-09-23), an opened ticket moved out when its feature retires. Today `session_log` in `mx/skills/tracker/board.py` keys each session by the path a commit changed, so a moved ticket lists only the sessions after the move. Asked for by the user on 05's D3: git records the rename, so following it costs nothing.

## What to build

`session_log`'s one pass over the repo reads renames as well as names (`git log --all --reverse --name-status -M` reports a move as `R<score>\t<old>\t<new>`, checked on `debrief-ticket`), and the sessions recorded under an old path carry over to the new one, through a chain of moves too. No git call per ticket.

## Acceptance criteria

- [ ] A ticket moved once, and one moved twice, lists the sessions that committed on it under every earlier path, at the loader seam, in a fixture repo that commits, moves and commits again.
- [ ] The session list still comes from one git call over the repo.
- [ ] Demo: `debrief-ticket` opened on the board lists the board-orients sessions that filed and ruled on 15.
