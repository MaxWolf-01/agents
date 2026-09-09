---
status: proposed
---

# Retire the legacy exporter

Cut from a worker's closing comment on `02-upload-and-parse-report`: the old
`export_csv` writes the format the importer now reads, and nothing has called
it since the account screen was rewritten.
