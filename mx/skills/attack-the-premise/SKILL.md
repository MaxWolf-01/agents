---
name: attack-the-premise
description: "Apply when two or more fixes that share one premise have failed the same gate. Write the premise down and test it directly before you write another fix that assumes it."
---

# Attack the premise

Each failed fix is evidence against the belief it assumed. A third fix on the same premise spends effort where the evidence already says the cause is not, so suspect the premise, not the fixes.

- **Write the premise down.** The premise is the one sentence every failed fix assumed.
- **Test it before the next fix.** Find an observation that would come out differently if the premise were false, and make it. Look at how the failures are distributed, not only at how large they are. Make the check rerunnable.
- **Follow the evidence.** If it contradicts the premise, the cause is elsewhere: look for what the failures share that the premise did not predict. If it confirms the premise, ask the next "why": the earlier fixes may have treated a consequence instead of the cause.
- **Remove the condition instead of compensating for it.** If one part always lands on the losing side, change what puts it there. A mechanism that cleans up after it leaves the cause in place and adds work on every run.

The next fix starts only once the premise is written down and tested.
