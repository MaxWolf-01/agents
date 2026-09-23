---
status: open
priority: 3
size: XS
---

# Nothing pins which column was blank

## Brief

The reason a rejected line carries is what the mapping screen shows the account holder, and no test
tells "date is blank" from "payee is blank".

## What to build

Cut from this feature's debrief, where a mutant survived on exactly that string: the parse-report
test asserts the reason a rejected line carries, not only its line number.

## Acceptance criteria

- [ ] the parse-report test asserts the reason, not only the line number
