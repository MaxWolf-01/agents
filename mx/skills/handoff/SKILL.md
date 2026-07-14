---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up — continue the work, or fork a side-quest out of it.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document so a fresh agent can continue the work. A handoff requires a **purpose** — what the next session should do; if none is clear, ask before proceeding. The purpose sets the scope:

- **Continuation** (this session is full or ending): the next agent inherits the thread. Walk the conversation start to end before writing — early decisions and corrections carry the same weight as the last few turns.
- **Fork** (a side-quest surfaced — a bug, a refactor, an idea out of scope here): extract only the slice that pertains to the forked task, and note in this session that it's now out of scope — that sharpens the parent too.
- **Return** (this session was a detour — a prototype, an investigation — reporting back to its parent): capture only what the produced artifacts don't already show: non-obvious learnings, dead ends, decisions.

Include a "suggested skills" section in the document, which suggests skills that the agent should invoke.

Do not duplicate content already captured in other artifacts (specs, tickets, ADRs, research, commits, diffs). Reference them by path or URL instead.

End with a **Sources** section: the spec/tickets, ADRs, research artefacts, key code files, and external docs the next agent needs, each with a one-line why. Bias toward marking them MUST READ — you have context that shaped your thinking; the next agent doesn't. When in doubt, MUST READ.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

The file is the deliverable — don't also summarize it in chat. Write it to `agent/handoffs/YYYY-MM-DD-<descriptive-keyword-slug>.md`, then give the user the pickup prompt:

```
Continue from agent/handoffs/YYYY-MM-DD-<slug>.md — read it in full first.
```
