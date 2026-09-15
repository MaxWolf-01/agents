---
worker-host: agent@pc
---
- catalogue scope tags partition almost nothing :: Ticket 01 tagged 44 of 46 rules `both`, 2 `artifact`, none `chat` (its assumption A4), on the test "where the fix belongs". Options: (a) keep the tags as they are; (b) drop the column, every rule binds everywhere; (c) narrow the chat scope to the 34 rules the prototype measured (ids 3 to 39), so the hook's latency and false-positive numbers carry over. Ticket 03 builds the hook against whatever you pick; it starts on (a).
- rule 52, sentences opening with a question word :: Ticket 01 dropped the patterns file's ban on question-word openers (assumption A3) because it contradicts rule 33 and fires on correct prose; both reviewers want it back as id 52. Keep it dropped, or add 52?
- board lanes for buildable proposals :: Ticket 02 kept the board drawing every proposal in one lane outside the waves (assumption A6), so a proposal that is claimable now sits beside one that is gated. Split the lane, or leave it?
- review range: fixed point or merge-base :: The reports' directory is `<fixed7>..<head7>` per the spec (04's A2). When the fixed point is a branch that moved since the fork, that range names a different change set than the three-dot diff the reviewers read. Keep the fixed point, or name the merge-base?
- "Filed" as a third disposition :: The spec's finding index names fixed and declined; 04 kept "filed" (a finding that becomes a proposed ticket) as a third row so it does not vanish from the index (its A1). Keep three, or fold filed into declined?
