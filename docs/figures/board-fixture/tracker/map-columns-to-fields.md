---
status: review
parent: csv-import
blocked-by: [upload-and-parse-report]
priority: 2
size: M
---

# Map a bank's columns onto the fields

## Brief

Banks name their columns differently, so the account holder says once per bank which column is the
date, the payee and the amount, and the next statement from that bank arrives already mapped.

## Acceptance criteria

- [x] The report re-reads the upload as the mapping changes, without uploading it again.
- [x] A second statement from the same bank arrives already mapped.

## Comments

**Built on `ticket/map-columns-to-fields`, merged into `csv-import` for its close-out.** Both criteria are met.

**Details, if you want them**

- [D1] Assumptions
  - A1 `ledger/mapping.py:6`: a bank with no remembered mapping starts from the default one, to correct on screen.
