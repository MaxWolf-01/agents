---
status: open
priority: 3
size: S
---

# Retire the legacy exporter

## Brief

`export_csv` writes the format the importer now reads, and nothing has called it since the account
screen was rewritten. Deleting it is a few lines; being sure nothing calls it is the work.

## What to build

Cut from a worker's closing comment on `csv-import/02`: `export_csv` and every test of it go, once
nothing in the tree imports it.

## Acceptance criteria

- [ ] `export_csv` and its tests are gone, and nothing imports it
