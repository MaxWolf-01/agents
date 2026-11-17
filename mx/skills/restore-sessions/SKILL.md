---
name: restore-sessions
description: Scan recent Claude Code sessions and classify unfinished work for resuming
disable-model-invocation: true
allowed-tools: Bash(uv run -q ${CLAUDE_SKILL_DIR}/scripts/scan_sessions.py --help)
---

# Restore Sessions

## Process

### 1. Run the scanner

```bash
uv run <skill-dir>/scripts/scan_sessions.py --days <N>
```

Run it from the project's directory. The classification below reads the fields its help names:

```text
!`uv run -q ${CLAUDE_SKILL_DIR}/scripts/scan_sessions.py --help`
```

If the user asks for "the last 100 sessions or the last 10 days, whichever is greater," run with `--days 10` first; if that returns fewer than 100, run again with `--sessions 100`.

### 2. Classify each session

Give each session one status:

**DONE**: Clear completion signal AND last messages confirm it:
- Committed + last assistant confirms ("Committed.", "Pushed.", etc.)
- Transcribed + last assistant shows transcript save
- Handoff written + last assistant confirms
- Health check / diagnostic agents (these are self-contained reports)
- `/mx:recap` or other info-only commands that completed

**JUNK**: Not worth showing:
- 0-1 substantive user messages with no real content
- Tiny size (<5KB) with no meaningful exchange
- Sessions that are just `/test`, `/context`, `/clear`, `/model`, `/rename` commands
- Duplicate starts (the user opened a session, typed nothing useful, and started a new one)

**UNFINISHED**: Everything else, and every session in doubt. It includes:
- No completion signals AND substantial content
- `interrupted: true` (crash/abort mid-work)
- `signals.commit: true`, but `last_assistant` shows work continuing after the commit rather than naming the commit as final
- Last assistant message indicates ongoing work ("Let me check...", "Now let me...", mid-sentence)
- Last user message asked for something that wasn't addressed

### 3. Present results

Output a single table of every non-junk session (DONE and UNFINISHED), newest first.

```markdown
| # | Session ID | Topic | Date | Status | Notes |
|---|-----------|-------|------|--------|-------|
```

Columns:
- **Session ID**: Full UUID (user needs this for `claude --resume <id>`)
- **Topic**: 5-10 word summary derived from `first_user`. Strip command prefixes (`mx:task`, `/mx:task`, etc.)
- **Date**: From `modified`, just date + time (e.g., "Feb 6 01:55")
- **Status**: One of: **DONE**, **UNFINISHED**, **MID-FIX**, **MID-DISCUSSION**, **MID-INVESTIGATION**, **MID-IMPLEMENTATION**, **MID-DESIGN**, **COMMIT PENDING**. Give an UNFINISHED session the specific mid-* label wherever its sub-state is clear.
- **Notes**: What was happening and what is left, in 10-20 words.

Present the full table first, then optionally a brief summary of the most urgent items (sessions from the last 1-3 days that are clearly unfinished).
