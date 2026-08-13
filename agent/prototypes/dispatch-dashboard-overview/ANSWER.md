# Dispatch dashboard overview — what makes the board übersichtlich?

**Question.** The dispatch dashboard (mx/skills/dispatch/dashboard.py) rendered a real 56-ticket
feature (skilltree v0-core-loop, 48 done) as an unreadable hairball: a 57-node mermaid flowchart
with curved dagre edges, and a flat table dominated by done rows. What overview treatment reads
at a glance late in a feature, when done tickets vastly outnumber live ones?

**Tried.** `dashboard_proto.py` (this dir) renders three overview variants on the real data,
switchable via `?variant=` and a floating bar:

- **a — full graph**: all tickets, ELK orthogonal layout, done nodes ghosted (dashed, muted)
- **b — frontier graph**: only undone tickets plus their direct done blockers as ghosts (57 → 12 nodes)
- **c — wave lanes**: no graph; remaining tickets grouped by topological depth
  ("now: in flight / ready" → "wave +1" → …), deps as chips

Shared across variants (requested by Max mid-session, not under test): ticket rows are
`<details>` expanding to the rendered markdown body; done tickets collapse into one fold;
graph nodes, header-strip cells, and dep chips anchor-link to the ticket row and auto-expand it.

**Verdicts (Max):**

- Keep **all three** overview views, cycleable in one page — each answers a different question
  (full = history/context, frontier = what blocks what now, lanes = what runs next).
- **Frontier opens by default** — the dispatch-time question is the frontier, and pruning done
  nodes does far more for readability than edge routing alone (variant a stayed a wall even with
  orthogonal ELK edges and ghosting).

**Proposals folded in without explicit verdict** (labeled as mine): needs-human queue moved above
the ticket list (most actionable section first); active tickets sorted claimed → open → blocked;
auto-refresh switched from `<meta http-equiv=refresh>` to a JS reload that saves/restores view
state in sessionStorage, because a meta refresh collapses every open `<details>` and resets the
view every 30 seconds.

Ported into `mx/skills/dispatch/dashboard.py` (2026-08-14).
