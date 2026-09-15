---
status: claimed
blocked-by: [06]
---

# The worker host is chosen per spawn, never recorded

## What to build

Dispatch stops recording a worker host anywhere. The orchestrator names the host when it spawns a worker: `dispatch ctl spawn <ticket> <model>` takes the host (`user@host`, or `local`), and the first spawn on a host does what `dispatch setup` did (the git remote, the scripts and worker prompt in that host's scratch dir for this branch, `dispatch-ctl init`, the push); a later spawn on the same host finds it staged and skips it. Each run records its host in the run's own record, so `wait`, `fetch`, `log`, `stop`, `resume` and `cleanup` find a ticket's host from the ticket and never from configuration. `dispatch setup` and the `dispatch.host`, `dispatch.repo` and `dispatch.setup-cmd` keys go; the repo name and the project's setup command travel the way the host does, as arguments of the first spawn on a host or as facts the scripts derive (the repo name from the checkout). `needs-human.md` stops carrying a `worker-host:` line; the board's per-feature host label reads from the runs instead, or is dropped.

The dispatch skill's setup section shrinks to what still needs saying once per feature (the feature worktree, the neighbour check), and its wave step is where the host is picked, per ticket: the live list from `worker-hosts`, each host's capability record, and what the ticket says it needs. A ticket that needs a machine nobody has becomes a needs-human entry, not a blocker in a worker.

Cut from ticket 05's closing comment and the user's ruling on it: recording one host per repo (or per feature, as before) caches a decision that belongs to the moment of spawning, and an override on top would patch the cache.

## Acceptance criteria

- [ ] `rg 'dispatch\.host|dispatch\.repo|dispatch\.setup-cmd|dispatch setup'` across the repo finds nothing; a fresh checkout dispatches a ticket with no setup step.
- [ ] Two tickets of one feature can run on two different hosts, and every per-ticket command follows its ticket to the right host.
- [ ] The dispatch skill picks the host in the wave step, from the live host list and the ticket, and says what happens when no host fits.
- [ ] Property, reviewed: one worker contract; a worker's obligations do not depend on what spawned it or where it runs.
- [ ] Demo in the closing comment: two toy tickets of one feature spawned on `local` and on a second host (or `local` twice with distinct scratch dirs if only one machine is reachable), the run records naming their hosts, and `wait`, `fetch` and `cleanup` finding each.
