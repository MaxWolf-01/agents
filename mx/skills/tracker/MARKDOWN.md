# Tracker backend: local markdown

Issues for this repo live as markdown files in `agent/tasks/`.

## Layout

- **Feature**: one directory per feature, `agent/tasks/<feature-slug>/`
  - `spec.md` — the work order for the whole feature (written by `/mx:to-spec`)
  - `NN-<slug>.md` — tickets, numbered from `01` (written by `/mx:to-tickets`)
- **Small standalone task**: a single file `agent/tasks/<slug>.md` — ticket-shaped, no spec needed
- **Numbering**: `NN` is an id, unique within its directory. Assign the next one by scanning the directory for the highest existing number and incrementing — never from an in-context picture of the board, which parallel sessions leave stale.

## Ticket state

Frontmatter:

```yaml
status: open | claimed | done
blocked-by: [01, 02] # ticket numbers within the feature; omit when nothing blocks it
```

- A ticket is **unblocked** when every ticket in `blocked-by` is `done`.
- The **frontier**: open, unblocked, unclaimed tickets — what can be started right now.
- `claimed` marks a ticket a session is actively working. Set it before any work. When agents run in parallel, a single orchestrating agent oversees them and is the sole claim-writer — no cross-checkout coordination needed. (With a single agent in a single checkout, claiming is optional.)
- Notes and follow-up conversation append under a `## Comments` heading at the bottom of the file.

## Publish / fetch

- "Publish to the issue tracker" → create the files above (creating the feature directory if needed).
- "Fetch the ticket" → read the ticket file **and** the feature's `spec.md` — tickets don't repeat the feature context, the spec carries it.

## Supersede

When a newer artefact replaces an older one — a spec supersedes a map, a new spec replaces the old — never leave the old file looking live: agents read whatever exists as current truth. Either **tombstone** it (one line at the very top: `> Historical artifact as of <date> — superseded by <successor>. Not current; kept as the reasoning trail.`) or, when it has no remaining reader value, **delete** it — git history keeps it. A real tracker expresses this natively (closed state + cross-reference).

The same duty applies partially: a resolved decision that contradicts a live spec includes the **spec sweep** — rewrite the affected spec sections in the same session, or file a ticket for the sweep with a blocking edge. A spec left teaching a superseded design is current truth to every later reader.

## Retire

Set `status: done` when a ticket completes. When the whole feature has shipped, `git rm -r agent/tasks/<feature-slug>/` — git history preserves it (`git log --diff-filter=D -- agent/tasks` finds retired work). If the repo doesn't track `agent/tasks/`, plain delete.

## Wayfinding operations

Used by `/mx:wayfinder`. An effort's map lives where the feature's spec will later land:

- **Map**: `agent/tasks/<effort>/map.md` — the Destination / Notes / Decisions-so-far / Not-yet-specified / Out-of-scope body.
- **Decision ticket**: `agent/tasks/<effort>/questions/NN-<slug>.md`, numbered from `01`, body `## Question`. Frontmatter: `status` and `blocked-by` as above, plus `type: research | prototype | grilling | task`.
- **Resolve**: append the answer under an `## Answer` heading, set `status: done`, and add a one-line pointer (gist + link) to the map's Decisions so far.
- **Frontier**: scan `questions/` for open, unblocked, unclaimed tickets; first by number wins.
- When the map is done, `/mx:to-spec` writes `spec.md` beside it, **tombstones the map** (see Supersede), and build tickets land in the feature dir root per the layout above. Retire the whole effort directory when the feature ships — the decision trail stays readable until then.
