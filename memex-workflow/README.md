# Memex Workflow

Task files, handoffs, and a persistent knowledge base for multi-session work.

## Core Concepts

**Tasks** (`agent/tasks/`) — Capture user intent, goals, assumptions. Not implementation logs.

**Handoffs** (`agent/handoffs/`) — Session continuation state. Created via **handoff skill**, resumed via `/task <handoff-path>`.

**Knowledge** (`agent/knowledge/`) — Persistent reference docs. Updated via `/distill` (code-grounded) or `/learnings` (session-grounded).

Wiki-links (`[[name]]`) connect everything. Hierarchy from links, not folders.

## Commands

| Command | Purpose |
|---------|---------|
| `/task [name]` | Start/continue work, capture intent |
| `/distill [scope]` | Sync knowledge with code (run every 5-10 commits) |
| `/learnings [session]` | Extract gotchas/patterns from a session |
| `/align [session]` | Deep intent verification |
| `/explain [scope]` | Understand code changes |

`/align` and `/learnings` need a named session (`/session-name` + `/rename` first).

## Skills

| Skill | When used |
|-------|-----------|
| **handoff** | End of session when work continues |
| **pickup** | When `/task` is given a handoff path |
| **implement** | Moving from planning to coding |

`/task` orchestrates and tells the model when to use each skill.

## Typical Flow

1. `/task` to capture intent or pick up from handoff
2. Explore knowledge base (always start from `overview`)
3. Work on the task
4. **handoff skill** when ending session mid-work
5. `/distill` periodically to sync knowledge

## Fresh Context for Meta-Analysis

`/align`, `/explain`, `/distill`, `/learnings` should run in fresh sessions. The working agent has sunk-cost bias and tunnel vision. Fresh agents can challenge assumptions objectively.

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

