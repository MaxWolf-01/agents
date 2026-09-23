---
status: proposed
priority: 3
size: XS
---

# Worker hosts keep job current

## Brief

A worker host keeps whichever `job` it fetched first, so it can lag the dotfiles by weeks without anyone noticing. `dispatch-ctl init` should refresh the copy it fetched, and leave alone a `job` installed any other way.

Cut from the orchestrator's run of figures-and-demos' landing demo on 2026-09-23. agent@pc's `job` was fetched before `job stage` existed, and the whole-feature review of figures-and-demos read that as the mode missing from the dotfiles (its `[D3]`, and queue entry D33 on master).

## What to build

`dispatch-ctl init` fetches `job` into `~/.local/bin` only when the host has none, and keeps any copy it finds. It should re-fetch its own copy, the one in `~/.local/bin`, on every init. A `job` found elsewhere on PATH stays untouched: on the orchestrator's machine that one is home-manager's.

## Acceptance criteria

- [ ] An init on a host whose `~/.local/bin/job` differs from the one at the fetch URL replaces it.
- [ ] An init on a host whose `job` is elsewhere on PATH leaves it alone.
