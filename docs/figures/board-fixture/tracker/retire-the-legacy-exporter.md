---
status: open
priority: 3
size: S
---

# Retire the legacy exporter

## Brief

`export_csv` writes the format the importer now reads, and nothing on the account screen has called it
since it was rewritten. Deleting it is a few lines; being sure nothing calls it is the work.

## Acceptance criteria

- [ ] `export_csv` and its tests are gone, and nothing in the tree imports it.
