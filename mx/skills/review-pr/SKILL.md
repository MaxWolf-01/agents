---
name: review-pr
description: "Review a PR with full codebase context. Use proactively: after creating a nontrivial PR, spawn a subagent with this skill for a fresh-eyes review before presenting to the user."
user_invocable: true
argument-hint: <PR number or branch>
---

# Review PR

Review a pull request with full codebase understanding. Arguments: `$ARGUMENTS`

## Process

### 1. Get the PR

- `gh pr view <number>` for title, description, author context
- `gh pr diff <number>` for the full diff
- `gh pr view <number> --comments` if there's prior discussion

### 2. Build the mental model first

Read every file touched by the PR — **in full**, not just the changed lines. Then follow references outward until you can answer:

- What does this change do, end to end?
- What's the user-facing behavior change?
- How does it interact with the rest of the system?

Specifically:
- Read callers of changed functions — who depends on this?
- Read types, protocols, interfaces that changed — what contracts shifted?
- Read project knowledge (`agent/knowledge/`) if the PR touches a documented domain
- Read related tests if they exist

**Do not form opinions during this phase.** You are building understanding, not evaluating.

### 3. Evaluate

Two passes: correctness, then quality. Both matter.

#### 3a. Correctness

For each potential finding, ask yourself before writing it down:

- **Is this actually a problem, or does it only look wrong because I'm reading a diff in isolation?** Check the surrounding code. Check existing patterns. Check callers.
- **What's the concrete consequence?** Name the specific failure mode (bug, security hole, data loss, perf regression, maintenance trap). If you can't name one, it's not an issue.
- **Does the existing codebase already handle this?** Check before flagging.

Things that are almost never issues:
- Style preferences the PR is internally consistent about
- Missing validation for inputs that can't actually arrive
- API semantics (PATCH, auth, error shapes) that match existing conventions
- "What if someone does X" when X is prevented by the system

#### 3b. Code quality

Read the new/changed code line by line. Apply these lenses:

- **Types**: Are types honest? Does the code lie to the type checker (`as any`, `!` non-null assertions on nullable values, arrays typed `T[]` that contain nulls)? Dishonest types hide bugs.
- **Structure**: Unnecessary nesting? Missing early returns/continues? `found` flags where a function extraction or direct return would be cleaner?
- **Naming**: Do names say what things are? Are abbreviations clear from context or cryptic?
- **Dead weight**: Unnecessary variables, redundant conditions, code that does nothing? Comments that restate what the code does ("what comments"), meta-commentary, or fluff?
- **Simplicity**: Could this be simpler without losing correctness? Fewer moving parts, less indirection, more direct expression of intent?

**Watch for LLM anti-patterns** — patterns that AI-generated code tends to introduce. Flag these in the reviewed code, and do NOT suggest them in your review:
- Wrapping things in try/except "just in case" — defensive error handling for failures that can't happen or that SHOULD be loud
- Adding validation for inputs that are already guaranteed by the system
- Over-abstracting: helpers/utilities/wrappers for one-time operations
- Comments that restate the next line of code (`# set x to 5` / `x = 5`), narrate the obvious, or add meta-commentary

**Zen of Python applies broadly** (not just Python):
- Simple is better than complex
- Flat is better than nested
- Explicit is better than implicit
- Readability counts
- If the implementation is hard to explain, it's a bad idea

### 4. Report

```
## <PR title>

**What it does**: 1-2 sentences, end-to-end.

### Architecture
Is the approach sound? Skip if straightforward.

### Bugs
Incorrect behavior. Each with: scenario that breaks, where (file:line), fix.

### Code Quality
Type honesty, structure, naming, unnecessary complexity, dead weight.
Each with: what's wrong, where (file:line), concrete fix.
"I'd write it differently" is not an issue — name the actual cost.

### Considerations
Non-blocking observations: trade-offs worth noting, things to watch for,
potential follow-ups. Not issues, just context.
```

Omit empty sections.

A clean PR gets a short review. Don't invent concerns to fill space.
