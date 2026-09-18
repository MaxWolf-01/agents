---
status: open
type: grilling
---

# A ticket records the sessions that touched it, resumable from the board

## Question

Ruled worth grilling by the user in chat, 2026-09-18. When a ticket comes back for a ruling, the session that built or grilled it is somewhere among a dozen tmux panes, and the user keeps panes open only to find it again. A ticket should carry every session that touched it, and the board should hand the user the command that resumes one, so panes can be closed freely.

What the user asked for, to decide against:

- Each entry is at least the repository the session ran in (an absolute path, since a ticket is sometimes touched from more than one repository) and the session id, which the agent has access to; the board's copy button yields `cd <repo> && claude --resume <id>`.
- Entries carry when the session started and when it last touched the ticket, kept current, so several sessions on one ticket read in order.
- A short title per session, so an id means something: the session-index script that titles sessions with a small model reading both sides of the conversation is a candidate source, queried at render time or written into the entry.
- The recording is mechanised, not left to a worker's prose: dispatch knows a worker's session id at spawn and resume, an orchestrator knows its own, a loose session its own.

To decide, options sketched by the agent, frame unconfirmed: the frontmatter shape (a `sessions:` list of `{repo, id, started, last, title}` entries, or one line per session under a fixed heading); who writes each field and when (spawn and resume for workers, claim and review for the orchestrator, the round's commit for a grilling session); where the title comes from and whether the board caches it; how `dispatch` learns a worker's session id from the runner (the status line carries `session=` already); and what the board shows when a session's repository no longer exists on this machine.
