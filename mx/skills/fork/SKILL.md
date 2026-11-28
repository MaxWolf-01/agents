---
name: fork
description: "Fork this session: spawn an agent that inherits the full conversation transcript, so delegated work keeps the current mental model without restating it in a prompt. Use when offloading a context-heavy side task (a heavy artifact build, a noisy investigation) out of the main conversation, or when another skill routes work to a fork."
---

# Fork

A fork is a new agent that inherits this conversation's full transcript, so the mental model transfers with nothing restated. Fork when the task needs that mental model; a task a few self-contained sentences can state goes to an ordinary subagent.

Give the fork **one bounded directive**. It carries your entire context and may run with permissions skipped, so the directive states its bounds explicitly: do only this task, write only the named output paths, nothing destructive, no installs or config changes outside the task's own sandbox (a venv, a scratch dir), stop when done and report the output path.

## How

Agent tool with `subagent_type: "fork"`. Requires `CLAUDE_CODE_FORK_SUBAGENT=1` in the settings `env` (set in claude/settings.json; it force-enables a feature behind a rollout gate).

If the agent type is unavailable (`Agent type 'fork' not found`), fork via the session-forking CLI: [CLI.md](CLI.md).
