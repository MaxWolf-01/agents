# mx — Agent Workflow Plugin

File-based specs and tickets, domain glossary + ADRs, research artefacts, and session continuity for multi-session work.

## Artefacts

| Object     | Location                           | Lifecycle                           | Content                                             |
| ---------- | ---------------------------------- | ----------------------------------- | ---------------------------------------------------- |
| Glossary   | `CONTEXT.md` (repo root)           | durable, edited in place            | domain terminology — opinionated, with avoid-lists   |
| ADR        | `decisions/NNNN-slug.md`           | durable, append-only                | one hard-to-reverse decision and why                  |
| Spec       | `agent/tasks/<feature>/spec.md`    | committed; `git rm -r` when shipped | the work order for one feature                        |
| Ticket     | `agent/tasks/<feature>/NN-slug.md` | retired with its feature            | one vertical slice with blocked-by edges              |
| Small task | `agent/tasks/<slug>.md`            | deleted when done                   | ticket-shaped, no spec                                |
| Research   | `agent/research/NN-slug.md`        | gitignored, ephemeral               | one question, cited findings                          |

The `tracker` skill defines the file conventions (status, blocked-by, frontier, claiming); a repo can override them (e.g. GitHub Issues) in its CLAUDE.md.

## The main flow: idea → ship

`/mx:grill-with-docs` (relentless interview; glossary terms and ADRs land as residue) → `/mx:to-spec` (thread → work order) → `/mx:to-tickets` (tracer-bullet vertical slices with blocking edges) → `/mx:implement` per ticket (tdd inside, code-review at the end), fresh context each.

**`/mx:orient` is the map** — the main flow, its on-ramps, and when to reach for what.

## Skills & commands

| | |
| --- | --- |
| `/mx:orient` | the router — start here |
| `/mx:grill-with-docs`, `/mx:grilling` | sharpen a plan by interview |
| `/mx:domain-modelling`, `/mx:codebase-design` | vocabulary layers: domain language + ADRs, deep-module design |
| `/mx:to-spec`, `/mx:to-tickets` | conversation → spec → tickets |
| `/mx:implement`, `/mx:tdd`, `/mx:code-review` | work a ticket; test-first; three-axis review |
| `/mx:prototype` | throwaway code to answer a design question |
| `/mx:diagnosing-bugs` | tight-loop debugging for hard bugs |
| `/mx:improve-codebase-architecture`, `/mx:bloat-audit` | codebase health |
| `/mx:research` | primary-source investigation → cited artefact |
| `/mx:codex` | second opinion from a different model |
| `/mx:handoff`, `/mx:transcript`, `/mx:recap`, `/mx:todos`, `/mx:reflect` | session continuity & status |
| `/mx:writing-skills` | reference for writing skills well |

Plus assorted utilities: `mermaid`, `tyro-cli`, `python-project-setup`, `stop-slop`, `session-name`, `restore-sessions`, `permissions-review`, `review-pr`, `changelog`, `dependabot-triage`.

---

**Local development:**

```bash
rm -rf ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
ln -s /path/to/mx ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
```

`claude plugin update mx@MaxWolf-01` replaces the symlink.
