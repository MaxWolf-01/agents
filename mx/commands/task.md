---
description: Create or pick up a task (decision record)
argument-hint: [task-name | handoff-path | transcript-path]
---

Create or pick up a task.

Arguments: `$ARGUMENTS`

Read provided files, handoffs, or transcripts in full before proceeding.

## What Tasks Are

Decision records. Like GitHub issues.

A task captures: what we want, why, what constraints exist, what "done" looks like.
A task links to research artefacts (`agent/research/`) for the heavy investigation output.

Tasks are NOT:
- Implementation logs (that's git)
- Session state (that's transcripts/handoffs)
- Code analysis or source listings (that's research artefacts)
- Gotchas for future reuse (that's knowledge)

## Intent Analysis

**You do 90% of the work.** Don't offload thinking to the user.

1. **Analyze deeply** — What does the request imply? What approaches exist? What constraints does the codebase impose?
2. **Think through each option** — Pros, cons, risks, edge cases, fit with existing patterns.
3. **Form a recommendation** — Be opinionated. Which approach and why?
4. **Present the analysis** — Show your reasoning. The user should see you've thought it through.
5. **Then ask what you genuinely need** — Preference questions, scope decisions, constraints you couldn't infer. Questions should emerge FROM your analysis.

Don't use questions as a substitute for thinking. If you haven't done the analysis, you haven't earned the right to ask.

Don't defer complexity to phases. "Phase 1: old way, Phase 2: migrate" is usually avoidance.

Don't default to "pragmatic" just because something exists. Agents overestimate implementation cost. If doing it properly is better long-term, just do it.

## Task File Structure

Statuses:
- `active` — we intend to work on this. Default when creating a new task.
- `backlog` — idea captured, not pursuing soon. Use for things explicitly parked.
- `done` — completed.

```markdown
---
status: active
refs: []
---

# <Descriptive Title>

## Intent

What we want and why.

## Assumptions

Things that, if wrong, would change the approach. Not obvious facts — hidden premises that need surfacing so they can be challenged.
For instance:
- What is assumed about the input?
- What is assumed about the environment?
- What would break this?
- What would a malicious caller do?

## Research

- [[research-artefact-name]] — what it covers

## Done When

What success looks like.

## Considered & Rejected

Approaches explored and dropped, with reasoning.
```

Filename: `YYYY-MM-DD-<descriptive-slug>.md` in `agent/tasks/`.

## Updating Tasks

Update when understanding changes:
- User clarifies intent or corrects your mental model
- Assumption gets validated or invalidated
- Decision made on approach (and why)
- New constraint discovered

Don't update for implementation progress — that's git.

Rewrite sections to reflect current understanding. Don't append chronologically.

When done, set `status: done`.

## Tracking Tasks

When work has independent sub-concerns, a tracking task captures the high-level intent and links to subtasks:

```
[[auth-migration-tracking]]
├── [[auth-backend]]
└── [[auth-frontend]]
```

Each subtask is a full task file with its own intent, assumptions, and research links. The tracking task is the overview — it doesn't duplicate what's in the subtasks.

Most tasks are standalone. Only split when sub-concerns are genuinely independent.
