---
worker-host: agent@pc
---
- catalogue scope tags partition almost nothing :: Ticket 01 tagged 44 of 46 rules `both`, 2 `artifact`, none `chat` (its assumption A4), on the test "where the fix belongs". Options: (a) keep the tags as they are; (b) drop the column, every rule binds everywhere; (c) narrow the chat scope to the 34 rules the prototype measured (ids 3 to 39), so the hook's latency and false-positive numbers carry over. Ticket 03 builds the hook against whatever you pick; it starts on (a).
- rule 52, sentences opening with a question word :: Ticket 01 dropped the patterns file's ban on question-word openers (assumption A3) because it contradicts rule 33 and fires on correct prose; both reviewers want it back as id 52. Keep it dropped, or add 52?
- board lanes for buildable proposals :: Ticket 02 kept the board drawing every proposal in one lane outside the waves (assumption A6), so a proposal that is claimable now sits beside one that is gated. Split the lane, or leave it?
- one worker host per repo :: Ticket 05 records the host once per repo (`dispatch.host`), as the spec says; a feature that wants a different host than the repo's (the GPU box for one feature, the always-on box for the rest) cannot have one without re-recording for everything. Is a per-feature override a real case, or is one host per repo enough?
