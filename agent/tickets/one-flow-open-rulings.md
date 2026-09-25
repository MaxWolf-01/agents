---
status: open
needs-user: true
priority: 2
size: S
---

# Four rulings left open when one-flow shipped

## Brief

Four small calls left open when one-flow shipped: which prose rules the chat hook applies, whether the question-word ban returns, whether proposed tickets still read wrong on the board, and whether rule 14 binds agent-facing prose.

Carried from the one-flow feature's needs-human queue when its directory was retired; the fourth came later, from the review of every-property-gets-a-criterion (its D4, 2026-09-22). Each is a small call; none blocks other work.

## Questions

1. **Which prose rules the chat hook applies.** Every rule in `mx/skills/writing-for-humans/CATALOGUE.md` carries a tag saying where it applies: written artifacts, chat replies, or both. 44 of 46 came out "both", 2 "artifact", none "chat", so the tag barely distinguishes anything and the hook reads 44 rules. Options: (a) keep the tags as they are; (b) drop the tag, every rule applies everywhere; (c) limit the hook to the 34 rules the prototype was measured on.
2. **Rule 52, sentences opening with a question word.** The old patterns file banned them; ticket 01 dropped the ban because it contradicts rule 33 and fires on correct prose ("When the parser fails, it exits 2"). Both of its reviewers wanted it back. Options: (a) keep it dropped; (b) add it as rule 52.
3. **Proposed tickets on the board.** Every slice to-tickets cuts is `proposed` until its build is accepted. On the board as it stood during one-flow, proposed tickets were left out of the counts, the graph and the wave lanes, so a freshly cut feature showed no graph. Master's redesign of the board (rows grouped by state, a graph panel that draws proposed tickets in their own class once something waits on them) may already answer this; render a feature with only proposed slices and decide whether anything is still missing.
4. **Rule 14, the colon as a mid-sentence connector, against agent-facing prose.** The catalogue bans it, and it is the native voice of `PRINCIPLES.md` and of nearly every skill in the plugin, so every reviewer of a skill diff settles the conflict alone. Options: (a) rule 14 does not bind agent-facing prose, and the catalogue says so where it lists its scope tags; (b) it binds, and the skills are brought into line over time.
