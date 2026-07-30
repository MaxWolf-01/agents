---
name: fork
description: "Fork this session — spawn an agent that inherits the full conversation transcript, so delegated work keeps the current mental model without writing a brief. Use when offloading a context-heavy side task (a heavy artifact build, a noisy investigation) out of the main conversation, or when another skill routes work to a fork."
---

# Fork

A fork is a new agent that inherits this conversation's full transcript — the mental model transfers for free, no brief to write. The cost: the fork reprocesses the whole parent transcript (cheap in cached tokens, real in latency, growing with context size). Fork when the task needs the shared mental model; a task expressible in a few self-contained sentences goes to an ordinary subagent instead.

Give the fork **one bounded directive**. It carries your entire context and may run with permissions skipped, so the bounds are part of the directive, stated explicitly: do only this task, write only the named output paths, nothing destructive, no installs or config changes outside the task's own sandbox (a venv, a scratch dir), stop when done and report the output path.

## How

Agent tool with `subagent_type: "fork"`. Integrated — the result streams back like any subagent, and permission prompts bubble up to the user. Requires `CLAUDE_CODE_FORK_SUBAGENT=1` in the settings `env` (set in claude/settings.json; the feature sits behind a rollout gate, the flag force-enables it).

If the agent type is unavailable (`Agent type 'fork' not found`), fork via the session-forking CLI: [CLI.md](CLI.md).
