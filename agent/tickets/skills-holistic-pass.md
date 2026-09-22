---
status: open
type: grilling
---

# A holistic pass over the skills and help texts: one home, the right altitude, the right file

## Question

Ruled by the user in chat, 2026-09-18, for after figures-and-demos ships: the skills, the worker contract, the output style and the scripts' `--help` texts have grown over several features, and a review of one diff at a time glosses over what only a read of the whole shows. The pass asks, for every sentence: is it stated twice, could it be a pointer, is it too broad or too specific, could it go, and does it sit in the right file among the global system prompt, a skill's description, a skill's body and a script's help. One case to settle in it: a script whose help an agent always reads before calling it might have that help loaded as skill text instead, so the read is not a separate step; a script with branches, called only sometimes, keeps its help where it is.

To decide, options sketched by the agent, frame unconfirmed: whether the pass runs as one session over the whole plugin or per skill family (dispatch, grilling, show, tracker); whether [The dispatch and job machinery, shown](dispatch-shown.md) comes first, since the user wants to see the whole before cutting; which rules the pass applies (`/mx:writing-for-agents`, `/mx:writing-for-humans`, the principles file) and whether the prose reviewer runs over the result; and how the pass records what it cut and why, so a later reader does not restore it.
