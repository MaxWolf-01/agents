---
status: review
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

- [x] A commit made in a Claude Code session carries `Session: <id>`, and one made outside a session carries none.
- [x] Amending a commit, rebasing it and merging it leave exactly one trailer.
- [x] Demo: `git log -1 --format=%B` of a commit made in a session, and of an amend of it.

## Comments

**2026-09-23**, orchestrator. A `prepare-commit-msg` hook in the dotfiles adds `Session: <id>` from `$CLAUDE_CODE_SESSION_ID`, wired globally by home-manager as a git config hook. Built and tested on branch `git/session-trailer` of `~/.dotfiles` (worktree `/var/tmp/wt-session-trailer`), one commit and one review round, not merged, and not switched on: it takes effect on a machine after the merge and an `hmswitch` (`nswitch` on pc). Review page: `agent/diffviews/board-orients/06-session-trailer-hook.html`.

**Demo.** A throwaway repo committing under the git config home-manager builds from the branch (`GIT_CONFIG_GLOBAL` pointed at the built file), inside this session:

```
$ git log -1 --format=%B
a commit made in this session

Session: 70c7b682-6f05-4244-a254-42af2dbe28cb

$ git log -1 --format=%B   # after an amend
the same commit, amended

Session: 70c7b682-6f05-4244-a254-42af2dbe28cb

$ git log -1 --format=%B   # outside a session
a commit made outside a session
```

`git/hooks/claude-session-trailer.test` drives real commits through the hook, wired the same way: in a session, outside one, amend twice across two sessions, a `--no-ff` merge, a rebase that rewrites every commit, a message ending in `Co-Authored-By`, and a commit through the editor with `--verbose`. 13 checks pass; swapping `doNothing` for `add` or `replace` in the hook fails 4 and 2 of them.

**I need from you**

- [D1] **Merge and switch it on?** Merge `git/session-trailer` into the dotfiles' master, then `hmswitch` here and `nswitch` on pc. Until then no commit carries the trailer, and ticket 05 builds against fixtures only.
- [D2] **Off under `~/work`, as built?** The include that sets the work address also turns the hook off there. The trailer is a random UUID and identifies no account, but it would put a convention of ours into the team's history. Turning it on there means deleting that one line.
  - Ruled 2026-09-23: on under `~/work` too; the include went back to setting only the address (`18b5f5e`).

**Details, if you want them**

- [D3] Assumptions
  - A1 `nix/home/common.nix`: a config hook (`hook.claude-session.*`, git 2.54 or later), not `core.hooksPath`. With `core.hooksPath` set, git stops running every repo's own `.git/hooks`, including this repo's pre-push plugin update and the vault's pre-commit. Probed on git 2.55: a config hook and a `.git/hooks` hook both run on the same commit. The spec's "beside the pre-push hook" holds for the file only; that hook is symlinked into one repo by `setup`, which could not cover every repo.
  - A2 `nix/home/common.nix`: the command is the hook's copy in the Nix store, not the file in `~/.dotfiles`. If the checkout were on a branch without the file, git would fail every commit on the machine. The cost is that an edit to the hook needs an `hmswitch`.
  - A3 `git/hooks/claude-session-trailer`: the first trailer wins. An amend in a second session keeps the first session's id, since `--if-exists doNothing` adds nothing when a `Session:` trailer is already there. Amending a commit that has no trailer, inside a session, adds that session's id: the session rewrote the commit.
  - A4 Probed on git 2.55: a plain rebase does not run `prepare-commit-msg` at all. `--force-rebase`, reword and squash do run it, with the old message, and that message already carries its trailer.
  - A5 Not installed for the worker users on pc (`nix/home/worker.nix`). The board leaves out sessions from other hosts, so nothing would read their trailers.
