# The markdown tracker

Tickets live as markdown files in `agent/tickets/`.

## Layout

- **Feature**: one directory per feature, `agent/tickets/<feature-slug>/`
  - `spec.md`: the work order for the whole feature, written round by round by `/mx:grilling`; frontmatter `status: draft | confirmed`, and a draft is never read as settled truth
  - `NN-<slug>.md`: tickets, build and decision alike (`/mx:tracker`, Decision tickets), numbered from `01`; written by `/mx:to-tickets`, or by any session that files a question. Every feature has at least one
- **Standalone ticket**: a single file `agent/tickets/<slug>.md`, no spec: a build ticket for work that needs no design round, or a decision ticket filed for later. It is committed on the tracker repo's integration branch from the main checkout, the one file a session writes outside its worktree: every session and the board read standalone tickets from there, while a feature's own tickets ride the feature branch; one filed on a branch anyway shows on the board tagged with that branch until it is moved. One that gets grilled is absorbed into its feature directory (see `/mx:grilling`). It is dispatched like a feature's ticket (`/mx:dispatch`), and the queue for standalone work is `agent/tickets/needs-human.md`, beside these tickets as a feature's is beside its own.
- **One tracker directory.** A project whose tracker sits at `agent/tasks/` is moved before anything is filed: `git mv agent/tasks agent/tickets`, as its own commit, repointing the project's own references (CLAUDE.md, scripts).
- **Numbering**: `NN` is an id, unique within its directory. Assign the next one by scanning the directory for the highest existing number and incrementing, never from an in-context picture of the board, which parallel sessions leave stale.

## Ticket state

Frontmatter:

```yaml
status: proposed | open | claimed | done
type: grilling # research | prototype | grilling | legwork on a decision ticket; omit on a build ticket
blocked-by: [01, 02] # ticket numbers within the feature, qualified <feature>/NN, or a standalone ticket's slug; omit when nothing blocks it
diff: [4f2a91c..8b3ce07] # commit ranges implementing the ticket; omit until the first lands
```

- `proposed` is the status of a ticket an agent filed that the user has not yet ruled on: an orchestrator's reading of a worker's friction or a harden line, a review session's finding too large to fix there, a punt. It is on the frontier and `claim` takes it like an open one, so what waits is the ruling and not the build: the user rules on the artifact the build produced. Its body opens with one line of provenance: what it was cut from (which closing comment, harden line, review finding, or the spec whose slice it is) and why it is worth a ticket. `open` is the status of a ticket already **ruled** and not yet built; a ticket the user asked for in conversation and a grilling's decision tickets are rulings already, and silence is not one. A `/mx:to-tickets` breakdown carries the ruling on the design alone, so its build tickets are `proposed` and each is ruled on from what it built (`/mx:to-tickets`).
- The ruling is made on the ticket's review page and the demo of what it built, or as a line in chat; the ticket's text is there to read whenever the user wants it and they never have to. Until the ruling, the build waits on its own ticket branch: nothing merges into the feature branch (the integration branch, for a standalone ticket) before the user has ruled, and a ticket that is built but not ruled on is not `done` and unblocks nothing. Four outcomes: **accept** merges the branch, `status: done`; **amend** sends the user's comments to the worker, which revises on the same branch and comes back for a ruling; **redo** discards the build and keeps the ticket, `git branch -D` and `status: open` with the reason under its Comments, for a fresh worker; **reject** deletes the ticket file and the build, `git branch -D`, the reason in the commit message (a reason the next feature must know goes where rules live: an ADR, the project's CLAUDE.md, the tool's config). A ruling that arrives before the build instead writes `open` (the provenance line stays), or sends the ticket to grilling (`type: grilling`, then open).
- A cross-feature blocker is written qualified: `blocked-by: [01, other-feature/03]`; a standalone ticket is referenced by its slug. Blocking names a ticket, never a whole feature. A reference whose file no longer exists counts as `done`, a deleted proposal included, so a rejection unblocks what waited on it; feature dirs are retired only after shipping.
- A ticket is **unblocked** when every ticket in `blocked-by` is `done`, which a speculative build is not until the user accepts it: a dependent never builds on a guess.
- `diff` accumulates one range per round: the implementation, then one per review round. SHAs, never branch names: a ticket branch is deleted once it lands while its commits survive. It is what regenerates the ticket's review page, which renders one section per range. That page lives at `agent/diffviews/<feature>/<NN>-<slug>.html`, or `agent/diffviews/<slug>.html` for a standalone ticket; gitignored, and the board links it from there.
- The **frontier**: unblocked, unclaimed tickets that are open or proposed, i.e. what can be started right now; first by number wins.
- A decision ticket resolves by appending the answer under a `## Answer` heading and setting `status: done`.
- `claimed` marks a ticket a session is actively working. Set it before any work. When agents run in parallel, a single orchestrating agent oversees them and is the sole claim-writer; no cross-checkout coordination needed. (With a single agent in a single checkout, claiming is optional.)
- Notes and follow-up conversation append under a `## Comments` heading at the bottom of the file.

## Publish / fetch

- "Publish to the issue tracker" → create the files above (creating the feature directory if needed).
- "Fetch the ticket" → read the ticket file **and** the feature's `spec.md`; tickets don't repeat the feature context, the spec carries it. Then render the board (below).

## Board

The board is the tracker as one page, `agent/board.html` beside it (gitignored, like `agent/diffviews/`): the tickets by state, the needs-human queue first, with the dependency graph beside them. `board`, run from anywhere in the repo, renders it, opens the tab and keeps it current until Ctrl-C; its `--help` says what the page shows, what it reads and which checkout's copy.

The human runs `board`; the tab then follows every tracker change on its own. A session renders once, without opening a tab, after it changes tracker state (`board --no-watch --no-open`), so the page on disk is current for whoever opens it next.

## Supersede

A superseded file (`/mx:tracker`, Supersede) is either **tombstoned** (one line at the very top: `> Historical artifact as of <date>, superseded by <successor>. Not current; kept as the reasoning trail.`) or, when it has no remaining reader value, **deleted**; git history keeps it.

## Retire

Set `status: done` when a ticket completes. Retire the files once the work has shipped, and take the show directory of what is retired (`/mx:show`) in the same commit, so no figure or demo outlives the design it drew:

- **Standalone ticket**: `git rm agent/tickets/<slug>.md`, with `agent/show/<slug>/` in the same command where the ticket built one (a decision ticket has none), as its own commit once its build has merged into the integration branch. The work arrives as a `--no-ff` merge of its ticket branch and `dispatch review` writes the ticket's range after that, so no commit of the work is left to carry the removal.
- **Feature**: `git rm -r agent/tickets/<feature-slug>/ agent/show/<feature-slug>/`, once the whole feature has shipped and every proposed ticket in it is ruled; an opened one that outlives the feature moves to a standalone ticket first.
- **Loose branch**: `git rm -r agent/show/<branch>/` on the branch itself, so the merge that lands the work carries the removal; there is no ticket beside it to retire.

The renders beside the figure sources are untracked (`agent/show/**/*.png`), so `git rm -r` leaves the directory standing with them inside: `rm -rf` what it leaves.

The research notes (`agent/research/`) the retired tickets cite leave the tree in the same step. Untracked, they are moved rather than deleted: `mkdir -p ~/logs/agent-research/<repo>/ && mv agent/research/<NN>-<slug>.md ~/logs/agent-research/<repo>/`, where the backups reach them and a later session reading the repo does not.

What a README, a PR or the build still needs is promoted in the same commit and kept current where it lands (`/mx:show`): a figure as a render, a demo's output as a code block, and with either the source and the script that regenerate it. Every reference into the removed directory is repointed in that commit. Where the promotion is to leave a source where it already sits, the commit keeps that directory and says in its message what it kept and what still reads it.

Git history preserves what it tracked: `git log --diff-filter=D -- agent/tickets agent/show` finds retired work. When the repo doesn't track `agent/tickets/`, git has nothing to recover from: move the file into `agent/tickets/done/` instead.
