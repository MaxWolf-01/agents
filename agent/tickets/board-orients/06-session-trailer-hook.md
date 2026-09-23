---
status: claimed
priority: 2
size: XS
---

# The Session trailer on every commit

## Brief

A git hook adds `Session: <id>` to every commit a Claude Code session makes, so the board can list who touched a ticket and any commit can be traced to the session that made it.

Slice of `spec.md`, building on the Decision on sessions from `Session:` commit trailers.

Outside this repo: the hook lives in the dotfiles, where no worker's worktree reaches, so the orchestrating session builds it in a dotfiles worktree rather than spawning a worker.

## What to build

A `prepare-commit-msg` hook in the dotfiles' global git hooks, beside the pre-push hook there, that adds the `Session:` trailer from `$CLAUDE_CODE_SESSION_ID` when the variable is set and the message carries no such trailer yet. An amend, a rebase and a merge never add a second one; a commit made outside a Claude Code session is untouched.

## Acceptance criteria

- [ ] A commit made in a Claude Code session carries `Session: <id>`, and one made outside a session carries none.
- [ ] Amending a commit, rebasing it and merging it leave exactly one trailer.
- [ ] Demo: `git log -1 --format=%B` of a commit made in a session, and of an amend of it.
