---
status: proposed
---

# The dispatch scripts get a test, and the demo becomes one

Cut from the whole-feature review of one-flow (Tests axis, D6 and D7): the feature rewrote 424 lines of `dispatch` and `dispatch-ctl` and `make test` reaches none of it. The one driver is `agent/show/host-per-spawn/demo.sh`, which nothing runs automatically, which stubs the runner rather than the harness, and which therefore checks the shipped `run-worker.sh` against a copy of itself. The whole-feature pass then introduced a variable collision in `copy_to` that only a demo run caught, by hand.

## What to build

Three rungs, cheapest first, and the ticket can stop at any of them where the next costs more than it returns.

1. `make check` runs `demo.sh` behind a `command -v tmux` guard, so a machine without tmux skips it with a line saying so.
2. A test over the pure text functions of both scripts, each of which is text in and text out with its oracle in the script's own header comment: `short`, `scratch_dir`, `host_of`, `hosts_used`, `forget_run`, `range_of`, `notes_of`. `range_of` is the sharpest: it writes a range into a ticket's `diff:` frontmatter and commits it, so `merge^1` becoming `merge^2` puts a permanently wrong range on a review page with nothing to notice.
3. The demo stubs `claude` on `PATH` instead of stubbing the runner, so the shipped `run-worker.sh` is what runs and its log-then-status contract is what gets checked; and `ssh localhost` stands in as the second host, which turns `push_to`'s push arm, `stage`'s scp arm and `dispatch push`'s partial-failure exit status from unexercised into exercised on one machine. Note that a tmux pane inherits the tmux server's environment rather than the client's, so a `PATH` stub needs checking against a server that is already running.

## Acceptance criteria

- [ ] `make check` runs the demo where tmux exists and says so where it does not.
- [ ] Each text function has a test whose expectation comes from the script's header, and a mutation of that function fails it.
- [ ] Whatever rung the ticket stops at, the closing comment names what stays unexercised and why.
- [ ] Demo in the closing comment: the suite run, and one mutation per rung shown failing.

## Comments

The figures-and-demos feature (ticket 04, 2026-09-16) deletes `agent/show/host-per-spawn/demo.sh` under the rule that a show directory retires with its work; `git log --diff-filter=D -- agent/show/host-per-spawn` finds it. Rung 1 restores it from history under a home that lasts (`tests/` beside the scripts, or `docs/`), never back under `agent/show/`.

**2026-09-22** The whole-feature review of figures-and-demos (`6c9ce66..5a322f6`, Tests axis) measured what rung 1 would buy. The feature adds 85 lines to `dispatch` (`demo_names`, `holds_ticket`, `not_staged`, `stage_demo`, `unstage_demo`, and three call sites) whose only driver is `agent/show/figures-and-demos/03-landing-demo/demo`, which nothing runs and which the retire rule deletes with the feature: the same loss `host-per-spawn/demo.sh` already took. Two mutations were demonstrated surviving that driver. Removing `unstage_demo`'s `git worktree remove` leaves it green, because the demo drives `host=local` throughout, where the worker's own cleanup removes the same worktree first; rung 3's second host, or an assertion through `dispatch fetch` where no cleanup precedes it, is what discriminates. And every `not_staged` arm is unexercised, so flipping the `100755` and `*)` cases in `stage_demo`'s mode check stages a non-executable demo with nothing noticing. Three more cases against the same toy repo cover them: a ticket with no demo, one committed `100644`, and a `job` stub without `stage` in its `--help`.

A fourth case the list above does not reach: `job` absent from PATH entirely, which the staging guards separately from a `job` whose `--help` has no `stage`. It needs a PATH without the demo's shim rather than a shim with a different `--help`, and `03-landing-demo/demo` refuses to start without `job` at all.

**2026-09-22** Ruled by the user on review-launcher's D5: rung 2 covers `mx/skills/code-review/review` too, whose text functions `touches`, `bullets` and `render` are text in and text out like the ones above and have no test; that ticket checked the script through `--help` alone. The script exists once review-launcher merges.
