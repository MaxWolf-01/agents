---
name: bloat-audit
description: "Whole-repo over-engineering audit: what to delete, simplify, or replace."
---

Audit the repo for code that shouldn't exist. Read the code, not the tree:
the manifest, the entry points, every source file outside vendored or
generated output. The audit is complete when every dependency and every
source file has been cleared or flagged; a file only skimmed is a file not
yet audited. Rank findings biggest cut first.

Tags you can orient by and use in commit body and explainers:
- `delete:` dead code, unused flexibility, speculative feature, noops, comment/docs bloat. Replacement: nothing.
- `stdlib:` hand-rolled thing the standard library ships. Name the function.
- `native:` dependency or code doing what the platform already does. Name the feature.
- `yagni:` abstraction with one implementation, config nobody sets, dead flags and config, layer with one caller.
- `shrink:` same logic, fewer lines. Show the shorter form.
- `refactor:` same logic, clearer form; wrappers that only delegate; one home instead of two, ...

Deliverable: Diffview + /mx:show artefact for visual understanding of the diff iff applicable.

Scope is over-engineering only; route correctness, security, and performance findings to a normal review pass. 
For findings that touch the shape of seams, consult `/mx:improve-codebase-architecture`.
