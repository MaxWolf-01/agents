---
status: done
priority: 2
size: M
blocked-by: [02]
---

# Map a bank's columns onto the fields

## Brief

Banks name their columns differently, so the account holder says once per bank which column is the
date, the payee and the amount, and the next statement from that bank arrives already mapped.

## What to build

Pick which column is the date, the payee and the amount, on the report screen,
and keep the mapping for the next statement from the same bank.

## Acceptance criteria

- [x] the report re-reads the upload as the mapping changes, without re-uploading
- [x] a second statement from the same bank arrives already mapped
