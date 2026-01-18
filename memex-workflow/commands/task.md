---
description: Capture or continue work on a task
argument-hint: [task-name-or-topic]
---

Capture or continue work on a task.

Arguments: `$ARGUMENTS`

## First: Check What Kind of Entry This Is

**If the argument is a handoff or session export** (e.g., `agent/handoffs/2026-01-10-workflow-design.md` or `abc123.txt`):
→ Use the **pickup skill** to resume. It handles both curated handoffs and session exports.

**If the user wants to continue from a handoff but doesn't have the path**:
→ Use the **pickup skill** — it has instructions for listing available handoffs.

**If the argument is a task file or topic** (e.g., `agent/tasks/...` or a topic name):
→ Continue with the process below.

**If no argument or just discussing an idea**:
→ Ask the user what they want to work on. Don't immediately create a task file — first discuss, think through the idea, then ask if a task file should be created before proceeding with the full process.

## What Tasks Are

Tasks capture intent, not implementation state. The code is the implementation state. Git is the history.

A task file contains:
- **Intent/Purpose** — What the user wants and why
- **Assumptions** — Explicit and surfaced
- **Considered & Rejected** — Approaches explored but dropped
- **Discussion History** — Clarifications, mental model evolution
- **Sources** — Wiki-links to knowledge files + external docs (MUST READ / Reference)

Tasks are NOT:
- Implementation logs (that's git)
- Code snippets (that's the code)
- Gotchas for future reuse (that's knowledge files)

## Process

### 1. Determine the Task

If a task file or topic was specified in arguments:
- Find or create it in `agent/tasks/`
- New files use date prefix: `YYYY-MM-DD-<slug>.md`

If no arguments:
- Search memex for active tasks: `grep "^status: active" agent/tasks/*.md`
- Ask what to work on or capture

### 2. Explore the Knowledge Base

**This is non-negotiable.** Before doing any significant work — including brainstorming and discussion:

- [ ] **Read `overview.md`** — the entry point to project knowledge, always
- [ ] **Read relevant knowledge files** — follow wikilinks from overview that relate to your task
- [ ] **Read project context files** — dev setup, conventions, things needed to work effectively
- [ ] **Search for related tasks** — previous work on similar problems
- [ ] **Read MUST READ sources** from the task file if continuing existing work
- [ ] **Read key code files** when the task requires understanding implementation

Use memex `explore` to follow wikilinks — it shows outlinks (what a note references) and backlinks (what references it).

Continue until you feel confident about the project structure and task context.

**What good exploration looks like:** (simplified example)

> Task: "Fix a bug where audio doesn't play for some documents"
>
> 1. Read `overview.md` → see Core section links to [[tts-flow]] and [[document-processing]]
> 2. Read both — the bug could be in either pipeline
> 3. Notice tts-flow has a "Voice change race condition" gotcha — could this be it?
> 4. Follow cross-references — tts-flow links to [[audio-playback]], which has a gotcha about WebSocket timing issues
> 5. Read related task [[2025-12-15-audio-websocket-fix]] — see they fixed a similar issue by [...]
> 6. Read the Key Files — now you know which source files to examine
> 7. The bug is still unclear? Maybe it's a frontend issue? -> Explore [[frontend]] to get up to speed on client-side audio handling.

This takes ~30 seconds. Without it, you'd grep around, miss the gotcha, and waste time rediscovering known issues.

**Bad exploration:** Read overview, skim one file, skip cross-references and gotchas. Miss critical context.

The knowledge, pointers, and bigger picture help you build an accurate mental representation — the foundation for effective problem-solving. Documented gotchas help you avoid repeating past mistakes.

### 3. Understand the Intent

If continuing an existing task:
- Read the task file
- Read any MUST READ sources listed
- Read linked knowledge files

If creating a new task, do the thinking first — then clarify:

**You do 90% of the work.** Don't lazily offload questions to the user. Your job is to:

1. **Deeply analyze** — What does their request imply? What are the realistic approaches? What constraints exist in the codebase? What trade-offs matter?

2. **Think through each option** — For each viable approach:
   - What are the pros and cons?
   - What does it require (dependencies, migrations, API changes)?
   - What are the risks and edge cases?
   - How does it fit with existing patterns?

3. **Form a recommendation** — Based on your analysis, which approach makes most sense? Why? Be opinionated.

4. **Present the full analysis** — Write it out. Show your reasoning. The user should see you've genuinely thought through the problem.

5. **Then ask what you actually need to know** — After all that analysis, what decisions genuinely require user input? These might be:
   - Preference questions where trade-offs are clear but choice is subjective
   - Scope decisions (MVP vs full feature)
   - Constraints you couldn't infer (timeline, must-haves)
   - Validation of your recommendation

**Use AskUserQuestion for structured input** when you have specific options to choose between. But the questions should emerge FROM your analysis — they're the genuine decision points you identified, not generic "what do you want?" prompts.

**The pitfall to avoid:** Using AskUserQuestion as a substitute for thinking. If you haven't done the analysis, you haven't earned the right to ask questions.

**Don't use phases to defer complexity.** If something needs refactoring, refactor it. If something needs clarification, ask. "Phase 1: do it the old way, Phase 2: migrate" is usually avoidance — do it right once instead of twice.

**Don't default to "pragmatic" just "because it's already there."** Agents overestimate implementation cost — a ~1h human task is ~10min for an agent. "Keep the old thing because it works" is often false economy. If doing it properly is better long-term without overengineering, just do it.

### 4. Capture or Update

For new tasks, create the file with this structure:

```markdown
---
status: active
started: YYYY-MM-DD
---

# Task: <Descriptive Title>

## Intent

What user wants. Their mental model. Why this matters.

## Assumptions

What we're taking for granted. Surface these explicitly.

## Sources

**Knowledge files:**
- [[knowledge-file]] — why relevant

**External docs:**
- MUST READ: [Doc title](url) — next agent needs this before working
- Reference: [Doc title](url) — consulted, key finding was X

**Key code files:**
- MUST READ: `path/to/file.py` — why this file matters
- Reference: `path/to/other.py` — related context
```

Use MUST READ for anything the next agent genuinely needs to read from scratch. Use Reference when you've distilled the key insight and they can skip unless diving deeper. Don't just list files — explain why each matters.

**Bias toward MUST READ.** You have context that shaped your thinking — the next agent doesn't. They need the big picture, not just the immediate task. When in doubt, mark it MUST READ. A 10-file MUST READ list is fine if those files genuinely matter.

**DO NOT** write task files before exploration/brainstorming/clarifying with the user.
Recommendations, ideas, etc. are discussed in chat first, the distilled versions/options/understanding goes into the task file.
Task files capture decisions and findings, not pre-discussion brainstorming

## Done When

(What does success look like? Checklist of acceptance criteria if helpful.)

## Considered & Rejected

(Fill as approaches are explored and dropped)

## Discussion

(Capture clarifications, mental model corrections, key decisions)
```

For existing tasks:
- Refine Intent if understanding has deepened (rewrite, don't append)
- Add to Assumptions as they're surfaced
- Add to Considered & Rejected as approaches are explored
- Update Discussion with significant clarifications

### 5. Work

With intent clear, proceed with the work. The task file is your north star.

**When moving to implementation** — once planning is complete, assumptions are validated, and you're ready to write code — use the **implement skill**. It provides the mindset and practices for coding.
You MUST invoke the **implement skill** before writing ANY code, regardless of task size

**Update the task file when understanding changes:**
- User clarifies intent or corrects your mental model
- Assumption gets validated (was implicit, now confirmed)
- Decision made on approach (and why)
- Research finding changes constraints

**Don't update for:**
- Implementation progress (that's git)
- Status updates ("did X, now doing Y")
- Work diary entries

The distinction: capture what matters for **intent**, not what you're **doing**.

When you discover gotchas or reusable patterns, note them for later extraction to knowledge files (via /distill or /learnings).

## The USE Principle

When updating task files, don't write:
- **U**nimportant — things that don't matter for continuing the work
- **S**elf-explanatory — obvious from code, context, or common knowledge
- **E**asy to find — documented elsewhere (link instead of duplicating)

Task files capture what matters for **intent and decision-making**, not everything that happened.

## Task Types

### Regular Tasks
Single-focus work items. Most tasks are this.

### Tracking Tasks
Meta-tasks that collect context for larger undertakings (like GitHub tracking issues).

**Use descriptive filenames** — include "-tracking" or similar in the name:
- `2026-01-10-auth-migration-tracking.md`
- `2026-01-08-gemini-integration-tracking.md`

**Structure:**
- High-level intent and goals
- Links to subtasks via wiki-links
- Collected documentation sources
- High-level decisions (detail in linked files)
- Gotchas that apply to ALL subtasks

**Example hierarchy:**
```
[[auth-migration-tracking]]
├── [[auth-migration-research-jwt-vs-sessions]]
├── [[auth-migration-backend-implementation]]
└── [[auth-migration-frontend-token-handling]]
```

Each subtask links back to the tracking task. Agents working on subtasks read the tracking task first for full context.

### Subtasks

Create a subtask when work can be **delegated** — isolated enough to spec out, substantial enough that fresh context helps.

**Good candidates:**
- Isolated implementation (backend while you hold frontend context)
- Research/investigation that would consume context
- Prerequisites that block but don't need big-picture context

**The test:** Is speccing it out less work than just doing it? If explaining the task is as much work as doing it, just do it yourself.

**When to split (same principle as knowledge files):**
- Has its own isolated set of concerns/links
- Can be understood independently
- Another agent could work on it without your full context
- Reduces complexity of the parent task

## Filename Guidelines

Use date prefix + descriptive keywords:
- `YYYY-MM-DD-<keywords-separated-by-dashes>.md`
- Include all major topics — more detail is better for differentiating
- If it's a subtask, you can reference the parent in the name
- Examples:
  - `2026-01-10-workflow-overhaul-commands-implementation.md`
  - `2026-01-09-gemini-extraction-prompt-latex-handling.md`
  - `2026-01-08-mobile-playback-safari-audio-context-fix.md`

## Notes

- Tasks can link to parent/tracking tasks via wiki-links
- Task files link TO knowledge (bottom-up), not vice versa (unless knowledge needs to reference historical reasoning)
- Don't update continuously — sync at natural stopping points or when context is high
- For handoffs, use the **handoff skill**, not task file updates
- Completed tasks are historical records of thought processes — keep for reference

- Task file = spec + decisions + rationale. Contains the "what" and "why" — goals, constraints, key decisions with reasoning, sources that informed those decisions. Should be readable in 3 months and still make sense. External docs belong here if they informed a decision.
- Task file ≠ implementation plan. Grand implementation checklists don't survive first contact with code. The detailed steps live in the handoff or emerge during implementation.
- Handoff = continuation context. What the next agent needs to pick up this specific work — which files matter, what was tried, what failed, what's the immediate next step. Can duplicate sources from task file but emphasizes urgency ("MUST READ before coding"), can include more detailed implementation notes.
- The split: Task file captures understanding that persists. Handoff captures momentum that transfers. If the handoff gets stale (work takes a different direction), the task file should still be accurate.

