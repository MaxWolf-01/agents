# mx — Agent Workflow Plugin

File-based specs and tickets, domain glossary + ADRs, research artefacts, and session continuity for multi-session work.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/full-cycle.png">
  <img alt="The full mx cycle: sharpen the idea, spec, tickets, build the frontier, drive each landed slice, review session — with feedback rails returning new tickets, reopened decisions, and new ideas, over the durable docs" src="assets/full-cycle-light.png">
</picture>

## Artefacts

| Object     | Location                           | Lifecycle                           | Content                                             |
| ---------- | ---------------------------------- | ----------------------------------- | ---------------------------------------------------- |
| Glossary   | `CONTEXT.md` (repo root)           | durable, edited in place            | domain terminology — opinionated, with avoid-lists   |
| ADR        | `decisions/NNNN-slug.md`           | durable, append-only                | one hard-to-reverse decision and why                  |
| Spec       | `agent/tasks/<feature>/spec.md`    | committed; `git rm -r` when shipped | the work order for one feature                        |
| Ticket     | `agent/tasks/<feature>/NN-slug.md` | retired with its feature            | one vertical slice with blocked-by edges              |
| Small task | `agent/tasks/<slug>.md`            | deleted when done                   | ticket-shaped, no spec                                |
| Map        | `agent/tasks/<effort>/map.md` + `questions/` | retired when the effort ships | wayfinder effort: destination, decisions-so-far, fog |
| Research   | `agent/research/NN-slug.md`        | gitignored, ephemeral               | one question, cited findings                          |
| Prototype  | `agent/prototypes/<slug>/`         | committed, kept                     | code that answered a design question + `ANSWER.md`    |
| Show       | `agent/show/<slug>/`               | committed once approved             | an explanation carried by an artefact                 |

`/mx:tracker` defines the file conventions (status, blocked-by, frontier, claiming); a repo can override them (e.g. GitHub Issues) in its CLAUDE.md.

## The main flow: idea → ship

`/mx:grill-with-docs` (relentless interview; glossary terms and ADRs land as residue) → `/mx:to-spec` (thread → work order) → `/mx:to-tickets` (tracer-bullet vertical slices with blocking edges) → `/mx:implement` per ticket (tdd inside, code-review at the end), fresh context each.

**`/mx:orient` is the map** — the main flow, its on-ramps, and when to reach for what.

When the planning itself is too big for one session, `/mx:wayfinder` charts it as a shared map of decision tickets, resolved one fresh session at a time:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/wayfinder-loop.png">
  <img alt="The wayfinder loop: chart the map, then per session pick and claim a decision ticket, resolve it, record it on the map, graduate the fog — until the frontier is empty and the spec supersedes the map" src="assets/wayfinder-loop-light.png">
</picture>

## What's manual, what's AFK — and why

- **Grilling is where alignment happens** — human in the loop, non-negotiable. Everything downstream trades on the shared understanding built there. External inputs (a meeting transcript, a client brief, a bug report) enter the flow here: grill through their unstated assumptions.
- **Plan in one window, respect the smart zone.** Grilling → spec → tickets stays in one unbroken context window; but reasoning degrades noticeably from roughly 30% of the window used, regardless of advertised size. Approaching the limit mid-planning → handoff to a fresh thread, don't push on degraded.
- **Don't review the spec — when you were there.** After a real grilling session the spec is a summary of an understanding you already share — reading it only verifies the LLM's ability to summarize. A spec *compiled from artifacts* (a wayfinder map, an external brief) is a translation, and translations drift: review that one line by line.
- **Do review the ticket breakdown** (to-tickets quizzes you). Cheap to check, and the failure mode is easy to spot: horizontal slices (all schema, then all API, then all UI) instead of vertical ones — no feedback until the layers meet.
- **Implementation is the AFK part.** Day shift plans and queues the backlog; night shift works the frontier, fresh context per ticket.
- **QA is where you impose taste — per landed slice.** Manual, deliberately: automate the idea, the planning, *and* the QA and you get slop. Every ticket is a tracer bullet, demoable the moment it lands; the agent announces what works and how to exercise it (the ticket's What-to-build + acceptance criteria), you drive it while the remaining frontier keeps running. Findings become new tickets with blocking edges; the board absorbs them.
- **Reviews run in fresh context.** A reviewer sharing the implementer's window reviews in the dumb zone; implement closes with code-review in clean context for a reason.
- **Feedback loops are the ceiling.** Agent output quality tracks the quality of the repo's tests and typechecks. Bad output → improve the loops, not the prompt (`/mx:improve-codebase-architecture`; deep modules — design the interface, delegate the implementation).
- **Done work gets deleted** (`git rm`). Closed tickets and specs left in the tree are doc rot steering future agents wrong; git history keeps them.

## Skills & commands

| | |
| --- | --- |
| `/mx:orient` | the router — start here |
| `/mx:grill-with-docs`, `/mx:grilling` | sharpen a plan by interview |
| `/mx:domain-modelling`, `/mx:codebase-design` | vocabulary layers: domain language + ADRs, deep-module design |
| `/mx:to-spec`, `/mx:to-tickets` | conversation → spec → tickets |
| `/mx:implement`, `/mx:tdd`, `/mx:code-review` | work a ticket; test-first; three-axis review |
| `/mx:dispatch` | parallelize independent frontier tickets — one orchestrator, N implements |
| `/mx:prototype` | throwaway code to answer a design question |
| `/mx:to-questionnaire` | turn a decision someone else must answer into a questionnaire for them |
| `/mx:wizard` | bash wizard walking a human through steps only they can do (credentials, dashboards, migrations) |
| `/mx:wait-what` | that didn't land — re-pitch it in plain language |
| `/mx:show` | show, don't tell — explain via artifact (diagram, comparison, demo, explainer page, …) |
| `/mx:fork` | delegate to an agent that inherits the full conversation |
| `/mx:diagnosing-bugs` | tight-loop debugging for hard bugs |
| `/mx:improve-codebase-architecture`, `/mx:bloat-audit` | codebase health |
| `/mx:research` | primary-source investigation → cited artefact |
| `/mx:codex` | second opinion from a different model |
| `/mx:handoff`, `/mx:transcript`, `/mx:recap`, `/mx:todos`, `/mx:reflect` | session continuity & status |
| `/mx:writing-for-agents`, `/mx:writing-for-humans` | the writing references: documents that instruct agents (skills, CLAUDE.md, specs, tickets) / artifact text read cold (docs, comments, UI copy) |

Plus assorted utilities: `tmux`, `mermaid`, `tyro-cli`, `uv-script`, `project-setup`, `session-name`, `restore-sessions`, `permissions-review`, `review-pr`, `pr-tldr`, `overview`, `changelog`, `dependabot-triage`.

---

**Local development:**

```bash
rm -rf ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
ln -s /path/to/mx ~/.claude/plugins/cache/MaxWolf-01/mx/0.1.0
```

`claude plugin update mx@MaxWolf-01` replaces the symlink.
