# Memex Workflow

Task files, session continuity, and a persistent knowledge base for multi-session work.

## Core Concepts

**Tasks** (`agent/tasks/`) — Capture user intent, goals, assumptions. Not implementation logs.

**Transcripts** (`agent/transcripts/`) — Raw session exports for continuation. Created via `/transcript`, resumed via `/task <path>`. High fidelity, no "handoff slop".

**Handoffs** (`agent/handoffs/`) — Curated session summaries. Use when transcripts are too long or unfocused, or when targeted continuation is needed.

**Knowledge** (`agent/knowledge/`) — Persistent reference docs. Updated via `/distill` (code-grounded) or `/learnings` (session-grounded).

Wiki-links (`[[name]]`) connect everything. Hierarchy from links, not folders.

## Commands

| Command | Purpose |
|---------|---------|
| `/task [name]` | Start/continue work, capture intent |
| `/transcript <session-id>` | Save session transcript for later pickup |
| `/distill [scope]` | Sync knowledge with code (run every 5-10 commits) |
| `/learnings [session]` | Extract gotchas/patterns from a session (works in current session too) |
| `/align [session]` | Deep intent verification |
| `/explain [scope]` | Understand code changes |
| `/recap` | Status report surfacing decisions and open questions |
| `/session-name` | Generate descriptive session name for `/rename` |

`/align` and `/learnings` accept either a session export file path or a session name.

## Skills

| Skill | When used |
|-------|-----------|
| **handoff** | End of session when curated summary needed |
| **pickup** | When `/task` is given a handoff or transcript path |
| **implement** | Moving from planning to coding |
| **session-name** | Generate descriptive session name |

`/task` orchestrates and tells the model when to use each skill.

## Typical Flow

1. `/task` to capture intent or pick up from transcript/handoff
2. Explore knowledge base (overview is auto-injected, follow wikilinks)
3. Work on the task
4. `/transcript` when ending session mid-work (or **handoff skill** for curated summary)
5. `/distill` periodically to sync knowledge

## Fresh Context for Meta-Analysis

`/align`, `/explain`, `/distill`, should run in fresh sessions. The working agent has sunk-cost bias and tunnel vision. Fresh agents can challenge assumptions objectively.

## Knowledge Structure

Flat file structure with wiki-links:
```
overview
├── domain-topics (tts-flow, auth, billing, ...)
│   ├── gotchas, key files, cross-references
│   └── links to code + external docs
└── operations (migrations, infrastructure, ...)
```

Knowledge files point to sources — they don't duplicate code or external docs or code.
Hubs create a small-world network for efficient navigation.

## Orchestration

Currently human. You decide when to `/align`, when to handoff, when to spawn parallel sessions.

With headless mode (`claude -p`) and session resumption (`--resume`), an orchestrating agent could manage sessions the same way — launch tasks, monitor via transcripts, invoke alignment checks, coordinate handoffs.

---

**Local development:**
```bash
rm -rf ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
ln -s /path/to/memex-workflow ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
```
`claude plugin update mx@MaxWolf-01` replaces the symlink.

