# Troubleshooting and recovery

## Contents

- [Rebase conflicts (exit 3)](#rebase-conflicts-exit-3)
- [After a squash merge](#after-a-squash-merge)
- [Local and remote stacks have diverged](#local-and-remote-stacks-have-diverged)
- [Restructuring a stack](#restructuring-a-stack)
- [Branch belongs to several stacks (exit 6)](#branch-belongs-to-several-stacks-exit-6)
- [Driving stacks from another tool or worktree](#driving-stacks-from-another-tool-or-worktree)
- [Stack file is locked (exit 8)](#stack-file-is-locked-exit-8)
- [An interrupted modify session (exit 10)](#an-interrupted-modify-session-exit-10)

## Rebase conflicts (exit 3)

`rebase` and `sync` both exit 3 on conflict. `sync` restores every branch to its pre-rebase state
first, so a failed `sync` leaves nothing half-applied; a failed `rebase` stops mid-flight and waits.

```bash
gh stack rebase
# exit 3 — conflicted paths are listed on stderr
git add <resolved paths>
gh stack rebase --continue     # repeat if the next branch also conflicts
```

`gh stack rebase --abort` restores every branch in the stack, not just the current one.

## After a squash merge

No manual action is needed: `gh stack sync` detects it and rebases with `--onto` against the
correct target, skipping the merged branch.

```bash
gh stack sync
gh stack view --json    # merged branch reports "isMerged": true, "state": "MERGED"
```

## Local and remote stacks have diverged

When non-interactive, `sync` prints both chains, changes nothing, and exits **0** with
`Sync aborted`, so exit 0 does not mean the sync happened: check for that message, or re-run
`gh stack view --json` and compare.

- **Keep the remote version.** Drop local tracking and pull the stack back down.

  ```bash
  gh stack unstack --local          # keeps the stack on GitHub
  gh stack checkout <stack-number>  # or a PR number
  ```

- **Keep the local version.** Remove the grouping on GitHub, then recreate it from local state.

  ```bash
  gh stack unstack                  # removes the grouping; PRs and branches survive
  gh stack init --base main branch-1 branch-2  # use your trunk and desired branch order
  gh stack submit --auto
  ```

Neither path deletes pull requests or branches.
Merged or queued PRs remain stacked on GitHub, but successful unstacking still removes local
tracking. If every PR is locked, GitHub rejects the operation and local tracking is retained.

## Restructuring a stack

There is no non-interactive reorder, rename, or removal. `add` run from the wrong branch suggests
`gh stack modify`, but that is TUI-only. Tear the stack down and rebuild it instead:

```bash
gh stack unstack                       # removes local tracking and the GitHub grouping
# Rename or drop branches, and rewrite ancestry as needed.
gh stack init --base main branch-1 branch-2 branch-3
gh stack submit --auto                 # re-link on GitHub
```

`init` adopts the branches that already exist, and their PRs survive; once Git ancestry is correct,
`submit` updates their base branches and re-links the stack on GitHub.

Changing metadata does **not** change Git ancestry. Reorder commits first, then rebuild the stack.
For example, to change `main <- models <- migration <- ui` into
`main <- migration <- models <- ui`:

```bash
old_models=$(git rev-parse models)
old_migration=$(git rev-parse migration)
git rebase --onto main "$old_models" migration
git rebase --onto migration main models
git rebase --onto models "$old_migration" ui
gh stack unstack
gh stack init --base main migration models ui
```

Preserve the old boundary SHAs before
moving any branch. For a different reorder, identify each layer's range with
`git log <old-parent>..<branch>`, then replay the ranges bottom to top.

## Branch belongs to several stacks (exit 6)

Commands exit 6 when the current branch cannot identify a single stack — typically because it is the
trunk of more than one stack. There is no flag to disambiguate.

```bash
gh stack checkout <a-branch-unique-to-the-intended-stack>
```

Then rerun. Commands given an explicit stack number (`merge 7`, `unstack 7`) do not infer the stack
from the current branch, so they never hit this.

## Driving stacks from another tool or worktree

`gh stack link` creates and updates stacks through the API alone, with no local tracking state: use
it when jj, Sapling, git-town or another tool outside gh-stack's local catalog manages the branches.
Linked worktrees share `<common-dir>/gh-stack` and do not require `link`.

```bash
gh stack link branch-a branch-b branch-c        # bottom to top
gh stack link --base develop --open a b c       # non-default trunk, ready for review
gh stack link 10 20 30                          # by PR number
gh stack link 7 feature-d                       # append to existing stack #7
```

With no local state, `up`, `down`, `top` and `bottom` do not work on a linked stack;
`gh stack checkout <stack-number>` adds local tracking later.

Legacy worktree catalogs are consolidated automatically only when their
definitions agree or are disjoint; originals are preserved. On migration conflicts, reconcile the
reported source definitions rather than choosing the newest file. Finish legacy operations in
their original worktree first, and do not mix old and new gh-stack writers in one clone.

## Stack file is locked (exit 8)

Another `gh stack` process holds either the short catalog lock (`<common-dir>/gh-stack.lock`) or
the clone-wide mutation lock (`<common-dir>/gh-stack-operation.lock`). Wait and retry, leaving
the lock files in place; read-only views remain available. Paused operations are also guarded by
shared recovery journals after their process lock has been released.

## An interrupted modify session (exit 10)

`gh stack modify` is TUI-only, so an agent never starts one. A repository someone else left in
this state is restored with:

```bash
gh stack modify --abort
```
