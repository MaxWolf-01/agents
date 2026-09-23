---
status: open
type: grilling
blocked-by: [board-orients/05]
priority: 4
size: M
---

# Workers in flight, from the board and the shell

## Brief

A ticket on the board lists only the sessions this machine can resume, so a worker running on agent@pc shows nowhere, and looking in on it means knowing its host and its tmux session name. The board could list the workers in flight, each with a button that copies the command attaching to it. The unmerged `dispatch-ps` branch built the same view for the terminal. One design should cover both, with shared code.

Filed on the user's idea on 2026-09-23, from board-orients 05's D1 (a landed build lists the sessions that filed and claimed it, never the worker that wrote it).

## What exists

- **Branch `dispatch-ps`**, five commits from 2026-09-09 and 2026-09-10, never merged and with no ticket. It adds `dispatch ps`, which asks every worker host in the repo's git config for every feature's workers (ticket, state, age, idle time, whether the pane is up, the worklog's last line). It adds `dispatch attach <handle>`, a read-only attach, since a keystroke in a live worker's pane lands in its prompt. And it adds `dispatch peek`. It includes `dispatch-ps`, a host-side script piped over ssh rather than installed, and 420 lines of tests. `master` has moved a long way since: `worker-hosts`, the per-spawn host, and the runs recorded per ticket.
- **board-orients 05** lists a ticket's sessions from `Session:` commit trailers, and shows only those with a transcript on this machine.
- `dispatch ctl probe` answers the same question for one feature, from its worktree.

## Question

1. **One listing, two faces.** What produces the list of workers in flight, once, so that the board and a terminal command read the same thing? A shared script whose output both read, the board calling `dispatch ps`, or something else.
2. **What the board shows.** A group of its own, a mark on the ticket's row, or a line in the opened ticket beside its sessions. And what the copy button copies: the ssh-and-attach command, read-only, as `dispatch attach` does.
3. **The stale branch.** Rebase and finish it, take its host-side script and tests into a fresh build, or drop it. Its read-only attach and its handle-by-ticket are the parts worth keeping or rejecting on purpose.
4. **A worker's session after it lands.** Whether the worker's transcript comes back with its branch, so a landed ticket can list the session that built it and resume it on this machine. That is the other half of 05's D1.

## Acceptance criteria

- [ ] The decision is recorded, with a spec or build tickets for what gets built. Options outside the lists above count.
- [ ] `dispatch-ps` is merged into that plan, or deleted with the reason in the commit message.
