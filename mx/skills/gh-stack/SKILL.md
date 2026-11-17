---
name: gh-stack
description: >
  Manages stacked PRs and splits multi-part work into reviewable branches with gh-stack.
  Use for stack creation, viewing, edits, push, submit, sync, rebase, merge, or checkout;
  when asked to split or isolate work for review; whenever a user mentions a stack,
  branch layers, or gh stack; or when a stack is checked out; when work has to go through PRs, and those PRs are dependent on each other.
metadata:
  author: github
  version: "0.2.0"
---

# gh-stack

Vendored from [github/gh-stack](https://github.com/github/gh-stack) `skills/gh-stack` at v0.3.0 (2a49e67, 2026-10-26), MIT; update by re-copying, keeping `references/github-side.md`, the line that points at it, the line under Core loop that points at `/mx:github`, and the description's last clause, which are local. The local copy is also pruned of what a current model does unprompted, and a re-copy prunes it again.

`gh stack` prints a stack trunk-first, left to right:

```
(main) <- auth <- api <- frontend
```

Left is the **bottom**: `auth` is based on `main` and merges first. Right is the **top**. `up`
moves away from trunk, `down` toward it. `references/stack-design.md` says how to choose the layers.

## Setup

Requires Git 2.36+ and an authenticated GitHub CLI.

```bash
gh extension install github/gh-stack
git config rerere.enabled true         # remember conflict resolutions
git config remote.pushDefault origin   # required if the repo has more than one remote
```

## Non-interactive use

Under a PTY, many `gh stack` commands open a prompt or a full-screen TUI and block forever; piped,
they error or print static text. Harnesses differ in which one you get, so always use the forms
in the table's first column.

**Multiple remotes:** without `remote.pushDefault` configured, pass `--remote <name>` to `push`,
`submit`, `sync`, `rebase`, and `link`. `checkout` and `trunk` have no `--remote` flag and require
the config.

| Always run | Never run bare | Why |
|---|---|---|
| `gh stack view --json` | `gh stack view` | opens a TUI under a PTY |
| `gh stack submit --auto` | `gh stack submit` | prompts for a title per new PR |
| `gh stack merge <target> --yes` | `gh pr merge` | `gh pr merge` cannot merge a stack |
| `gh stack init <branch>...` | `gh stack init` | prompts for branch names |
| `gh stack add <branch>` | `gh stack add` | prompts for a name, and fails even when piped |
| `gh stack checkout <target>` | `gh stack checkout` | opens a selection menu |
| `gh stack up` / `down` / `top` / `bottom` | `gh stack switch` | `switch` is menu-only |
| — | `gh stack modify` | TUI-only, no non-interactive path |

- **`checkout <pr>` when a different local stack already covers those branches** cannot be forced.
  Run `gh stack unstack --local` first (this keeps the stack on GitHub), then retry.
- **Worktrees:** local stacks share one common-directory catalog. Use `--print-path` with
  navigation or explicit-target `checkout` to locate a foreign-owned branch without stealing its
  checkout. Unoccupied targets are checked out here first.

## Branch placement

- **Starting multi-part work:** create the stack before writing files, and write each dependent
  concern into its own layer, bottom to top, rather than on trunk to split later.
- **Editing an existing stack:** check out the layer that owns the change before editing; a lower
  layer's concern is committed on that layer, never on the top branch.

```bash
gh stack down                   # or: gh stack checkout api
git add ... && git commit -m "Add get-user endpoint"
gh stack rebase --upstack       # replay every branch above onto the change
gh stack top                    # return to where you were
gh stack push
```

## Core loop

```bash
gh stack init auth              # create the stack and check out its branch
git add ... && git commit -m "Add auth middleware"
gh stack add api                # next layer, branched from the current one
git add ... && git commit -m "Add API routes"
gh stack submit --auto          # push every branch and open draft PRs
gh stack view --json            # confirm
```

`submit --open` creates PRs ready for review instead of drafts. Branch names are used verbatim.

The titles and bodies `submit --auto` generates are rewritten per `/mx:github`, then set with `gh pr edit`.

## Staying in sync

```bash
gh stack sync                   # fetch, reconcile with GitHub, rebase, push, refresh PR state
gh stack sync --prune           # also delete local branches for merged PRs
```

Non-interactive, `sync` prunes only with `--prune`. When the local and remote stacks have
diverged, it prints both chains, makes no changes, and exits 0 with `Sync aborted`; see
`references/troubleshooting.md`.

## Merging

```bash
gh stack merge 42 --yes          # PR #42 plus every unmerged PR below it
gh stack merge 7 --yes           # every unmerged PR in stack #7
gh stack merge 42 --yes --squash # or --merge, --rebase, --merge-method <method>
```

The merge is all-or-nothing: if any PR in the set cannot merge, none do. Without a method flag,
the last-used method applies. If the base branch uses a merge queue, the stack is queued instead,
the queue picks the method (a flag you passed is ignored with a warning), and queued PRs may land
in separate groups.

## Reading state

`gh stack view --json` writes JSON to **stdout**. Status messages go to **stderr**; branch on exit
codes rather than on them.

```
trunk           string
currentBranch   string
branches[]      name, head, base, isCurrent, isMerged, isQueued, needsRebase
branches[].pr   number, url, state ("OPEN" | "MERGED" | "QUEUED"); absent when no PR exists
```

`base` is the saved SHA of the parent branch that this branch was last known to contain, which can
lag the parent's current tip. `needsRebase` is true when the current parent tip is no longer
an ancestor of the branch.

## Exit codes

| Code | Meaning | Recovery |
|---|---|---|
| 0 | Success | — |
| 1 | Generic error | Read stderr |
| 2 | Not in a stack | `gh stack init`, or `gh stack checkout <target>` |
| 3 | Rebase conflict | Follow the Exit 3 recovery below |
| 4 | GitHub API failure | Check `gh auth status`, retry |
| 5 | Invalid arguments | Fix the invocation; see `<command> --help` |
| 6 | Disambiguation required | Branch is in several stacks; check out a non-shared branch |
| 7 | Rebase already in progress | `gh stack rebase --continue` or `--abort` |
| 8 | Stack file locked | Another `gh stack` process is writing; retry after ~5s |
| 9 | Stacked PRs unavailable | Not enabled on the repository; tell the user |
| 10 | Modify recovery required | `gh stack modify --abort` |

**Exit 3 recovery:**

- After `gh stack rebase`: resolve the files, run `git add`, then
  `gh stack rebase --continue`; use `gh stack rebase --abort` to restore the stack.
- After `gh stack sync`: the stack has already been restored. Run `gh stack rebase` to recreate the
  conflict, then resolve and continue as above.

## Constraints

- Stacks are strictly linear: one parent, at most one child. Use separate stacks for parallel work.
- `rebase` and `sync` automatically update affected clean worktrees; they never auto-stash or
  create/remove worktrees. Mutations serialize across the clone, and paused operations require
  recovery in their recorded owners.
- `modify` recovery flags may run from any worktree and act on the recorded native operation
  owners; resolve and stage only in the tree the diagnostic names, which need not be the caller's.
- There is no non-interactive reorder or removal. Errors may suggest `gh stack modify`, which is
  TUI-only; restructure with `unstack` then `init` instead.

## More detail

`gh stack help <command>` prints only the top-level help; use `gh stack <command> --help`.

- `references/github-side.md` — read before linking PRs that already exist into a stack, before
  merging a layer, when the merge box says the stack is out of date, and when `sync` or `rebase`
  asks for `--accept-base-change`.
- `references/stack-design.md` — read before creating a stack, when deciding how many layers to
  use, what belongs in each one, or whether work belongs in a new stack.
- `references/commands.md` — read when a command fails unexpectedly or you need its preconditions,
  side effects, atomicity, or ordering guarantees.
- `references/troubleshooting.md` — read on a rebase conflict, after a squash-merge, on local and
  remote divergence, when restructuring a stack, or when driving stacks from another tool.
