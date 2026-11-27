---
name: handoff
description: "Compact the current conversation into a handoff file a fresh session starts from. Use when a context checkpoint says to write one, when the session is full or ending, or to fork a side-quest out of it."
argument-hint: "What will the next session be used for?"
---

A handoff is the conversation compacted into one file a fresh session starts from, written by the session that holds the context and read by the user before anything replaces it.

## Purpose

A handoff requires a **purpose**: what the next session should do. The purpose sets the scope:

- **Continuation**: this session is full or ending, and the next one inherits the thread. Walk the conversation start to end before writing; early decisions and corrections weigh as much as the last few turns. A context checkpoint, a message saying where the context stands sent once per mark, means this purpose; once a mark says to write, write the file without asking first, since the user's read before the next session starts is the check. Each mark asks for something else:
  - the first: write the handoff at the next phase boundary and tell the user it is there.
  - the second: write it now and tell the user to `/clear`.
- **Fork**: a side-quest surfaced (a bug, a refactor, an idea out of scope here). Carry only the slice that pertains to it, and note in this session that it is now out of scope. Before writing, tell the user in a few lines the purpose, the scope and what only this conversation knows that you would carry over: their reply is the mandate, and a purpose you inferred is a proposal until they confirm it.

## What it carries

Complete on these seven even at the cost of length; everything else short:

1. **Asked, decided, ruled out.** Every request, decision, rejection, preference and boundary, stated exactly, with the user's reason where they gave one. The user's words stay close to verbatim; a decision you proposed and they never confirmed is marked as your proposal.
2. **Options set aside.** Every approach raised, tried or dropped, and why.
3. **Difficulties.** What went wrong and how it was handled or left.
4. **Where things stand.** What is done, landed, merged, pushed; what sits on which branch or worktree, unmerged.
5. **What is open.** Questions waiting on the user, work promised, jobs still running, the next step.
6. **What is hard to reconstruct.** Names, numbers, paths, commands, exact wording, measurements: kept exactly.
7. **Peers.** Every session this one exchanged messages with: its name, its role, and what it expects from this session; and this session's own name. `/clear` keeps that name and a new process gets a new one, so a next session answering to a different name sends each peer that name as its first act after reading the file.

Condense your own explanations and reasoning to what they concluded. What already lives in an artefact (a ticket, an ADR, research, a commit, a diff) gets a pointer to it by path, never a copy of what it says.

Two sections close the file:

- **Suggested skills**: the skills the next session should invoke, and when.
- **Sources**: the tickets, ADRs, research, key code files and external docs the next session needs, each with a one-line why, the ones that shaped your thinking marked MUST READ. When in doubt, MUST READ: you have context the next session does not.

## The file

A handoff file, with a descriptive slug, goes in the agent repo of the project the work is in, committed in its main checkout as a ticket file is. A dispatched worker's goes to `agent/show/<slug>/handoff.md` on its agent branch instead, beside its report, so the orchestrator's fetch brings it home with the branch; its contract says when it writes one, and nobody `/clear`s it, so the rest of this section is for a session. The frontmatter carries this session's id:

```markdown
---
session: <the value of $CLAUDE_CODE_SESSION_ID>
purpose: continuation | fork
---
```

For a continuation from the current live session, the user only needs to `/clear`, then send any message: in a project whose agent repo holds the handoff, the plugin's `SessionStart` hook puts the line below in the fresh session's context, and the session acts on it at its first turn, which only the user's message starts. Give the user that line verbatim, with this skill's base directory and the handoff's path filled in, so they can also continue from a fresh `claude` started any other way (N such lines if you split the handoff into N successors):
```
Continue from <absolute path>: first run `<base directory>/pickup.py <absolute path>`, which prints the handoff in full, retires it and links the session pages.
```
