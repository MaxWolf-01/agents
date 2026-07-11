---
name: bloat-audit
description: Whole-repo over-engineering audit — a ranked list of what to delete, simplify, or replace with stdlib. Report only; applying cuts is a separate decision.
disable-model-invocation: true
---

Audit the repo for code that shouldn't exist. Read the code, not the tree:
the manifest, the entry points, every source file outside vendored or
generated output. The audit is complete when every dependency and every
source file has been cleared or flagged — a file only skimmed is a file not
yet audited. Rank findings biggest cut first.

## Tags

- `delete:` dead code, unused flexibility, speculative feature. Replacement: nothing.
- `stdlib:` hand-rolled thing the standard library ships. Name the function.
- `native:` dependency or code doing what the platform already does. Name the feature.
- `yagni:` abstraction with one implementation, config nobody sets, layer with one caller.
- `shrink:` same logic, fewer lines. Show the shorter form.

## Hunt

Deps the stdlib or platform already ships, single-implementation interfaces,
factories with one product, wrappers that only delegate, files exporting one
thing, dead flags and config, hand-rolled stdlib.

## Output

One line per finding, ranked: `<tag> <what to cut>. <replacement>. [path]`.

- `stdlib: 27-line email validator class. "@" in email, real validation is the confirmation mail. [validators.py:L12]`
- `native: moment.js imported for one format call. Intl.DateTimeFormat, 0 deps. [utils/date.js:L4]`
- `yagni: AbstractRepository with one implementation. Inline it until a second one exists. [repo.py:L88]`
- `delete: retry wrapper around an idempotent local call. Nothing replaces it. [client.py:L52]`

End with `net: -<N> lines, -<M> deps possible.` Nothing to cut: `Lean already. Ship.`

## Boundaries

Scope is over-engineering only; route correctness, security, and performance
findings to a normal review pass. A lone smoke test or `assert` self-check is
the lean minimum — leave it standing. Report only: the reader decides what to
apply.
