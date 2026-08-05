# Phase boundaries

A **phase** is a chunk of work inside a session — the grilling, the implementation, the QA. The definition is fuzzy on purpose: a phase ends when you think _"ok, we're done with that"_.

The **phase boundary** is the gap between two phases, and it is the only place this decision belongs. Mid-phase there is no decision to make — continue, or split the work that's left into subagents. Resetting mid-phase makes the agent lose the thread.

## The four options

| Option           | What it does                                                                         |
| ---------------- | ------------------------------------------------------------------------------------ |
| **Continue**     | Stay in the session. No context switch at all.                                       |
| **`/clear`**     | Empty the context window and start from nothing.                                     |
| **Subagent**     | Send the task to its own context window and get a report back.                       |
| **`/mx:handoff`** | Compact the conversation into a portable markdown file and seed a fresh session with it. |

## The tree

Work top to bottom at the boundary. The first **yes** wins.

**1. Can you continue in this session?** Two things make the answer yes: the next phase needs this phase as a **primary source**, or you have enough **smart zone** left for the next phase to fit (degradation becomes noticeable from roughly 30% of the window used — the advertised size is retrieval room, not reasoning room). Grilling → implementation is the standard yes: the implementation wants the reasoning verbatim, not a summary of it. Continue costs nothing and loses nothing, so rule it out before anything else.

**2. Is the context irrelevant to what comes next?** Is everything in this session — the exploration, the decisions, the dead ends — disposable? If so, **`/clear`**. It is the cheapest move on the board: it takes no time and hands back the whole window. `/clear` also isn't terminal — the old session stays resumable.

The cost of getting this wrong is one-way. Clear a _relevant_ context and you lose the **why** behind what you built, and no amount of reading the diff back gets it returned.

**3. Can the task be done AFK?** Is it scoped tightly enough to run with you away from the keyboard, no steering? Then send it to a **subagent** and leave this session untouched: `/mx:fork` when it needs the mental model built here (the fork inherits the transcript), a fresh background agent with a brief when it doesn't. Automated review is the standard case: the agent reads the diff and reports, and you aren't needed while it does.

**4. Otherwise, `/mx:handoff`.** Relevant context, the next phase needs steering, and continuing doesn't fit — compact the conversation into a handoff file and open a fresh session on it. This is also the move whenever the work must **travel**: a new harness (Claude → Codex), a new directory or repo, a colleague, a side-quest forked mid-phase.

What a handoff buys over the built-in `/compact` is **inspectability**: the file can be proofread and edited before it seeds the next session, where a compact summary is a black box — the failure mode is a fresh session confidently wrong about a decision the summary flattened. That is why `/compact` is not on this ladder, and why auto-compact is disabled.

## Primary and secondary sources

Every move except **Continue** turns a **primary source** into a **secondary source** — the session as it happened, replaced by a summary of it. The trade is always the same shape:

| Source                     | Information | Noise | Room to move |
| -------------------------- | ----------- | ----- | ------------ |
| Primary (Continue)         | Full        | Lots  | Little       |
| Secondary (`/mx:handoff`)  | Lossy       | Less  | Lots         |

This is why question 1 comes first. You only pay the lossiness when staying costs more than it saves.

## These are judgement calls

The questions are not objective — each has taste in it, and the same boundary can go two ways on two days. The value is in asking them **in order**, at the boundary rather than in the middle of the work.
