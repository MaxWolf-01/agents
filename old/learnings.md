---
description: Extract learnings from a session into knowledge files
argument-hint: [transcript-path-or-nothing]
allowed-tools: Read, Grep, Glob, Bash(cat:*)
model: opus
---

Extract learnings from a session and update or create knowledge files.

Arguments: `$ARGUMENTS`

Read provided files or session transcripts in full before analyzing.

## Analyze

Read through looking for:

- **Gotchas** — What went wrong that wasn't obvious? Incorrect assumptions? Misleading errors?
- **Patterns** — What approaches worked well? What sequences solved the problem?
- **Decisions** — What trade-offs were evaluated? What was chosen and why?
- **Missing context** — What would have been helpful to know upfront?
- **Friction** — Dev setup pain points, workflow inefficiencies, communication breakdowns, tooling gaps. Things that slowed the work down or caused frustration.

Apply 80/20: a session might have 10 interesting moments but only 2 worth persisting.

## Check Existing Knowledge

Before creating new files:
1. Use `mx search` and `mx explore` to find related knowledge
2. Check if learnings belong in an existing file vs a new one
3. **Prefer updating existing files** over creating new ones

## Update or Create

Write for future agents working on the project.

- State facts, not speculation. Ground in code truth.
- Link to code files, don't embed snippets.
- Include the "why" not just the "what."
- Add wikilinks to related knowledge files.

**New files:** `agent/knowledge/<topic>.md`. Only when the topic is genuinely distinct from existing files.

**Link direction:** Knowledge links to other knowledge. Tasks and research link to knowledge, not the other way around — knowledge stays stable, doesn't accumulate references to ephemeral work.

**Don't write:**
- Things obvious from code or common knowledge
- One-off issues unlikely to recur
- Extended code comments / docstrings
- Content already documented elsewhere (link instead)

## Report

Tell the user what you extracted, which files changed, and anything you chose NOT to capture.
