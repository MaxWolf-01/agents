---
name: review-pr
description: "Review an existing GitHub PR with full codebase context — fetches the PR and drives code-review against its merge-base. Use when the user asks to review a PR (incoming, a collaborator's, or an already-pushed one)."
argument-hint: <PR number or branch>
---

# Review PR

Fetch the PR, then run the `/mx:code-review` skill with the PR's merge-base as fixed point and its description as spec. Arguments: `$ARGUMENTS`

## Process

1. **Fetch the PR**: `gh pr view <n>` (title, description), `gh pr view <n> --comments` (prior discussion), `gh pr view <n> --json baseRefName,headRefName`.
2. **Get the code locally**: if the head branch isn't already checked out, `gh pr checkout <n>` — in a fresh `/tmp` clone when the working tree is dirty or must stay untouched.
3. **Run the `code-review` skill** with:
   - fixed point = the PR's base branch (the three-dot diff lands on the merge-base),
   - the PR title + description + any linked issues as the spec source,
   - prior review discussion passed to the sub-agents, so settled points aren't relitigated.
4. **Report**: prepend `**What it does**: 1–2 sentences, end to end.` to the aggregated three-axis report. A clean PR gets a short review — don't invent concerns to fill space.
