# CLI fork

Fallback when the fork subagent type is unavailable — forks the session via the documented CLI. Mint the identifiers first; they make concurrent forks safe and every fork resumable:

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
- `--dangerously-skip-permissions` is needed here: headless runs can't answer prompts and session grants don't carry over. It is acceptable only because the directive is bounded (see SKILL.md).
- The transcript flushes per message — a fork launched mid-turn sees everything up to the previous tool result.
- Fire and forget: read the log when the pane exits nonzero, otherwise only to collect the result.
- `--resume-session-at <message-id>` forks from an earlier point, cutting a noisy tail out of the inherited context.
