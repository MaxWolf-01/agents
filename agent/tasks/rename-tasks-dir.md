---
status: done
type: grilling
---

# Rename agent/tasks/ to match the ticket vocabulary

## Question

The skills say "ticket" and "spec" everywhere; the directory that holds them is `agent/tasks/`, and the standalone file is called a "task", which is also one of the four decision-ticket types. Is the directory renamed (`agent/tickets/`, `agent/tracker/`, or another name), or does "task" stay as the file-level word and the directory keeps its name? A rename touches every skill, `dispatch-ctl`, `dashboard.py`, the diffviews mirror, and every project already carrying `agent/tasks/`.

## Answer

The directory becomes `agent/tickets/`, and "task" stops being the name of any artefact. One word per thing, across every skill, script and README:

| Thing | Word |
|---|---|
| the unit file | ticket; a build ticket (no type) or a decision ticket (typed) |
| the directory | `agent/tickets/` |
| a spec with its tickets | feature, `agent/tickets/<feature>/`; a wayfinder effort is a feature from its map on |
| the design doc | spec |
| the pre-spec plan | map |
| a single file with no spec | standalone ticket |
| the decision-ticket type for manual work that unblocks a decision | `legwork` (was `task`) |
| the text a session hands a subagent | brief; the word means nothing else |
| task | plain English only ("the task at hand", background tasks) |

Why not the alternatives: `tracker/` names the tool that reads the directory, not its contents; `issues/` would pull the skills toward GitHub's word after they deliberately abstract over it. `blocker` for the type fails because every ticket in the DAG blocks something. "effort" is dropped because the wayfinder skill already places the map "where the feature's spec will later land".

Scope of the change: `mx/skills/**` (tracker, orient, dispatch, grilling, wayfinder, handoff, and the `brief`/`effort`/`standalone task` usages elsewhere), `dispatch`, `dispatch-ctl`, `dashboard.py` (with a fallback to `tasks/` so unmigrated projects keep working), `mx/README.md`, the `agent/diffviews/` mirror path, and one `git mv agent/tasks agent/tickets` per project that carries the directory, updating only load-bearing references there (CLAUDE.md, scripts), not stale documents.

## Comments

Raised by max in the review of the decision-ticket change (agent/show/decision-tickets/), 2026-09-07: "a bit annoying that the dir is called tasks when we say tickets everywhere". Not decided.

Decided by max with the agent in chat, 2026-09-07: every row of the table above ratified item by item.
