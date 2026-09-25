---
name: research
description: "Investigate a question against primary sources and land the findings on the ticket that asked it. Use when a decision waits on a fact outside the working directory: a third-party API, a vendor's docs, a standard, a knowledge base, or when another skill fires a background investigation."
argument-hint: [topic or question]
---

Investigate a question, and be exhaustive on findings: skip the storytelling, no methodology recap and no intro or conclusion prose, every sentence a finding or a citation. Short is fine; findings that are inconclusive say so rather than padding to look complete.

1. Sharpen the question first if it's fuzzy.
2. **Frame check**: when the question arrives with a diagnosis or option list attached (a ticket's options, an earlier session's plan), the options share a **frame**, the premise that makes them the menu. State that premise in one sentence, then name the strongest option *outside* it; drop the premise and check whether the problem dissolves. Agent-authored framing is an assumption to test; a frame the user decided (an ADR, a ticket's decision, a grilling verdict) stands, so surface a conflict rather than reopening it.
3. Investigate against **primary sources** (official docs, source code, standards, first-party APIs), not a secondary write-up of them. Follow every claim back to the source that owns it.
4. **The findings land in the ticket that asked the question** (`/mx:tracker`): the gist, the answers its acceptance criteria asked for, and each claim's source (URL, file path, commit). An inherited frame is reported there too: the shared premise, the strongest option outside it, and the verdict, whose "holds" needs its why.
5. Detail too long for the ticket, and only when there is some, goes to `agent/research/NN-<slug>.md` in the agent repo (numbered from the highest existing), cited from the ticket and carrying a `ticket:` frontmatter line pointing back. What the user has to see or understand to judge the answer is a `/mx:show` artifact instead of prose.
