## Agent Workflow

This project has persistent knowledge and task tracking in `agent/`.

- `agent/knowledge/` — knowledge wiki (like Obsidian); project understanding, constraints, gotchas
- `agent/tasks/` — intent and decisions, definition of done, ...
- `agent/handoffs/` — curated session continuation
- `agent/transcripts/` — session continuation; user and assistant messages (without tool calls or thinking)

Use `[[name]]` (not `name.md`) for references between files.

Link directions:
- Tasks → Knowledge (task references what it needs)
- Handoffs → Tasks (handoff belongs to a task)
- Knowledge ↔ Knowledge (cross-links)
- Knowledge → Tasks (historical reasoning trails, tracking-issue style; rarer)

Hierarchy from links, not folders. Use memex `explore` to follow outlinks/backlinks.

Only knowledge files are tracked by git. Tasks, handoffs, and transcripts are ignored (global gitignore).

Don't commit knowledge files unless explicitly doing a distillation.
