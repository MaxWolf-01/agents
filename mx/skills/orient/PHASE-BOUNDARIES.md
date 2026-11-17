# Phase boundaries

A **phase** is a chunk of work inside a session: the grilling, the implementation, the QA. The definition is fuzzy on purpose: a phase ends when you think _"ok, we're done with that"_.

The **phase boundary** is the gap between two phases, and the only place this decision belongs. Mid-phase, continue, or split the work that is left into subagents: a reset mid-phase makes the agent lose the thread.

## The tree

Work top to bottom at the boundary. The first **yes** wins.

**1. Can you continue in this session?** Yes if the next phase needs this phase as a **primary source**, or if enough **smart zone** is left for the next phase to fit (`/mx:orient`, Context hygiene). Grilling → cutting the tickets is the standard yes: the breakdown wants the design's reasoning verbatim, not a summary of it. A ticket's build is never on this ladder: it is a fresh worker in a context of its own, whatever the size of the work (`/mx:orient`). Continuing costs nothing and loses nothing, so rule it out before anything else.

**2. Is the context irrelevant to what comes next?** Is everything in this session (the exploration, the decisions, the dead ends) disposable? If so, **`/clear`**.

Getting this wrong costs in one direction only: clear a _relevant_ context and the **why** behind what you built is lost, and no reading of the diff gets it back.

**3. Can the task be done AFK?** If it is scoped tightly enough to run with you away from the keyboard, without steering, send it to a **subagent** and leave this session untouched: `/mx:fork` when it needs the mental model built here (the fork inherits the transcript), a fresh background agent with a prompt when it does not. Automated review is the standard case.

**4. Otherwise, `/mx:handoff`.** The context is relevant, the next phase needs steering, and continuing does not fit: compact the conversation into a handoff file and open a fresh session on it. It is also the move whenever the work must **travel**: to a new harness (Claude → Codex), a new directory or repo, a colleague, a side-quest forked mid-phase.

A handoff beats the built-in `/compact` on **inspectability**: the file can be proofread and edited before it seeds the next session, where a compact summary is a black box, and the failure is a fresh session confidently wrong about a decision the summary flattened. That is why `/compact` is not on this ladder, and why auto-compact is disabled.
