---
status: open
priority: 2
size: S
blocked-by: [ticket-file-contract]
---

# The glossary and the ADRs live in the agent repo

## Brief

`CONTEXT.md` and `decisions/` move from the code repo's root into its agent repo, beside the tickets, so every piece of the workflow's own record is in one private place. A public project stops showing its glossary and ADRs next to its code; the user accepts that, since what a human reader wants is documentation in its own form, not the workflow's record.

Ruled by the user on 2026-09-25, at `ticket-file-contract`'s close-out, after moving dotfiles' ADRs out of the secrets repo into dotfiles' agent repo. Shared agent collaboration is out of scope: where a team is involved, the seam is the one the user runs at work already, a private workflow and tracker, GitHub issues to talk with the team, and docs for everyone.

## Acceptance criteria

- [ ] Every skill, the workflow block in `claude/CLAUDE.md` and its copy in the worker contract name `agent/CONTEXT.md` and `agent/decisions/`, and `/mx:domain-modelling` writes them there.
- [ ] `/mx:code-review`'s check that runs `glossary-lint` when a diff touches the glossary or an ADR fires on the agent repo's branch, where they now change.
- [ ] This repo's `CONTEXT.md` and `decisions/`, where it has them, are moved into its agent repo with their history.

## Comments
