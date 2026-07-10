---
status: done
---

# dispatch — parallelize frontier tickets

## What to build

A model-invocable skill that works a feature's ticket DAG (the `blocked-by` edges) in parallel: fan independent frontier tickets out to parallel agents, integrate as tickets land, re-evaluate the frontier, repeat until the feature ships. "Delegate the delegation": an orchestrating agent can invoke it.

## Decisions so far

- **Always exactly one orchestrating agent.** It computes the frontier, claims tickets (sole claim-writer — no cross-checkout coordination protocols, that was YAGNI), spawns workers, and integrates. Multi-machine/uncoordinated parallelism is out of scope.
- **Downstream of to-tickets, not a general "parallelize any task" skill.** The DAG exists only after `/mx:to-tickets` — the blocked-by edges plus the quiz step make independence explicit and human-approved. An unticketed task with ≥2 independent parts routes through to-tickets first. Dispatch is a peer of implement: implement works one ticket, dispatch orchestrates N implements.
- **Git reconciliation: the feature branch is the integration branch.** Ticket branches are cut from it and merge back into it, never directly to main. Newly-unblocked tickets branch from the *updated* feature branch — a blocked ticket needs its blockers' code. Feature branch → PR → squash to main when the spec ships.
- **Integration: a ticket is `done` only when green on the feature branch.** Two candidate merge mechanics: (a) ticket agent rebases onto the current feature branch and re-runs tests before handing back, orchestrator merges + verifies (thin orchestrator, conflict work done by the agent with context for its own diff); (b) Matt's Sandcastle pattern — a dedicated **merger agent** takes the finished branches + issues and merges them, fixing type/test breakage itself (ticket agents just commit and exit; better when workers finish and vanish at different times). Leaning (b) for AFK waves, (a) when workers stay resumable (which tmux sessions are).
- **Orchestrator lifetime: a `/loop`-driven session, not a babysitting turn** (https://claude.com/blog/getting-started-with-loops). Each tick: check landed tickets, integrate, re-evaluate frontier, claim + spawn next wave; stop when no open tickets remain. Ticket agents can be wrapped in `/goal` where a deterministic stop exists.
- **Spawn mechanism: tmux + `claude -p`, one session per ticket** (candidates in `agent/research/01-dispatch-spawn-mechanism.md`). Decisive: orchestrator can resume prematurely-stopped sessions and interact with them; the human can attach directly. Dynamic workflows rejected (proprietary runtime, resumability dies with the session). Policy note: as of 2026-06-15 Anthropic *paused* splitting `claude -p` off subscription limits — currently draws from plan limits, but they've signaled revisiting; keep the spawn layer thin and swappable. Source: https://support.claude.com/en/articles/15036540
- **Worktrees for same-machine dispatch.** With a single orchestrator there's no coordination need pushing toward remote round-trips, so worktrees' instant creation + local merges win. Costs to respect: shared-.git blast radius, `.git`-file tooling quirks, one worktree per branch (orchestrator holds the feature branch), per-worktree env dirs (node_modules/venv — defer to first concrete project). Matt's Sandcastle combines worktree (cheap branch) + Docker container (execution isolation) — the hybrid to steal if blast radius bites. Global CLAUDE.md's "no worktrees" rule needs this carve-out when dispatch lands.
- **Collision assessment happens at dispatch time, not in to-tickets.** Sandcastle's planner step picks which frontier issues are safe to run in parallel — file overlap depends on the code as it stands at that moment, so assessing it when spawning a wave beats front-loading a quiz question that goes stale.
- **Model routing** (Sandcastle): cheaper model for implementers, strongest for review/merge judgment.
- **UI-ish tickets parallelize in implementation like any other slice** — only the HITL verification serializes (user attention, one browser at a time; per-instance port allocation and quick switching are per-project details to refine when concrete). Deterministic "green on feature branch" applies only where checks are automated; otherwise the ticket's done-check is the human QA pass.
- **QA runs concurrently and feeds the board** (Matt's flow): while agents implement, the human QAs landed slices and files new tickets with blocking edges — QA output is more tickets, not just verdicts. The board absorbs them; the orchestrator's frontier picks them up.

- **Worker permission mode: `--permission-mode auto`.** Auto-approves the safe middle (read-only, reversible, in-scope) without allowlist curation; in `-p` there's no one to prompt, so the residual risky calls get denied — and denials are a first-class resumable event: orchestrator spots a blocked worker, adds the allowlist entry or resumes with guidance. `bypassPermissions` only ever inside containers.
- **Done signal: frontmatter + verify green.** The contract: the worker's last act is setting `status: done` + committing. On process exit the orchestrator reads the ticket frontmatter — not done → resume with "continue". A `done` is accepted only after the orchestrator independently verifies tests green; the status flip alone proves nothing.
- **Integration: merge-if-clean, resume-on-conflict. No merger agent.** Orchestrator merges when clean; on conflict it resumes the ticket's worker session ("feature branch moved — rebase, resolve, re-verify"). Key argument: Sandcastle's merger agent isn't a considered choice over resumption — his Docker workers are ephemeral, so a merger was his *only* option; our tmux/`--resume` workers remove that constraint, so conflicts go to the most-informed agent. If a worker session is truly unrecoverable, no special machinery: reset the ticket to `open`, back onto the frontier, fresh worker — the ticket+spec carry all needed context by construction. Rebasing ticket branches is safe — they're private, nobody builds on them.

## Reference details from Matt's Ralph setup (once.sh / afk.sh)

- Worker prompt assembly: cat all open issue files + the last 5 commits into the prompt, run `claude` with `--permission-mode acceptEdits`.
- AFK priority order baked into the worker prompt: critical bug fixes > development infrastructure > tracer bullets > polish/quick wins/refactors.
- Stop condition: "if all AFK tasks are complete, output NO MORE TASKS" — a sentinel the outer loop greps for.

## Open questions

- None blocking — build-time details only (proposed defaults: tmux session `dispatch-<feature>-<NN>`; worktrees under a sibling dir of the checkout).

## Acceptance criteria

- [x] Design settled (2026-07-10 grilling: permissions=auto, done-signal=frontmatter+verify, integration=hybrid) — grow into a spec when building starts
- [x] Skill exists, model-invocable, referenced from orient's parallel-work line
- [x] Dispatch-time planner assesses parallel-safety (file overlap) of the wave
- [x] Global CLAUDE.md worktree rule gets the orchestrated-dispatch carve-out

## Comments

- 2026-07-10: idea from the mx restructure session.
- 2026-07-10: branching model + scope settled; spawn mechanism decided (tmux + `claude -p`); uncoordinated/multi-machine coordination trimmed as YAGNI (tracker/orient/to-tickets updated to the single-orchestrator assumption).
- 2026-07-10: built — mx/skills/dispatch/SKILL.md (no helper scripts; the orchestrator runs tmux/git itself), orient + to-tickets routing lines, README row, global CLAUDE.md carve-out. File left for the QA pass; retire (`git rm`) after review.
- 2026-07-10: incorporated Matt Pocock's workshop transcript (~/Documents/library/full-walkthrough-workflow-for-ai-coding-matt-pocock/) — Sandcastle pattern (planner → sandboxed implementers → reviewer → merger agent; worktree+Docker; model routing), collision assessment at dispatch time, QA-feeds-the-board. Also validates: deleting done PRDs/tickets (doc rot), review in fresh context, push-standards-to-reviewer / pull-for-implementer (already how the code-review copy works).
