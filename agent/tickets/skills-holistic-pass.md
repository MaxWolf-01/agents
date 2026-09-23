---
status: open
type: grilling
priority: 2
size: L
---

# A holistic pass over the skills and help texts: one home, the right altitude, the right file

## Brief

The skills, the worker contract, the output style and the scripts' help texts have grown feature by feature, and reviewing one diff at a time glosses over what only a read of the whole shows: what is doubled, what could be a pointer, what sits in the wrong file.

## Questions

Ruled by the user in chat, 2026-09-18, for after figures-and-demos ships: the skills, the worker contract, the output style and the scripts' `--help` texts have grown over several features, and a review of one diff at a time glosses over what only a read of the whole shows. The pass asks, for every sentence: is it stated twice, could it be a pointer, is it too broad or too specific, could it go, and does it sit in the right file among the global system prompt, a skill's description, a skill's body and a script's help. One case to settle in it: a script whose help an agent always reads before calling it might have that help loaded as skill text instead, so the read is not a separate step; a script with branches, called only sometimes, keeps its help where it is.

To decide, options sketched by the agent, frame unconfirmed: whether the pass runs as one session over the whole plugin or per skill family (dispatch, grilling, show, tracker); whether [The dispatch and job machinery, shown](dispatch-shown.md) comes first, since the user wants to see the whole before cutting; which rules the pass applies (`/mx:writing-for-agents`, `/mx:writing-for-humans`, the principles file) and whether the prose reviewer runs over the result; and how the pass records what it cut and why, so a later reader does not restore it.

**2026-09-22** The whole-feature review of figures-and-demos (`6c9ce66..5a322f6`, Standards axis) leaves two worked examples for the pass. The landing's staged demo is now stated in `dispatch --help`, `dispatch/SKILL.md`, `orient/SKILL.md` twice, `worker-prompt.md`, `claude/output-styles/max.md` and `mx/README.md`, and drawn in `docs/figures/landing.html`: ticket 03 designed it as one sentence each pointing at `/mx:show`, and two of the copies went past a phrase into mechanics that `--help` owns ("with the branch checked out beside this worktree", "until `dispatch ctl cleanup` or the next round's `dispatch fetch`"). The dispatch skill's `review` bullet is now around 400 words in one paragraph, the longest in the skill, a sixth of it added by that feature.

**2026-09-23** Token numbers for the pass, in `agent/research/09-skill-token-usage.md` (gitignored, on zephylux), with the scripts that remeasure them after the cut:
- Where a skill's text is paid. Over the last 30 days the bodies with the most tokens resident in context were code-review, tyro-cli, grilling, dispatch and writing-for-agents. Per-load bodies grew: grilling's median went from 1.6k to 3.6k tokens, dispatch's from 3.8k to 7.5k.
- What the parent reads versus what its subagents read. code-review's reviewers read `SMELLS.md` 70 times, at ~4k tokens a read, more than the skill body itself. They read writing-for-humans' `SKILL.md` as a file 75 times, against 13 loads of that skill as a skill.
- The listing. mx's descriptions cost ~3.4k tokens on every request. Claude Code ignores `skillOverrides` for plugin skills, so an mx skill's entry shrinks only through its description or `disable-model-invocation`. On a 200k-window model the whole listing is over budget, and every mx skill except the few most used is listed by name alone.
- Before/after. `agent/research/09-skill-token-usage/capture after` records a fresh session's first request, and `compose.py` adds it as a column beside `captures/sync-off.json` and `captures/plugin-dev-off.json`.
