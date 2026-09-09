---
status: open
---

# Harden owns the greenlet coverage setting

## What to build

`make harden` collects a true line map on a project whose code switches stacks under coverage's tracer (SQLAlchemy's async engine, on greenlet) without any setting in the project and without inspecting the project to decide whether to run.

Coverage's `sysmon` core sees the frames the default tracer loses, and on Python 3.14 it is coverage's default. Harden sets it for its own coverage pass. Where coverage cannot use that core (Python below 3.12, a config naming a greenlet-family library), coverage prints a warning and falls back to the default core with the project's own concurrency setting, so a project that configured itself for its CI coverage is never worse off than it made itself.

Today harden refuses to measure a project that has greenlet installed but whose coverage config does not name it, and decides whether greenlet is the project's by grepping `uv.lock` and globbing `.venv`. All of that goes: the setting is harden's, so it lives in harden.

## Acceptance criteria

- [ ] Harden's coverage pass runs with coverage's `sysmon` core; verified on the yapit clone that the lines after the `await` in `get_document` are recorded with no coverage config in the project.
- [ ] The detector, the refusal, their tests and the `greenlet` package the repo's test run installed for them are gone; `--help` describes the core harden uses and nothing a project has to do.
- [ ] PYTHON.md keeps one line for a project's own coverage runs, phrased as the project's choice.

## Comments

Filed from the property-tests-land-green session, 2026-09-09, on max's ruling that a tool which needs every project special-cased is worse than none. Rewritten the same day after `agent/show/harden-greenlet/` measured the shapes: the flag shape (`--concurrency=thread,greenlet`) carries a library name and would need a mapping for gevent and eventlet; the sysmon core carries none.
