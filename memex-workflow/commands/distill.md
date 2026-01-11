---
description: Distill knowledge from recent code changes
argument-hint: [scope-or-instructions]
disable-model-invocation: true
---

You are updating knowledge files to match the current state of the codebase.

User's instructions: `$ARGUMENTS`

If no specific instructions, do a full distillation since the last distill commit.

## Find Starting Point

Look for the most recent commit with message starting with `distill:`:

```bash
git log --oneline --grep="^distill:" -1
```

If none exists, this is the first refinement. Ask the user for a reasonable starting point or lookback period.

## Gather Context

Get all commits since last refinement:
```bash
git log --oneline <last-refine-hash>..HEAD
```

Get the cumulative diff:
```bash
git diff <last-refine-hash>..HEAD
```

Check current state:
```bash
git status --short
```

If there are uncommitted changes, ask whether to include them (might be WIP from another agent).

Read task files that were touched (since the last refine-knowledge commit) — they provide context on what was being worked on, what's still brainstorming vs implemented.

## What Knowledge Files Are

Knowledge files describe **what IS** — grounded in code truth, not aspirational. They're the persistent reference that outlives individual tasks and sessions.

**Examples of knowledge files:**
- **Architecture docs** — how the TTS pipeline works, how documents flow through the system
- **Procedures/skills** — how to test Stripe locally, how to debug processor issues
- **Design principles** — frontend aesthetics, coding conventions
- **Tracking nodes** — `stripe-integration` linking to related subtopics and tasks
- **Decisions with rationale** — why we chose X over Y (when it needs space)

**Core principles:**

1. **Sources section** — Same pattern as tasks. Link to code files, external docs, related knowledge. Mark MUST READ vs Reference.

2. **Wiki-links are mandatory** — Every knowledge file should link to related files. Orphan files are anti-pattern. The graph structure IS the value.

3. **Describe what IS** — Not what was planned, not speculation. Task files are future-oriented; knowledge files are present-tense ground truth.

4. **Link, don't duplicate** — Link to code files, don't embed snippets. Link to external docs, don't copy content. Future agents can fetch fresh.

5. **USE principle** — Don't write:
   - **U**nimportant — things that don't matter for future work or understanding
   - **S**elf-explanatory — obvious from code or basic knowledge
   - **E**asy to find — documented elsewhere (link instead)

**When to create a new file vs keep inline:**

Split into a separate file when:
- **Isolated link cluster** — The topic has its own set of wiki-links that don't overlap with the parent; the "child" references things the "parent" doesn't care about
- **Multiple entry points** — You'd navigate to it from different places (If it's only reachable from one place, maybe it's just a section).
- **Clear interface** — You can name it clearly and reference it meaningfully.
- **Reduces parent complexity** — Including inline would dilute the parent's focus or make it too long to navigate (> ~300 lines).
- **Independent understanding** — Someone could read it and get value without having to read the parent first (even if context helps).

Keep inline when:
- Small, tightly coupled to parent context
- Only makes sense within the parent's narrative
- Would create a near-orphan (only one link to it)

**The test:** If you'd say "see the section on X" → keep inline. If you'd say "see the doc on X" → split.

## Update Knowledge Files

For each file in `agent/knowledge/`:
1. Read the current content
2. Check mentioned file paths — do they still exist? Were they renamed?
3. Check documented patterns — does the code still work this way?
4. Look for new gotchas in commit messages or code comments
5. Add new relevant links, remove stale references, ...

Base all updates on the **code ground truth**. Task files provide context (intent, what was explored) but knowledge files describe what IS, not what was planned.

Make targeted, factual updates:
- Fix file paths that moved/renamed
- Update pattern descriptions if implementation changed
- Add gotchas discovered from commits/code
- Remove references to deleted code
- Add Sources section if missing
- Ensure wiki-links connect to related files

**Do NOT:**
- Add code snippets (link to files instead)
- Add speculative content (only facts from code)
- Rewrite sections unnecessarily
- Create orphan files (always link from somewhere)

**Ambiguities:** If something is unclear — conflicting information, can't tell if code is intentional or WIP, etc. — use AskUserQuestion. Don't guess.

**Secrets:** Knowledge with private/secret information goes in `agent/knowledge/private/`.

## Commit

Stage agent files:
```bash
git add agent/
```

Commit with refine-knowledge prefix:
```bash
git commit -m "distill: <brief summary>"
```

Examples:
- `distill: update tts-flow.md paths after processor refactor`
- `distill: add gotcha about Gemini rate limits`
- `distill: sync knowledge with recent auth changes`

## Report

Tell the user what changed and why. If you had to make judgment calls, explain them.
