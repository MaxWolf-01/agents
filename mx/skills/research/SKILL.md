---
name: research
description: Investigate a question and produce a research artefact
argument-hint: [topic or question]
---

Investigate a question. Write the findings to `agent/research/NN-<slug>.md` (numbered from the highest existing).

Research artefacts are point-in-time snapshots that other sessions consume. Be exhaustive on findings; skip the storytelling (no methodology recap, no intro/conclusion prose; every sentence a finding or a citation).

1. Sharpen the question first if it's fuzzy.
2. **Frame check**: when the question arrives with a diagnosis or option list attached (a ticket's Options section, an earlier session's plan): the options share a **frame**, the premise that makes them the menu. State that premise in one sentence, then name the strongest option *outside* it: drop the premise and check whether the problem dissolves. Agent-authored framing is an assumption to test (`/mx:implement`); a frame the user decided (ADR, spec decision, grilling verdict) stands: surface a conflict rather than reopening it.
3. Investigate against **primary sources** (official docs, source code, specs, first-party APIs), not a secondary write-up of them. Follow every claim back to the source that owns it.
4. Write the artefact: `## Question`, `## Frame` (required when one was inherited: the shared premise, the strongest out-of-frame option, and the verdict; "holds" needs the why), `## Findings`. Cite each claim's source (URL, file path, commit). Short is fine; if findings are inconclusive, say so; don't pad to appear complete.
5. If the research backs a spec or ticket, list the artefact there (that's the direction future agents read); give the artefact a `task:` frontmatter line pointing back.
