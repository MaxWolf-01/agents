---
status: proposed
priority: 3
size: XS
---

# Pin which column was blank

## Brief

Cut from csv-import's close-out: the reason a rejected line carries is what the mapping screen shows,
and no test tells "date is blank" from "payee is blank".

## Acceptance criteria

- [ ] The parse report's test asserts the reason a rejected line carries, not only its number.
