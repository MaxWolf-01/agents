---
name: fork
description: "Fork this session — spawn an agent that inherits the full conversation transcript, so delegated work keeps the current mental model without writing a brief. Use when offloading a context-heavy side task (a heavy artifact build, a noisy investigation) out of the main conversation, or when another skill routes work to a fork."
---

# Fork

A fork is a new agent that inherits this conversation's full transcript — the mental model transfers for free, no brief to write. The cost: the fork reprocesses the whole parent transcript (cheap in cached tokens, real in latency, growing with context size). Fork when the task needs the shared mental model; a task expressible in a few self-contained sentences goes to an ordinary subagent instead.

Give the fork **one bounded directive**. It carries your entire context and may run with permissions skipped, so the bounds are part of the directive, stated explicitly: do only this task, write only the named output paths, nothing destructive, no installs or config changes outside the task's own sandbox (a venv, a scratch dir), stop when done and report the output path.

## Primary: fork subagent

Agent tool with `subagent_type: "fork"`. Integrated — the result streams back like any subagent, and permission prompts bubble up to the user. Requires `CLAUDE_CODE_FORK_SUBAGENT=1` in the settings `env` (set in claude/settings.json; the feature sits behind a rollout gate, the flag force-enables it).

## Fallback: CLI fork

If the agent type is unavailable (`Agent type 'fork' not found`), fork via the documented session-forking CLI. Mint the identifiers first — they make concurrent forks safe and every fork resumable:

1. Read the parent id from `$CLAUDE_CODE_SESSION_ID`.
2. `uuidgen` → the fork's session id. Always pass it via `--session-id`: it is the handle to resume or interrogate the fork later (`claude --resume <fork-id>`, or `claude -p --resume <fork-id> '<follow-up>'`).
3. tmux session name `fork-<slug>-<first 8 of fork-id>` — unique, so concurrent forks never clash.

```bash
tmux new-session -d -s fork-<slug>-<id8> "env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID \
  claude -p --resume <parent-session-id> --fork-session --session-id <fork-id> \
  --dangerously-skip-permissions '<directive>' > <workdir>/fork.log 2>&1"
```

- `--fork-session` gives the child its own transcript; resuming without it interleaves both processes into one.
- Detached tmux with `CLAUDECODE` unset avoids the nested-interactive-claude freeze; `claude -p` this way is verified safe.
- `--dangerously-skip-permissions` is needed here: headless runs can't answer prompts and session grants don't carry over. It is acceptable only because the directive is bounded (see above).
- The transcript flushes per message — a fork launched mid-turn sees everything up to the previous tool result.
- Fire and forget: read the log when the pane exits nonzero, otherwise only to collect the result.
- `--resume-session-at <message-id>` forks from an earlier point, cutting a noisy tail out of the inherited context.
