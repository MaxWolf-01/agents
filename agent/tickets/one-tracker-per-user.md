---
status: open
needs-user: true
priority: 3
size: L
---

# One tracker for all of a user's repos, with research and show artefacts committed

## Brief

One workspace repo holding every project's tracker, with research and show artefacts committed, as your work setup already runs. The cost to weigh is that a feature's tickets would stop moving with its code.

## Questions

Raised by the user in the figures-and-demos grilling, 2026-09-16, and ruled worth grilling on its own. The work setup already runs this way: one agents repo for the organisation spans every code repo, and everything is committed, so nothing has to be sorted into tracked and untracked and a retired artefact is a `git rm` with history behind it. The personal repos keep a tracker each, `agent/research/` gitignored, `agent/show/` committed only once approved, and the failure that follows is on record: an agent picks up an old research or show artefact as current and corrects the design toward it.

The user's sketch: one workspace repo under `~/repos/github/MaxWolf-01/`, the code repos inside it as untracked clones, the tracker beside them; the board shows every project and hides the ones not in play; everything commits except what a script can rebuild, whose script commits instead. Shareability is fine, since these are one person's planning state.

What the current design supports, read from the tools on 2026-09-16:

- `board` finds the nearest `agent/tickets` up from the working directory, so a clone inside a workspace repo reaches the workspace's tracker, and its `--help` names that layout. One board per tracker; it does not traverse several.
- `dispatch` reads `agent/tickets/<feature>/` from the feature worktree of the code repo it runs in, commits claims on the feature branch, and renders review pages under the same tree. A tracker in a workspace repo is not where it looks, so a feature dispatched from the workspace would have no tickets to read and nowhere to write its claims. This is the part a workspace tracker changes.
- The tracker skill already names the workspace layout ("a workspace repo that holds the clones as untracked directories and the tracker beside them") without saying how dispatch finds it.

To decide, the options sketched by the agent, frame unconfirmed:

1. **Whether to do it at all.** For: one commit rule, one board, retirement by `git rm` everywhere, research kept forever in history. Against: a feature's tickets today ride the feature branch of the code repo, so a claim, a status flip and a spec round are on the branch the code is on; in a workspace tracker they are commits on a second repo, and a feature's state and its code stop moving together. That is the cost to weigh, not the migration.
2. **Layout.** A feature directory per repo (`agent/tickets/<repo>/<feature>/`) or a repo prefix in the slug; standalone tickets per repo or one pool; the queue file per repo or one.
3. **Migration.** A cutoff, where existing trackers stay in their repos until their features ship and new work starts in the workspace, or a move of every open ticket at once. The board tolerates both since it reads one tracker per invocation.
4. **Research artefacts until then.** Retire means delete, or move to a directory that survives and is backed up: `~/logs` is in the restic backups for twelve months, the XDG cache is not, which is the argument for `~/logs` if anything is kept at all. The figures-and-demos spec carries the interim rule; this ticket decides whether committing them makes it moot.

Out of this ticket, as the user said: how the design scales with larger models and one orchestrator for everything, and a global optmem memory. Both are for after the workflow has shipped.

An implementation the user sketched on 2026-09-25, after `ticket-file-contract` made `agent/` its own repo at `<code repo>/agent/` (so a ticket's code repo is the one containing `agent/`): one agent repo linked into several code repos, with an optional `repo:` field in a ticket's frontmatter that, when present, names the ticket's code repo and takes priority over that rule.
