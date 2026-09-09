---
status: done
blocked-by: [02]
---

# Map a bank's columns onto the fields

## What to build

Pick which column is the date, the payee and the amount, on the report screen,
and keep the mapping for the next statement from the same bank.

## Acceptance criteria

- [x] the report re-reads the upload as the mapping changes, without re-uploading
- [x] a second statement from the same bank arrives already mapped
