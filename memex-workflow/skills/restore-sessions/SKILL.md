---
name: restore-sessions
description: This skill should be used when the user asks to "find sessions", "find unfinished sessions", "recover sessions", "restore sessions", "what was I working on", "list recent sessions", "scan sessions", or needs to identify open/unfinished Claude Code sessions from a time range. Also triggered by session crashes, lost session IDs, or "restore my sessions".
---

# Restore Sessions

Find and classify Claude Code sessions from a project's session directory. Produces a comprehensive table of sessions with completion status, so the user can quickly identify unfinished work.

## When to Use

- User lost track of open sessions (crash, restart, etc.)
- User wants to find unfinished work from a time range
- User needs session IDs for continuation (`claude --resume <id>`)

## Session Directory

Claude Code stores sessions as `.jsonl` files in:
```
~/.claude/projects/<project-path-with-dashes>/*.jsonl
```

Subagent sessions live in subdirectories (`<session-id>/subagents/`) — these are excluded (they belong to their parent session).

Determine the correct project path from the current working directory. The path encoding replaces `/` with `-` and strips the leading slash. Example: `/home/max/repos/code/yapit` → `-home-max-repos-code-yapit`.

## Process

### 1. Run the scanner script

```bash
uv run python <skill-dir>/scripts/scan_sessions.py <sessions_dir> --days <N>
```

Arguments:
- `--days N` — only sessions modified within the last N days
- `--sessions N` — only the N most recent sessions (by modification time)

Both filters can be combined. If the user specifies "last 100 sessions or last 10 days, whichever is greater," run with `--days 10` first, then check if the count is under 100 — if so, run again with `--sessions 100`.

The script outputs a JSON array of session objects (newest first), each containing:
- `session_id`, `modified`, `size_kb`
- `user_msgs_total`, `user_msgs_substantive` — total vs. non-meta/non-system user messages
- `signals.commit`, `signals.transcribe`, `signals.handoff` — boolean completion indicators
- `interrupted` — whether the last user message was a request interruption
- `first_user` — first substantive user message (cleaned of command tags)
- `last_user` — last substantive user message
- `last_assistant` — last assistant message with >20 chars

### 2. Classify each session

For each session, assign one of these statuses:

**DONE** — Clear completion signal AND last messages confirm it:
- Committed + last assistant confirms ("Committed.", "Pushed.", etc.)
- Transcribed + last assistant shows transcript save
- Handoff written + last assistant confirms
- Health check / diagnostic agents (these are self-contained reports)
- `/mx:todos`, `/mx:distill`, or other info-only commands that completed

**JUNK** — Not worth showing:
- 0-1 substantive user messages with no real content
- Tiny size (<5KB) with no meaningful exchange
- Sessions that are just `/test`, `/context`, `/clear`, `/model`, `/rename` commands
- Duplicate starts (user opened session, typed nothing useful, started a new one)

**UNFINISHED** — Everything else. This is the default — be inclusive. When in doubt, mark as unfinished. Specifically:
- No completion signals AND substantial content
- `interrupted: true` (crash/abort mid-work)
- Has commit signal but last messages show continued work after the commit
- Last assistant message indicates ongoing work ("Let me check...", "Now let me...", mid-sentence)
- Last user message asked for something that wasn't addressed

**Key judgment calls:**
- A session can have `signals.commit: true` but still be UNFINISHED if work continued after the commit. Check `last_assistant` — does it reference the commit as final, or is there subsequent work?
- Sessions ending with `/mx:transcript` ARE done (the transcript captures the state for later).
- Sessions where last_user is a question or request and last_assistant doesn't resolve it → UNFINISHED.

### 3. Present results

Output a single table containing ALL non-junk sessions (both DONE and UNFINISHED), sorted newest-first.

```markdown
| # | Session ID | Topic | Date | Status | Notes |
|---|-----------|-------|------|--------|-------|
```

Column guidelines:
- **Session ID**: Full UUID (user needs this for `claude --resume <id>`)
- **Topic**: 5-10 word summary derived from `first_user`. Strip command prefixes (`mx:task`, `/mx:task`, etc.)
- **Date**: From `modified`, just date + time (e.g., "Feb 6 01:55")
- **Status**: One of: **DONE**, **UNFINISHED**, **MID-FIX**, **MID-DISCUSSION**, **MID-INVESTIGATION**, **MID-IMPLEMENTATION**, **MID-DESIGN**, **COMMIT PENDING**. Use specific mid-* labels for UNFINISHED sessions where the sub-state is clear from context.
- **Notes**: Brief context on what was happening / what's left. 10-20 words max.

Present the FULL table first, then optionally add a brief summary section highlighting the most urgent items (sessions from the last 1-3 days that are clearly unfinished).

### 4. Handle follow-up

The user may ask to:
- Resume a session: provide `claude --resume <session_id>`
- Get more detail on a specific session: re-read the `.jsonl` file's last ~10 messages
- Filter differently: re-run the script with adjusted parameters
