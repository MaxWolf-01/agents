---
status: open
---

# Harden owns the greenlet coverage setting

## What to build

`make harden` measures coverage with greenlet named in coverage's concurrency setting on every project, from harden's own environment, so a project with SQLAlchemy's async engine gets a true line map without any per-project configuration and harden never inspects a project's lock file or virtualenv to decide whether to run.

Today harden refuses to measure a project that has greenlet installed but whose `[tool.coverage.run] concurrency` does not name it, and finds out whether greenlet is the project's by grepping `uv.lock` and globbing `.venv` (`mx/skills/testing/mutmut_runner.py`, `require_concurrency_config` and `project_has_greenlet`), because `import greenlet` inside `uv run --with` answers for harden's own packages. A tool that needs every project configured for it, and a detector to prove the configuration is missing, is the wrong shape: the measurement is harden's, so its settings are harden's.

## Acceptance criteria

- [ ] harden carries greenlet in its own run environment and collects coverage with `thread,greenlet` concurrency unconditionally; verified on the yapit clone that `get_document`'s lines after the `await` are covered, with no coverage config in the project.
- [ ] `require_concurrency_config`, `project_has_greenlet` and their tests are gone, along with harden's refusal message and the `--help` sentence about it.
- [ ] PYTHON.md keeps one line for the project's own coverage runs (CI, a local `--cov`), phrased as the project's choice, not as something harden needs.
- [ ] Verified that pytest-cov takes the setting from harden without a project config file; if it cannot, the ticket's closing comment says what harden does instead (a coverage config file it writes to its own temp dir is the fallback to try first).

## Comments

Filed from the property-tests-land-green session, 2026-09-09, on max's ruling that a tool which needs every project special-cased is worse than none.
