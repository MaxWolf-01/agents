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
| `/distill [scope]` | Sync knowledge with code reality (always in a fresh session) |
| `/learnings` | Extract gotchas/patterns into knowledge (within session) |
| `/transcript` | Save session transcript for later pickup |
| `/recap` | Status report surfacing decisions and open questions |
| `/todos` | Overview of active task files |

## Skills

| Skill | Purpose |
|-------|---------|
| **implement** | Loads coding best practices and principles. For the mechanical part — translating an idea into clean code. Not always-on; loaded when it's time to write code. |
| **handoff** | Curated session summary for continuation in a new session |
| **session-name** | Generate long, descriptive, searchable session names for `/rename` |
| **restore-sessions** | Recover old sessions after crashes or when tmux history is lost |
| **tyro-cli** | Patterns and features for building CLIs with tyro — documentation for humans and LLMs, `--help` best practices |

## Planned

| Name | Type | Purpose |
|------|------|---------|
| **reflect** | command | Within-session post-implementation reflection. "Now that you've experienced the implementation, where was the friction? What assumptions broke? Where is the architecture fighting the feature? What would you redesign?" |
| **roast** | command | Standalone bird's-eye critical review of codebase or module. Architecture, coupling, code smells, structural debt. Heavier than reflect — needs to actually read and understand the code. |
| **codex** | skill | Second opinion from a different model (OpenAI Codex). Packages context (transcript, CLAUDE.md, code) and gets an independent critique. Usable standalone, but also layered into other commands — e.g., /roast fans out codex sub-agents alongside its own analysis for a more diverse review. Also useful for /recap or as a general "get a second perspective" tool. |
| **init-knowledge** | command | Bootstrap a knowledge base for an existing project from scratch. Sequential, not parallel — writing good knowledge requires deep understanding. Planned after distill improvements. |

## How This Gets Used

Most sessions don't need ceremony. You talk to the agent, work through a problem, ship it.

**`/research` is the default entry point for non-trivial work.** It shifts the model into investigation mode instead of jumping to implementation. Research artefacts separate sources and findings from the task itself — "these sources → these conclusions" — keeping issues clean while preserving the evidence trail. They also serve as a searchable, compact audit trail over thoughts and resources, far more accessible than digging through session transcripts. Discussion of approaches, goals, and intent refinement happens in chat afterward.

**`/task` is for things that need to survive context loss.** New features, multi-session work, complex problems that branch into multiple research questions. Most quick fixes and single-session bug fixes don't need a task file.

**`/distill` is periodic maintenance** — always in a fresh session, since it needs to analyze the full change set plus broader knowledge context.

**`/learnings` is within-session** — extract insights into knowledge while the context is still hot.

## Knowledge Structure

Flat files connected by wiki-links. Hubs (project overview in CLAUDE.md, domain entry points) create short paths to any topic. Knowledge files describe what IS — grounded in code, not aspirational.

---

**Local development:**
```bash
rm -rf ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
ln -s /path/to/mx ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
```
`claude plugin update mx@MaxWolf-01` replaces the symlink.
