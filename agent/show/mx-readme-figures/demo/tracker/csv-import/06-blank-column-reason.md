---
status: proposed
---

# Nothing pins which column was blank

Cut from the harden report for this feature: the reason string a rejected line
carries survives every mutant, so no test tells "date is blank" from "payee is
blank". That string is what the mapping screen shows the account holder, and it
is the whole reason the rejected line was kept rather than dropped.

## Acceptance criteria

- [ ] the parse-report test asserts the reason, not only the line number
