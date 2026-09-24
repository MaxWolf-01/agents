---
status: open
priority: 3
size: S
---

# The grid's words in /mx:show

## Brief

The ways an explanation can show a thing, as words you and an agent both ask with: the level (concept, code, output) against the form (as it is, how it changed). They land in `/mx:show` and the glossary.

Asked for by max on 2026-09-22, in the session-page grilling (its Q1: the words land on their own, ahead of the page). Starts once `figures-and-demos` has merged into master, since that feature rewrites `/mx:show` around its shape table and this change sits on top of it.

## What to build

The ways an explanation can show a thing, as leading words an agent and max both think and ask with. They sit on two axes. The level is what the reader looks at: the **concept** (how it fits, why), the **code** (what is written: code, config, prompt, skill prose) or the **output** (what it produces: a printout, a render, a session transcript). The form is the thing as it is, or how it changed. Prose can sit at any level. The words:

| | as it is | how it changed |
| --- | --- | --- |
| prose | abstract prose, narrated example | |
| concept | concept figure | concept diff |
| code | code listing | code diff |
| output | output | output diff |

- The line that matters is narrated against real, not abstract against concrete: an example written from the head is still prose; one pasted from a run is output.
- The reader's question picks the level (how does it fit, what did you write, what will I see) and whether something moved picks the form. There is no default cell: a clean output diff is usually the most useful, and cells combine whenever each adds something the others don't.
- The cell is "prose", not "tell": "tell" keeps its catalogue meaning in `/mx:writing-for-humans`, a giveaway of generated text.

The words go into `/mx:show` as the frame above its shape table, and into `CONTEXT.md` under a new Showing heading through `/mx:domain-modelling`. Round 1 of the session-page grilling drew the grid with one toy change filling every cell: `agent/show/session-page/round-1/index.html`.

## Acceptance criteria

- [ ] `/mx:show` carries the grid and the choosing rule once, and its shape table reads as filling the grid's cells at two stations rather than as a second vocabulary.
- [ ] The glossary entries pass `glossary-lint`, and no other file restates the grid.
- [ ] Each word passes `/mx:writing-for-agents`' test for what else it primes.
- [ ] Demo: a driven session asked to explain one change, before and after the edit, showing which cells it picked.
