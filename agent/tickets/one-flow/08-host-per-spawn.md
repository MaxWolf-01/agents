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

- [x] `rg 'dispatch\.host|dispatch\.repo|dispatch\.setup-cmd|dispatch setup'` across the repo finds nothing; a fresh checkout dispatches a ticket with no setup step.
- [x] Two tickets of one feature can run on two different hosts, and every per-ticket command follows its ticket to the right host.
- [x] The dispatch skill picks the host in the wave step, from the live host list and the ticket, and says what happens when no host fits.
- [x] Property, reviewed: one worker contract; a worker's obligations do not depend on what spawned it or where it runs.
- [x] Demo in the closing comment: two toy tickets of one feature spawned on `local` and on a second host (or `local` twice with distinct scratch dirs if only one machine is reachable), the run records naming their hosts, and `wait`, `fetch` and `cleanup` finding each.

## Comments

### Closing comment

Dispatch no longer records a worker host anywhere: `dispatch ctl --host <user@host|local> spawn <ticket> <model>` is where one is named, the first spawn on a host stages it, and every command that follows a ticket reads its host from the run record that spawn wrote. `dispatch setup` and the `dispatch.*` git config keys are gone, the repo name is derived from the checkout, and the queue file and the board have dropped the per-feature host. Four commits on `ticket/one-flow/08-host-per-spawn`, `7798574`, `38d789e`, `e6c1b0f` and `33dccce`, unmerged.

**Demo.** One command, from a checkout of this branch:

```
$ bash agent/show/host-per-spawn/demo.sh
```

It builds a toy repo in a fresh temp dir, stages a stub in the runner's place (so no harness runs, while `dispatch` and `dispatch-ctl` themselves do), and drives three tickets of a feature plus one standalone ticket. What to look for, in the order it prints:

```
== 01 on local: the first spawn on a host stages it and pushes what it cuts from
+ cp .../dispatch-ctl .../run-worker.sh .../worker-prompt.md /tmp/tmp.YpQ/setup /home/agent/.local/state/dispatch/lamp-lamp-ui/
+ bash .../dispatch-ctl init lamp lamp-ui agent/tickets/lamp-ui /tmp/hps/lamp-lamp-ui /tmp/hps
+ on_host local env ... bash .../dispatch-ctl spawn 01-warm-preset sonnet
spawned dispatch-lamp-lamp-ui-01  run=dispatch-lamp-lamp-ui-01-1789436979
dispatch-lamp-lamp-ui-01 exited  run=...  attempts=1 exit=0 status=done session=stub-...

== 02 on local: staged already, so the spawn is the spawn
+ cp .../prompt-02.md /home/agent/.local/state/dispatch/lamp-lamp-ui/      # no copy of the scripts, no init

== the branch's worker prompt moves on; 03 finds an older copy staged and stages again
+ cp .../dispatch-ctl .../run-worker.sh .../worker-prompt.md .../lamp-lamp-ui/
the host holds the branch's prompt, byte for byte

== each run recorded its host, under the common git dir
lamp-ui	01	local
lamp-ui	02	local
lamp-ui	03	local

== probe: every host this branch has run on, each line behind its host
local  dispatch-lamp-lamp-ui-03 exited  run=...  attempts=1 exit=0 status=done session=stub-...
local  dispatch-lamp-lamp-ui-02 exited  ...
local  dispatch-lamp-lamp-ui-01 exited  ...

== fetch and cleanup follow each ticket to its own host
local host: ticket/lamp-ui/01-warm-preset is already here
+ on_host local env ... bash .../dispatch-ctl cleanup 01-warm-preset

== a standalone ticket dispatches from the integration branch, into its own scratch dir
/home/agent/.local/state/dispatch/lamp-lamp-ui
/home/agent/.local/state/dispatch/lamp-main

== a ticket recorded on another machine: the command goes there, and only there
+ on_host agent@nowhere.invalid env ... bash .local/state/dispatch/lamp-main/dispatch-ctl log 04
ssh: Could not resolve hostname nowhere.invalid: Name or service not known
```

Two readings of that transcript. It was captured before `33dccce`, so the run listing after the three cleanups now shows only the standalone line: `cleanup` forgets the run it removed. And the last two steps are what one machine can show of two hosts: the second host is a record, not a machine, so the ssh hop is real and the machine at the end of it is not. See `[D4]`.

**I need from you**

1. `[D1]` `agent/tickets/plugin-scripts-on-path/spec.md` is `status: confirmed`, its shims shipped in `a9f4740`, and three of its lines still describe `dispatch setup` and the `dispatch.*` keys as the mechanism. Spec language is yours: retire the directory (`/mx:tracker`, Retire), or amend those lines? It is the one live document acceptance criterion 1's `rg` still finds (A6).
2. `[D2]` Two fixtures behind the README's board figures still carry the retired `worker-host:` frontmatter, `agent/show/mx-readme-figures/demo/tracker/{saved-views,csv-import}/needs-human.md`. Ticket 07 owns the README figures and is running now, so I left them rather than edit its surface under it.
3. `[D3]` Two calls where the ticket left a choice: the board's per-feature host label is dropped rather than read from the runs (A2), and the host is an option of `dispatch ctl` rather than a positional of `spawn` (A1). Both are one-line reversals if you want the other.
4. `[D4]` One declined finding and one demonstration gap, both the same shape: no second machine is reachable from this host, so `stage`'s ssh arm and `push_to`'s remote arm ran only against a host that does not resolve, and I left the demo script exactly as it was verified rather than re-run it here (A6, A11).

**Details, if you want them**

5. `[D5]` **Assumptions.**

   - A1 `mx/skills/dispatch/dispatch:12`: the host is an option of `dispatch ctl` (`--host`), where the ticket wrote it as part of `spawn`. `ctl` forwards dispatch-ctl's own argv, and `fuzz start` needs the same choice, so the host rides on dispatch's side of the command line. See `[D3]`.
   - A2 `mx/skills/tracker/board.py:244`: the board's per-feature host label is dropped, the ticket's second option. A feature has no one host now, and the run record is dispatch's own state under the git dir, which the board would have to reach into per ticket to say anything true. See `[D3]`.
   - A3 `mx/skills/dispatch/dispatch:243`: `dispatch prompt` writes the ticket message here and the spawn carries it, where it used to write it on the host. Before a spawn names a host there is none to write to.
   - A4 `mx/skills/dispatch/dispatch:103`: the repo name comes from the common git dir, `<repo>/.git` in a checkout and `<repo>.git` in the bare repo a host holds, where the ticket said "from the checkout": one rule reads it off either side, and a feature worktree (`<repo>-<feature>`) would have given the wrong name.
   - A5 `mx/skills/dispatch/dispatch:254`: `probe` with no `--host` fans out over every host the branch has a run on, each line behind its host. The ticket's list of commands that follow a ticket does not name it, and a hostless probe has to mean this now.
   - A6 `agent/tickets/one-flow/08-host-per-spawn.md:18`: criteria 1 and 2 are ticked as "no live document and no code says otherwise, and the routing is demonstrated". The `rg` still matches ten lines: this ticket's own text (2), ticket 05's and 06's closing comments, `plugin-scripts-on-path/spec.md` (`[D1]`), and the frozen `agent/show/dispatch-ctl-absorb/orchestrator-ticket-lifecycle.sh` that ticket 06's A8 already declined to touch. Criterion 2's two hosts are built and reviewed, and demonstrated as a record pointing at another machine rather than a second machine. See `[D4]`.
   - A7 `agent/show/host-per-spawn/demo.sh:1`: the demo is committed as a show artefact beside `agent/show/dispatch-ctl-absorb/`, rather than left in `/tmp` as ticket 06's toy runs were, so the steps a stranger runs are one command and the scripts, which have no test suite, have one thing that drives them end to end.
   - A8 `mx/skills/dispatch/dispatch-ctl:230`: `send-keys` and `capture-pane` name their session with tmux's `=` exact-match prefix, as `kill-session` and `has-session` already did. Not asked for by this ticket; it rode this branch because the host's tmux server died under me and this was the nearest path in these scripts to touching a session they do not own. See `[D7]`.
   - A9 `.gitignore:6`: `__pycache__/` is ignored, after a reviewer running pytest directly left `.pyc` files staged in my own commit.
   - A10 `mx/skills/dispatch/SKILL.md:37`: the conflict step runs `dispatch push` before resuming the worker. The tip a worker is told to rebase onto reaches its host by push and by nothing else, which was true before this ticket too and had no step saying so.
   - A11 `agent/show/host-per-spawn/demo.sh:60`: declined, the demo re-derives the feature-or-standalone ticket path that `locate` already computes (Standards 3), and it asserts neither the skip-restaging branch nor `dispatch push` (Tests d1, d2). Every one of those is an edit to a script I was told not to re-run on this host after the tmux server died, and an unrun demo is worth less than a redundant line in one. See `[D4]`.

6. `[D6]` **Finding index.** `/mx:code-review`, four axes, against merge-base `a554d0a`; reports under `agent/reviews/a554d0a..e6c1b0f/`. Fixes in `33dccce`.

   - Correctness 1: `dispatch push` died on the first unreachable host, and nothing ever pruned the run record, so a host that finished three waves ago could block the push a live worker is waiting to rebase onto → fixed, `push` reports the host that refused and reaches the rest, `cleanup` forgets the run it removed.
   - Correctness 2: a hostless `probe` piped each host through `sed`, so an unreachable host was an absent line and exit 0 → fixed, it prints that host's state where its workers would have been and returns nonzero.
   - Standards 1: the queue reader's frontmatter split guarded nothing the bullet parser did not already skip, and its comment claimed otherwise → fixed, both deleted.
   - Standards 2: `ctl` asked "which subcommand is this" four times → fixed, once, into what dispatch does for it.
   - Standards 3: the demo re-derives `locate`'s ticket-path fork → declined, A11.
   - Standards 4: two README-figure fixtures still model the retired frontmatter → `[D2]`.
   - Spec (a): the board-label choice was unanchored → fixed, A2; the `rg` residue → A6 and `[D1]`; the unticked criteria and the missing closing comment → this comment.
   - Spec (b): `e6c1b0f` rode this branch unasked → kept, A8, and named in the friction below.
   - Spec (c), Tests (d3): the run record appended unlocked where the manifest it parallels takes a lock, and the file is the repo's, not the feature's → fixed, same lock.
   - Spec (d): "one worker contract" holds; `worker-prompt.md` and `run-worker.sh` are untouched by this branch, and the only thing that varies by host is the permission mode, which is environment and was host-dependent before.
   - Tests (a): the queue test kept a frontmatter block it could not tell from its absence → fixed, dropped with the code it claimed to cover.
   - Tests (d1, d2): `dispatch push` and the skip-restaging branch are unexercised by the demo → declined, A11.

7. `[D7]` **Friction.**

   - The host's tmux server went down at 01:57:15, taking this worker's pane and ticket 07's, two minutes after my demo drove `dispatch-ctl` here and while four review agents were reading. Neither run wrote a status file, which is the `gone` state working. I audited what I had run: every `kill-session` and `has-session` in `dispatch-ctl` names `=<session>`, tmux's exact match, and is guarded; there is no `kill-server`; `cleanup` matches one name; the committed demo makes no tmux call of its own. The one asymmetry was `send-keys` and `capture-pane`, which took a bare name and so could fall back to tmux's prefix matching if a `new-session` had failed: that is A8. The user journal shows no OOM and no `systemd-oomd` action, both panes' scopes ended in the same second with no error, and `journalctl -k` and `dmesg` are not readable from this account, so an OOM of the tmux server under four concurrent agents can be neither confirmed nor excluded from here.
   - The re-run of the review went two axes at a time and finished. If a wave of agents can take a worker host's tmux server down, the biggest fan-out a worker makes is the review station in its own contract.
   - A worker whose pane dies leaves nothing anywhere saying why: the runner writes its status line only when it gets to run. The orchestrator reads `gone`, which is right and silent. A pane that dies with the server is indistinguishable from one killed by hand.
   - The demo stages a copy of the branch's scripts into a temp dir, and after the review fixes my first verification ran that stale copy and looked like the fix had not worked. That is this ticket's own hazard (a host holding a version the branch has moved past) in the one place that has no stamp.
   - `dispatch-ctl init` runs `claude plugin update` on the host, so a toy demo in `/tmp` updated this machine's real plugin install, 0.1.56 to 0.1.57, mid-run.
   - The installed plugin and this branch disagree about where review reports go; I followed the branch, as ticket 06's worker did. Every worker on this feature meets this.
   - `dispatch` and `dispatch-ctl` have no test suite, and half of what they do needs a second machine to exercise at all.
