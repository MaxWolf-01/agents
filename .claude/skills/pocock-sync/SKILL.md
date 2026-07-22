---
name: pocock-sync
description: Review upstream mattpocock/skills changes since the recorded baseline and adopt what fits the adapted mx skills. Use when the user asks to check, sync, or adopt Matt Pocock's latest skill changes.
---

# Sync with mattpocock/skills

**Baseline** — last upstream commit reviewed: `ed37663` (2026-07-21). Every sync ends by moving this line forward; it is the single source of truth for "where we left off".

## Process

1. **Clone fresh**: `git clone https://github.com/mattpocock/skills /tmp/mattpocock-skills` (full history — the baseline may be far back).
2. **Walk the log**: `git log <baseline>..HEAD` — classify every commit as either touching a mapped skill (below), a new upstream skill (including `in-progress/` — note each with one line), or noise (changesets, plugin manifests, `agents/openai.yaml`, docs site, README). Done when every commit is classified.
3. **Read before judging**: for each substantive change, read the full diff *and* the commit message — Matt's reasoning lives in the message body. Then read the current mx version. The mx skills are adaptations, not copies: a line upstream deletes as redundant may be load-bearing in mx (e.g. to-tickets' routing to `/mx:dispatch`), and upstream vocabulary translates (`.scratch/` → `agent/`, `/skill` → `/mx:skill`, `docs/adr/` → `decisions/`, GitHub issues → the mx `tracker` conventions).
4. **Present before editing**: one section per affected skill with a table quoting actual lines — current mx text vs proposed text — plus Matt's reasoning and your recommendation (adopt / adapt / skip, and why). The user decides per item; a go-ahead on one item doesn't cover the rest.
5. **Apply what's approved**, adapted to mx conventions, one commit per skill citing the upstream hash. Record deliberate rejections in the baseline-bump commit message so the next sync doesn't re-propose them.
6. **Move the baseline**: update the Baseline line above to the upstream HEAD you reviewed, and commit it. Done when the recorded hash equals the reviewed HEAD.

## Mapping (mx ← upstream)

Same-named: grilling, grill-with-docs, code-review, codebase-design, diagnosing-bugs, improve-codebase-architecture, prototype, research, tdd, to-spec, to-tickets, implement, handoff.

Renamed:
- orient ← ask-matt
- domain-modelling ← domain-modeling
- writing-skills ← writing-great-skills
- tracker ← the one-file-per-ticket local tracker conventions (upstream folded these into setup-matt-pocock-skills)

Everything else in mx is homegrown; everything else upstream is unadopted — flag interesting new skills, don't auto-adopt them.
