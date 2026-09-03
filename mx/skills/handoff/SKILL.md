---
name: handoff
description: "Compact the current conversation into a handoff document for another agent to pick up: continue the work, or fork a side-quest out of it."
argument-hint: "What will the next session be used for?"
---

Write a handoff document so a fresh agent can continue the work. A handoff requires a **purpose**: what the next session should do. The purpose sets the scope:

- **Continuation** (this session is full or ending): the next agent inherits the thread. Walk the conversation start to end before writing; early decisions and corrections carry the same weight as the last few turns.
- **Fork** (a side-quest surfaced: a bug, a refactor, an idea out of scope here): extract only the slice that pertains to the forked task, and note in this session that it's now out of scope; that sharpens the parent too.
- **Return** (this session was a detour, a prototype or an investigation, reporting back to its parent): capture only what the produced artifacts don't already show: non-obvious learnings, dead ends, decisions.

Load `/mx:writing-for-agents` before drafting the document, unless it's already loaded in this session: the handoff is read cold by an agent, and it's the standard for it.

Before writing the file, put a short brief to the user: the purpose, the scope, and all the things only this conversation knows that you'd carry over. Their reply is the mandate: a purpose you inferred yourself is a proposal until they've confirmed it. The same discipline holds inside the document: the user's decisions are binding input; your proposals stay labeled as proposals.

Include a "suggested skills" section in the document, which suggests skills that the agent should invoke.

Do not duplicate content already captured in other artifacts (specs, tickets, ADRs, research, commits, diffs). Reference them by path or URL instead.

End with a **Sources** section: the spec/tickets, ADRs, research artefacts, key code files, and external docs the next agent needs, each with a one-line why. Bias toward marking them MUST READ: you have context that shaped your thinking; the next agent doesn't. When in doubt, MUST READ.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

The file is the deliverable; don't also summarize it in chat. Write it to `agent/handoffs/YYYY-MM-DD-<descriptive-keyword-slug>.md`, then give the user the pickup prompt:

```
Continue from agent/handoffs/YYYY-MM-DD-<slug>.md. Read it in full first.
```
