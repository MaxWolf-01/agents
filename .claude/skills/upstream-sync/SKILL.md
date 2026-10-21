---
name: upstream-sync
description: Review what the upstreams mx adapts skills from (mattpocock/skills, Cursor's pstack) changed since their recorded baselines, and adopt what fits. Use when the user asks to check, sync, or adopt upstream skill changes.
---

# Sync with the upstreams

Each upstream below has a **baseline**, the last upstream commit reviewed. Every sync of an upstream ends by moving its baseline line forward; that line is the single source of truth for where we left off.

## Process

1. **Clone fresh** the upstream's repo into `/var/tmp` (full history; the baseline may be far back).
2. **Walk the log**: `git log <baseline>..HEAD` over the upstream's path, then classify every commit as touching a mapped skill (its section below), a new upstream skill (note each with one line), or noise (changesets, plugin manifests, docs site, README). Done when every commit is classified.
3. **Read before judging**: for each substantive change, read the full diff *and* the commit message; the author's reasoning lives in the message body. Then read the current mx version, `PRINCIPLES.md` at the repo root, and the rejections recorded in earlier baseline bumps (`git log --grep='move baseline'`, older ones under `pocock-sync`). An upstream move either already answers is still presented, with that answer quoted beside it: the new version may add a nuance the answer lacks, and that is judged in the same per-item presentation as everything else. The mx skills are adaptations, not copies: a line upstream deletes as redundant may be load-bearing in mx, and upstream vocabulary translates (each upstream's section says how).
4. **Present before editing**: one section per affected skill with a table quoting actual lines (current mx text vs proposed text) plus the author's reasoning and your recommendation (adopt / adapt / skip, and why). The user decides per item; a go-ahead on one item doesn't cover the rest.
5. **Apply what's approved**, adapted to mx conventions, one commit per skill citing the upstream hash. Record deliberate rejections in the baseline-bump commit message (`upstream-sync: move <upstream> baseline to <hash>`) so the next sync doesn't re-propose them.
6. **Move the baseline**: update the upstream's Baseline line to the HEAD you reviewed, and commit it. Done when every synced upstream's recorded hash equals its reviewed HEAD.

## mattpocock/skills

`https://github.com/mattpocock/skills`, the whole repo. **Baseline**: `24fe0ef` (2026-10-04, v1.3.1).

Vocabulary: `.scratch/` → `agent/`, `/skill` → `/mx:skill`, `docs/adr/` → `decisions/`, GitHub issues → the mx `tracker` conventions; to-tickets' routing to `/mx:dispatch` is an example of a line that is load-bearing in mx alone. Changes to `agents/openai.yaml` are noise.

### Mapping (mx ← upstream)

Same-named: grilling, code-review, codebase-design, diagnosing-bugs, improve-codebase-architecture, prototype, research, handoff, wait-what, to-questionnaire, wizard, writing-for-agents.

Dissolved:
- implement → the worker contract in `mx/skills/dispatch/worker-prompt.md`, which every ticket worker starts with; upstream changes to implement's process map onto that prompt, its review hand-off onto code-review.
- grill-with-docs → grilling, which runs with `/mx:domain-modelling` in a repo; upstream changes to grill-with-docs map onto grilling's rounds, its docs side onto domain-modelling.
- to-spec → grilling writes the design into the ticket round by round; upstream changes to to-spec's design sections map onto `mx/skills/grilling/DESIGN.md`, to its frontmatter or section order onto `mx/skills/tracker/SKILL.md`'s The ticket file, and to its process onto grilling's rounds.
- to-tickets → cutting a ticket into child tickets, `mx/skills/tracker/SLICING.md`; upstream changes to its slicing rules map there.
- wayfinder → grilling spans sessions through child tickets the user is in the loop for; upstream changes to wayfinder's map body map onto `mx/skills/tracker/SKILL.md`'s The ticket file for the shape and `mx/skills/grilling/DESIGN.md` for the design sections, to its charting or work-through process onto grilling's Across sessions. Its ticket types map onto nothing: mx has one kind of ticket.

Renamed:
- testing ← tdd (red-green is no longer the frame: upstream changes to tdd's loop map onto diagnosing-bugs' regression test, its test-quality material onto `code-review/TEST-SMELLS.md`)
- orient ← ask-matt
- domain-modelling ← domain-modeling
- tracker ← the one-file-per-ticket local tracker conventions (upstream folded these into setup-matt-pocock-skills)

Everything else upstream is unadopted; flag interesting new skills, don't auto-adopt them.

## Cursor's pstack

`https://github.com/cursor/plugins`, the path `pstack/` alone (MIT, Lauren Tan). **Baseline**: `d1715e0` (2026-10-17), the commit session cfabdcfe and aaa2fc5b read pstack at.

Vocabulary: a playbook of `/poteto-mode` → an mx skill or flow (`/mx:orient` routes); a `principle-*` skill → an mx skill or a line of `PRINCIPLES.md`; Cursor's subagents and model roles → `/mx:dispatch` and the Agent tool.

### Mapping (mx ← upstream)

Copied, then fitted to mx (the byte copy is the commit before the fitting, for a diff against upstream):
- benchmark-checklist ← benchmark-checklist
- attack-the-premise ← principle-attack-the-premise

Adapted into existing mx skills:
- sharpen ← sharpen (plus `/mx:expert`'s re-derivation and the premise check of the retired `wf` line)
- improve-codebase-architecture's scan ← correct and architect's agent-contributor test, and Comment Sicko's surprise-explaining comment
- retro (What is already written, the Watched list, corrections read for their cause) ← reflect's synthesizer criteria and correct
- PRINCIPLES.md #1 ← the inverse pyramid of poteto's post

Considered and not adopted, with max's reasons, in sessions cfabdcfe and aaa2fc5b's pages: their lists D1 to D17. Everything else upstream is unadopted; flag interesting new skills, don't auto-adopt them.

Everything in mx not mapped under either upstream is homegrown.
