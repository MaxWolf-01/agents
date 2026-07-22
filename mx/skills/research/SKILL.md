---
description: Investigate a question and produce a research artefact
argument-hint: [topic or question]
---

Investigate a question. Write the findings to `agent/research/NN-<slug>.md` (numbered from the highest existing).

Research artefacts are point-in-time snapshots that other sessions consume. Be exhaustive on findings; skip the storytelling (no methodology recap, no intro/conclusion prose — every sentence a finding or a citation).

1. Sharpen the question first if it's fuzzy.
2. Investigate against **primary sources** — official docs, source code, specs, first-party APIs — not a secondary write-up of them. Follow every claim back to the source that owns it.
3. Write the artefact: `## Question`, `## Findings`. Cite each claim's source (URL, file path, commit). Short is fine; if findings are inconclusive, say so — don't pad to appear complete.
4. If the research backs a spec or ticket, list the artefact there (that's the direction future agents read); give the artefact a `task:` frontmatter line pointing back.
