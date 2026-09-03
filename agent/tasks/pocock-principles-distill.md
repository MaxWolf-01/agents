---
status: open
---

# Distill workflow principles from upstream and our own refinement history

Two histories hold lessons nobody has written down as principles:

1. Upstream: mattpocock/skills release history since our adoption baseline (see the pocock-sync skill for the recorded baseline commit).
2. Ours: this repo's commit history since the workflow was adopted — every refinement we made to the adapted skills, and why (e.g. ef90c24 harness-agnostic wording).

Also: Fetch youtube transcripts from his youtube and talks he gave -- one of them is already symlinked in this repo's resources/

## Research

- `agent/research/03-agent-workflow-principles.md` — both histories, the blog, the keynote and 32 videos, plus a web survey of other practitioners, read into a candidate list with citations, a model-specific layer, and a mapping onto the current CLAUDE.md bullets. Transcripts and the fetch recipe sit beside it in `03-agent-workflow-principles.sources/`.

## What to build

Read both histories, extract the recurring principles — the things that repeatedly bit and got fixed, upstream or here — and distill them as durable context for future workflow adjustments. Shape (Max, 2026-09-03): a file loaded when skills, CLAUDE.md or the workflow are edited, with one pointer line in CLAUDE.md — not always-loaded bullets; the research artefact's Frame section carries the reasoning.

## Acceptance criteria

- Each bullet is a principle (transferable rule), not a change log entry.
- Each cites at least one commit (upstream or ours) as evidence.
- Existing CLAUDE.md bullets that turn out to be instances of a distilled principle are folded in, not duplicated.
