# The markdown tracker

Tickets live as markdown files in `agent/tickets/`.

## Layout

- **Feature**: one directory per feature, `agent/tickets/<feature-slug>/`
  - `spec.md`: the work order for the whole feature, written round by round by `/mx:grilling`; frontmatter `status: draft | confirmed`, and a draft is never read as settled truth
  - `NN-<slug>.md`: tickets, build and decision alike (`/mx:tracker`, Decision tickets), numbered from `01`; written by `/mx:to-tickets`, or by any session that files a question. Every feature has at least one
- **Standalone ticket**: a single file `agent/tickets/<slug>.md`, no spec: a build ticket for work that needs no design round, or a decision ticket filed for later. It is committed on the tracker repo's integration branch from the main checkout, the one file a session writes outside its worktree: every session and the board read standalone tickets from there, while a feature's own tickets ride the feature branch; one filed on a branch anyway shows on the board tagged with that branch until it is moved. One that gets grilled is absorbed into its feature directory (see `/mx:grilling`). It is dispatched like a feature's ticket (`/mx:dispatch`).
- **One tracker directory.** A project whose tracker sits at `agent/tasks/` is moved before anything is filed: `git mv agent/tasks agent/tickets`, as its own commit, repointing the project's own references (CLAUDE.md, scripts).
- **Numbering**: `NN` is an id, unique within its directory. Assign the next one by scanning the directory for the highest existing number and incrementing, never from an in-context picture of the board, which parallel sessions leave stale.

## The ticket file

All of a ticket's metadata is frontmatter; its body is the H1, the brief, what to build, and the sections below.

```yaml
status: proposed | open | claimed | review | done
priority: 1 # 1 now, 2 next, 3 soon, 4 later, 5 someday
size: M # XS | S | M | L | XL, the user's own time on the ticket
type: grilling # research | prototype | grilling | legwork on a decision ticket; omit on a build ticket
blocked-by: [01, 02] # ticket numbers within the feature, qualified <feature>/NN, or a standalone ticket's slug; omit when nothing blocks it
diff: [4f2a91c..8b3ce07] # commit ranges implementing the ticket; omit until the first lands
gh: [owner/repo#317, owner/other-repo#412] # the pull requests and issues the ticket produced or tracks, as owner/repo#number, in any number of repositories; omit when there are none
```

**Priority** is the agent's reading of how soon the ticket matters to the user, set from what they have said and changed when they say so; ranking tickets is never their chore. **Size** is the user's time on the ticket and never the agent's: reading it, trying the demo, deciding, learning. XS is under 15 minutes, S about 20, M about an hour, L half a day, XL several sessions. Both are filled at filing, by whoever files the ticket.

**The H1 is the ticket's short name**, the few words a board row shows; the sentence a title would carry goes in the brief instead.

**`## Brief`** sits right under the H1: two or three sentences written cold for the user, what the ticket is and why it matters. `/mx:to-tickets` writes it for a slice, the filing session for a standalone ticket, the orchestrator for a proposal.

**`## Questions`** holds the calls only the user can make, on the ticket they belong to. One item each, tagged with the ticket's running `Dn` sequence (continued from the highest tag the file already carries, so a tag names one thing for good), a bold headline and its detail:

```markdown
## Questions

- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing.
- [D2] **Keep the test in the fast suite?** It takes four seconds either way.
  - Ruled 2026-09-21: keep it in the fast suite.
```

A question is open, and shows on the board's needs-me group, until a `Ruled <date>:` line sits under it; the session that relays the user's answer writes that line, in the tracker's own copy of the ticket, whatever branch the question was asked on. Every question belongs to a ticket: one with no ticket to hang on is filed as a proposed ticket, and the ruling on that proposal is the answer. A question the ruling on a build leaves open is filed as a proposed ticket then, so a done ticket carries none. A decision ticket states what it is asking here too, which is what shows it under its row, and records the answer under `## Answer` (Ticket state).

**`## Comments`** at the bottom takes notes and follow-up conversation, a worker's closing comment included.

## Ticket state

- `proposed` is the status of a ticket an agent filed that the user has not yet ruled on: an orchestrator's reading of a worker's friction or a harden line, a review session's finding too large to fix there, a punt. It is on the frontier and `claim` takes it like an open one, so what waits is the ruling and not the build: the user rules on the artifact the build produced. Its body opens with one line of provenance: what it was cut from (which closing comment, harden line, review finding, or the spec whose slice it is) and why it is worth a ticket. `open` is the status of a ticket already **ruled** and not yet built; a ticket the user asked for in conversation and a grilling's decision tickets are rulings already, and silence is not one. A `/mx:to-tickets` breakdown carries the ruling on the design alone, so its build tickets are `proposed` and each is ruled on from what it built (`/mx:to-tickets`).
- `review` is the status of a ticket whose work is finished and waits for the user's ruling: a build, on its own ticket branch (the worker's last act there, and the orchestrator's flip on the feature branch when it renders the review page, `/mx:dispatch`), or a decision ticket's answer no human was in the loop for. The board lists these in its **needs-me group**. `done` is the accept and nothing less.
- The ruling is made on the ticket's review page and the demo of what it built, or as a line in chat; the ticket's text is there to read whenever the user wants it and they never have to. Nothing merges into the feature branch (the integration branch, for a standalone ticket) before the user has ruled. Four outcomes: **accept** merges the branch, `status: done`; **amend** sends the user's comments to the worker, which holds the ticket again (`claimed`), revises on the same branch and comes back for a ruling; **redo** discards the build and keeps the ticket, `git branch -D` and `status: open` with the reason under its Comments, for a fresh worker; **reject** deletes the ticket file and the build, `git branch -D`, the reason in the commit message (a reason the next feature must know goes where rules live: an ADR, the project's CLAUDE.md, the tool's config). A ruling that arrives before the build instead writes `open` (the provenance line stays), or sends the ticket to grilling (`type: grilling`, then open).
- A cross-feature blocker is written qualified: `blocked-by: [01, other-feature/03]`; a standalone ticket is referenced by its slug. Blocking names a ticket, never a whole feature. A reference whose file no longer exists counts as `done`, a deleted proposal included, so a rejection unblocks what waited on it; feature dirs are retired only after shipping.
- A ticket is **unblocked** when every ticket in `blocked-by` is `done`, which a ticket in `review` is not until the user accepts it: a dependent never builds on a guess.
- `diff` accumulates one range per round: the implementation, then one per review round. SHAs, never branch names: a ticket branch is deleted once it lands while its commits survive. It is what regenerates the ticket's review page, which renders one section per range. That page lives at `agent/diffviews/<feature>/<NN>-<slug>.html`, or `agent/diffviews/<slug>.html` for a standalone ticket; gitignored, and the board links it from there.
- The **frontier**: unblocked, unclaimed tickets that are open or proposed, i.e. what can be started right now; first by number wins.
- A decision ticket resolves by appending the answer under a `## Answer` heading: `status: done` when the user was in the loop (the HITL types, `/mx:tracker`); `status: review` when an agent answered it alone (research), and the user's accept of the answer, a line in chat with no branch to merge, is written as `status: done` by the session that relays it.
- `claimed` marks a ticket a session is actively working, a worker resumed to revise included. Set it before any work. When agents run in parallel, a single orchestrating agent oversees them and is the sole claim-writer; no cross-checkout coordination needed. (With a single agent in a single checkout, claiming is optional.)

## Publish / fetch

- "Publish to the issue tracker" → create the files above (creating the feature directory if needed).
- "Fetch the ticket" → read the ticket file **and** the feature's `spec.md`; tickets don't repeat the feature context, the spec carries it. Then render the board (below).

## Board

The board is the tracker as one page, `agent/board.html` beside it (gitignored, like `agent/diffviews/`): the tickets by state, the needs-me group first, with the board briefing and the dependency graph beside them. A ticket is in the needs-me group when it is not done and is a build in review, has an open question, or is a design or prototype decision at p1 or p2 that nobody has claimed. The briefing is a `claude -p` session's account of where things stand and what to take up next, which a watching board keeps current. `board`, run from anywhere in the repo, renders it, opens the tab and keeps it current until Ctrl-C; its `--help` says what the page shows, what it reads and which checkout's copy.

The human runs `board`; the tab then follows every tracker change on its own. A session renders once, without opening a tab, after it changes tracker state (`board --no-watch --no-open`), so the page on disk is current for whoever opens it next.

## Supersede

A superseded file (`/mx:tracker`, Supersede) is either **tombstoned** (one line at the very top: `> Historical artifact as of <date>, superseded by <successor>. Not current; kept as the reasoning trail.`) or, when it has no remaining reader value, **deleted**; git history keeps it.

## Retire

A ticket is `done` once the user's accept merged it. Retire the files once the work has shipped:

- **Standalone ticket**: `git rm agent/tickets/<slug>.md`, as its own commit once its build has merged into the integration branch. The work arrives as a `--no-ff` merge of its ticket branch and `dispatch review` writes `done` and the ticket's range after that, so no commit of the work is left to carry the removal.
- **Feature**: `git rm -r agent/tickets/<feature-slug>/`, once the whole feature has shipped and every proposed ticket in it is ruled; an opened one that outlives the feature moves to a standalone ticket first.

Git history preserves both: `git log --diff-filter=D -- agent/tickets` finds retired work. When the repo doesn't track `agent/tickets/`, git has nothing to recover from: move the file into `agent/tickets/done/` instead.
