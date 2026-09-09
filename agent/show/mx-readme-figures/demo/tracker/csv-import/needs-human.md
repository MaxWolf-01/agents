---
worker-host: workbench.local
---

- debrief :: `csv-import`, frontier empty and everything landed. **Fixed:** the dry run's already-settled branch had no test; `{fix_sha}` adds one. **Proposed:** `06-blank-column-reason`, from a survivor no test pins. **Left:** `Row` and `ParseReport` generate no mutants, so nothing inside them is measured; the logic around them is.
