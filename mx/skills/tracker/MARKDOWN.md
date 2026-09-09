# The markdown tracker

Tickets live as markdown files in `agent/tickets/`.

## Layout

- **Feature**: one directory per feature, `agent/tickets/<feature-slug>/`
  - `spec.md`: the work order for the whole feature, written round by round by `/mx:grilling`; frontmatter `status: draft | confirmed`, and a draft is never read as settled truth
  - `NN-<slug>.md`: tickets, build and decision alike (`/mx:tracker`, Decision tickets), numbered from `01`; written by `/mx:to-tickets`, or by any session that files a question. A feature built in the session that grilled it has none
- **Standalone ticket**: a single file `agent/tickets/<slug>.md`, no spec: a build ticket for work that needs no design round, or a decision ticket filed for later. One that gets grilled is absorbed into its feature directory (see `/mx:grilling`).
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

- `proposed` is the status of a ticket an agent filed that the user has not yet ruled worth doing: an orchestrator's reading of a worker's friction or a harden line, a review session's finding too large to fix there, a punt. It is off the frontier, and dispatch's `claim` refuses it. Its body opens with one line of provenance: what it was cut from (which closing comment, harden line or review finding) and why it is worth a ticket. Only a **ruling** by the user writes `open`; a ticket the user asked for in conversation, a grilling's decision tickets and a to-tickets breakdown are rulings already, and silence is not one. A ruling arrives as a review comment on the ticket file or a line in chat, and the session flips the file: it opens the ticket (the provenance line stays), deletes it (the commit message carries the reason; a reason the next feature must know goes where rules live: an ADR, the project's CLAUDE.md, the tool's config), or sends it to grilling (`type: grilling`, then open).
- A cross-feature blocker is written qualified: `blocked-by: [01, other-feature/03]`; a standalone ticket is referenced by its slug. Blocking names a ticket, never a whole feature. A reference whose file no longer exists counts as `done`, a deleted proposal included, so a rejection unblocks what waited on it; feature dirs are retired only after shipping.
- A ticket is **unblocked** when every ticket in `blocked-by` is `done`.
- `diff` accumulates one range per round: the implementation, then one per review round. SHAs, never branch names: a ticket branch is deleted once it lands while its commits survive. It is what regenerates the ticket's review page, which renders one section per range. That page lives at `agent/diffviews/<feature>/<NN>-<slug>.html`, or `agent/diffviews/<slug>.html` for a standalone ticket; gitignored, and the board links it from there.
- The **frontier**: open, unblocked, unclaimed tickets, i.e. what can be started right now; first by number wins. A proposed ticket is not open, whatever blocks it.
- A decision ticket resolves by appending the answer under a `## Answer` heading and setting `status: done`.
- `claimed` marks a ticket a session is actively working. Set it before any work. When agents run in parallel, a single orchestrating agent oversees them and is the sole claim-writer; no cross-checkout coordination needed. (With a single agent in a single checkout, claiming is optional.)
- Notes and follow-up conversation append under a `## Comments` heading at the bottom of the file.

## Publish / fetch

- "Publish to the issue tracker" → create the files above (creating the feature directory if needed).
- "Fetch the ticket" → read the ticket file **and** the feature's `spec.md`; tickets don't repeat the feature context, the spec carries it. Then render the board (below).

## Board

The board is the tracker as one page, `agent/board.html` beside it (gitignored, like `agent/diffviews/`): every feature with its spec status, dependency graph and ticket rows, the standalone tickets, the needs-human queue, the review-page links; proposed tickets sit in every view as ordinary nodes and rows in their own colour, so they are triaged from the graph. `board`, run from anywhere in the repo, renders it, opens the tab and keeps it current until Ctrl-C; its `--help` says what it reads and which checkout's copy it shows.

The human runs `board`; the tab then follows every tracker change on its own. A session renders once, without opening a tab, after it changes tracker state (`board --no-watch --no-open`), so the page on disk is current for whoever opens it next.

## Supersede

A superseded file (`/mx:tracker`, Supersede) is either **tombstoned** (one line at the very top: `> Historical artifact as of <date>, superseded by <successor>. Not current; kept as the reasoning trail.`) or, when it has no remaining reader value, **deleted**; git history keeps it.

## Retire

Set `status: done` when a ticket completes. Retire the files once the work has shipped:

- **Standalone ticket**: `git rm agent/tickets/<slug>.md`, in the same commit as the work it describes.
- **Feature**: `git rm -r agent/tickets/<feature-slug>/`, once the whole feature has shipped and every proposed ticket in it is ruled; an opened one that outlives the feature moves to a standalone ticket first.

Git history preserves both: `git log --diff-filter=D -- agent/tickets` finds retired work. When the repo doesn't track `agent/tickets/`, git has nothing to recover from: move the file into `agent/tickets/done/` instead.
