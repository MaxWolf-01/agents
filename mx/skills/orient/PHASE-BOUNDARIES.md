# Phase boundaries

A **phase** is a chunk of work inside a session: the grilling, the implementation, the QA. The definition is fuzzy on purpose: a phase ends when you think _"ok, we're done with that"_.

The **phase boundary** is the gap between two phases, and it is the only place this decision belongs. Mid-phase there is no decision to make: continue, or split the work that's left into subagents. Resetting mid-phase makes the agent lose the thread.

## The tree

Work top to bottom at the boundary. The first **yes** wins.

**1. Can you continue in this session?** Two things make the answer yes: the next phase needs this phase as a **primary source**, or you have enough **smart zone** left for the next phase to fit (`/mx:orient`, Context hygiene). Grilling → cutting the tickets is the standard yes: the breakdown wants the design's reasoning verbatim, not a summary of it. A ticket's build is never on this ladder: it is a fresh worker in a context of its own, whatever the size of the work (`/mx:orient`). Continue costs nothing and loses nothing, so rule it out before anything else.

**2. Is the context irrelevant to what comes next?** Is everything in this session (the exploration, the decisions, the dead ends) disposable? If so, **`/clear`**.

The cost of getting this wrong is one-way. Clear a _relevant_ context and you lose the **why** behind what you built, and no amount of reading the diff back gets it returned.

**3. Can the task be done AFK?** Is it scoped tightly enough to run with you away from the keyboard, no steering? Then send it to a **subagent** and leave this session untouched: `/mx:fork` when it needs the mental model built here (the fork inherits the transcript), a fresh background agent with a prompt when it doesn't. Automated review is the standard case.

**4. Otherwise, `/mx:handoff`.** Relevant context, the next phase needs steering, and continuing doesn't fit: compact the conversation into a handoff file and open a fresh session on it. This is also the move whenever the work must **travel**: a new harness (Claude → Codex), a new directory or repo, a colleague, a side-quest forked mid-phase.

What a handoff buys over the built-in `/compact` is **inspectability**: the file can be proofread and edited before it seeds the next session, where a compact summary is a black box; the failure mode is a fresh session confidently wrong about a decision the summary flattened. That is why `/compact` is not on this ladder, and why auto-compact is disabled.
