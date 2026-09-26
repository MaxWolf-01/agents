---
name: handoff
description: "Compact the current conversation into a handoff file a fresh session starts from. Use when a context checkpoint says to write one, when the session is full or ending, or to fork a side-quest out of it."
argument-hint: "What will the next session be used for?"
---

A handoff is the conversation compacted into one file a fresh session starts from, written by the session that holds the context and read by the user before anything replaces it. That is its whole advantage over a summary a harness writes on its own: it can be proofread and corrected first.

## Purpose

A handoff requires a **purpose**: what the next session should do. The purpose sets the scope:

- **Continuation**: this session is full or ending, and the next one inherits the thread. Walk the conversation start to end before writing; early decisions and corrections carry the same weight as the last few turns. A context checkpoint asking for a handoff means this purpose, and the file is written at once: the user's read before the next session starts is the check.
- **Fork**: a side-quest surfaced (a bug, a refactor, an idea out of scope here). Extract only the slice that pertains to it, and note in this session that it is now out of scope. Tell the user in a few lines the purpose, the scope and what only this conversation knows that you would carry over, before writing: their reply is the mandate, and a purpose you inferred is a proposal until they confirm it.

## What it carries

Complete on these six even at the cost of length; everything else short:

1. **Asked, decided, ruled out.** Every request, decision, rejection, preference and boundary, stated exactly, with the user's reason where they gave one. The user's words stay close to verbatim; a decision you proposed and they never confirmed is marked as your proposal.
2. **Options set aside.** Every approach raised, tried or dropped, and why.
3. **Difficulties.** What went wrong and how it was handled or left.
4. **Where things stand.** What is done, landed, merged, pushed; what sits on which branch or worktree, unmerged.
5. **What is open.** Questions waiting on the user, work promised, jobs still running, the next step.
6. **What is hard to reconstruct.** Names, numbers, paths, commands, exact wording, measurements: kept exactly.

Your own explanations and reasoning condense to what they concluded. What already lives in an artefact (a ticket, an ADR, research, a commit, a diff) is a pointer to that artefact by path, never a copy of what it says.

Two sections close the file:

- **Suggested skills**: the skills the next session should invoke, and when.
- **Sources**: the tickets, ADRs, research, key code files and external docs the next session needs, each with a one-line why, the ones that shaped your thinking marked MUST READ. When in doubt, MUST READ: you have context the next session does not.

## The file

A handoff is `agent/handoffs/YYYY-MM-DD-<descriptive-slug>.md` in the agent repo of the project the work is in, committed in its main checkout, as a ticket file is. Its frontmatter carries this session's id:

```markdown
---
session: <the value of $CLAUDE_CODE_SESSION_ID>
purpose: continuation | fork
---
```

The file is the deliverable, so the chat gets its absolute path and the pickup line, not a summary of it:

```
Continue from <absolute path>. Read it in full first, then git rm it in the agent repo and commit: a handoff is retired once a session has picked it up.
```

For a continuation, the user runs `/clear` once they have read the file and gives the fresh session that line.
