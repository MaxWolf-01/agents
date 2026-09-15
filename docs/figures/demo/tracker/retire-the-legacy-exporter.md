---
status: proposed
---

# Retire the legacy exporter

Cut from a worker's closing comment on `csv-import/02`: the old `export_csv`
writes the format the importer now reads, and nothing has called it since the
account screen was rewritten. Deleting it is a few lines; being sure nothing
calls it is the work.

## Acceptance criteria

- [ ] `export_csv` and its tests are gone, and nothing imports it
