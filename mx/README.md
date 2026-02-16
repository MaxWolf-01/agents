# mx — Agent Workflow Plugin

Markdown-based issue tracking, research artefacts, knowledge persistence, and session continuity for multi-session work.

## Core Concepts

**Tasks** (`agent/tasks/`) — Markdown issue tracking: intent, assumptions, done-when. Not session logs. Committed to project repo.

**Research** (`agent/research/`) — Point-in-time investigation snapshots. Linked from tasks. Gitignored.

**Knowledge** (`agent/knowledge/`) — Persistent reference. Updated via `/distill` (code-grounded) or `/learnings` (session-grounded). Committed.

**Transcripts** (`agent/transcripts/`) — Exported sessions, tool calls and thinking stripped. Gitignored.

**Handoffs** (`agent/handoffs/`) — Curated session summaries for targeted continuation. Rare. Gitignored.

Wiki-links (`[[name]]`) connect everything. Hierarchy from links, not folders.

## Commands

| Command | Purpose |
|---------|---------|
| `/task [name]` | Create or pick up a decision record |
| `/research [topic]` | Investigate a question, produce a research artefact |
| `/transcript` | Save session transcript for later pickup |
| `/distill [scope]` | Sync knowledge with code (run periodically) |
| `/learnings [session]` | Extract gotchas/patterns into knowledge |
| `/explain [scope]` | Explain code changes with fresh eyes |
| `/recap` | Status report surfacing decisions and open questions |
| `/todos` | Overview of active task files |

## Skills

| Skill | When used |
|-------|-----------|
| **handoff** | Curated session summary for continuation |
| **implement** | Pre-coding readiness gate + coding guidelines |
| **session-name** | Generate descriptive session name |
| **restore-sessions** | Find unfinished sessions |
| **tyro-cli** | Scaffold a CLI script with tyro |

## Knowledge Structure

Flat files connected by wiki-links. Hubs (project overview in CLAUDE.md, domain entry points) create short paths to any topic. Knowledge files describe what IS — grounded in code, not aspirational.

## Fresh Context for Meta-Analysis

`/explain`, `/distill`, `/learnings` benefit from fresh sessions. The working agent has sunk-cost bias and tunnel vision.

---

**Local development:**
```bash
rm -rf ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
ln -s /path/to/mx ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
```
`claude plugin update mx@MaxWolf-01` replaces the symlink.
