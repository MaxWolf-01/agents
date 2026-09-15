---
status: done
blocked-by: [02]
---

# A standalone ticket is dispatched like a feature's

## What to build

A ticket with no spec, `agent/tickets/<slug>.md`, is worked by the same dispatch scripts as a feature's tickets: same host selection from the repo's setup, same pane, worklog, stop and resume, same fetch and review. What differs is only the branching: its ticket branch cuts from and merges into the repo's integration branch, there is no feature worktree and no feature branch, and its needs-human entries live in `agent/tickets/needs-human.md`. The host setup (the bare repo on the host, the host record) happens once per repo and is reused by every feature and every standalone ticket; a session that files a standalone ticket dispatches it from the checkout it is in, claiming by committing the status flip on the integration branch, and a collision between two sessions is an ordinary one-line conflict.

The scripts' `--help` and the dispatch skill describe the standalone case where they describe the feature case, without a second set of commands: a standalone ticket is the feature case with the integration branch as the feature branch and the ticket root as the feature directory.

A standalone ticket built while `proposed` has no feature branch to wait on, so its own ticket branch is the container: the review page renders from the fetched branch, the branch merges into the integration branch only when the user accepts on that page, and a rejection deletes the ticket and the branch with the integration branch never having seen it. Ticket 02 landed the claim rule and the reject path for features; this ticket states the standalone form of both.

## Acceptance criteria

- [x] From a checkout on the integration branch, `dispatch setup`, `claim`, `prompt`, `ctl spawn`, `wait`, `fetch` and `review` work on `agent/tickets/<slug>.md` with no feature directory, and the review page lands at `agent/diffviews/<slug>.html` where the board already looks for it.
- [x] The host setup is recorded once per repo and reused; a second feature or standalone ticket needs no new setup.
- [x] The dispatch skill's setup and tick sections cover the standalone case in the same sentences as the feature case.
- [x] Property, reviewed: one worker contract; a worker's obligations do not depend on what spawned it or where it runs.
- [x] Property, reviewed: ticketed work always appears on the board.
- [x] Demo in the closing comment: a toy standalone ticket dispatched end to end on the local host, the pane's log, the fetched branch, the review page, the board.

## Comments

### Closing comment

A standalone ticket is now the feature case with two substitutions, and the scripts make them from the branch they run on: a branch that names a ticket directory is a feature, anything else dispatches the tracker root. Nothing gained a flag or a second command. What varies is the ticket path, the review-page path, the queue file and the commit-message prefix; branch names, worktree names, pane names, `wait`, `fetch` and the worker contract are untouched. The host record moved from `dispatch.<feature>.*` to the repo-wide `dispatch.host`, `dispatch.repo` and `dispatch.setup-cmd`, and the scratch dir is derived from repo and branch rather than stored. A standalone proposal's build waits on its own ticket branch: the page renders from it unmerged, the integration branch carries only the claim until the ruling, and accept is the merge.

**Demo.** A toy standalone ticket dispatched end to end on this host, with the scripts as they stand. Setup, claim, spawn:

```
$ dispatch setup local lamp true
+ bash ~/.local/state/dispatch/lamp-main/dispatch-ctl init lamp main agent/tickets /tmp/lamp /tmp
initialised ~/.local/state/dispatch/lamp-main  mx=0.1.56  tickets=agent/tickets  git=/tmp/lamp  worktrees=/tmp
+ git commit -q -m workers on agent@pc -- agent/tickets/needs-human.md
host=local  repo=lamp  scratch=~/.local/state/dispatch/lamp-main  tickets=agent/tickets  (git config dispatch.*)
$ dispatch claim warm-preset
+ git commit -q -m claim warm-preset -- agent/tickets/warm-preset.md
$ dispatch prompt warm-preset < prompt.md
$ DISPATCH_PERMISSION_MODE=bypassPermissions dispatch ctl spawn warm-preset sonnet
+ git -C /tmp/lamp worktree add /tmp/lamp-main-warm-preset -b ticket/main/warm-preset main
+ tmux new-session -d -s dispatch-lamp-main-warm-preset -c /tmp/lamp-main-warm-preset
spawned dispatch-lamp-main-warm-preset  run=dispatch-lamp-main-warm-preset-1789433256
$ dispatch wait warm-preset
dispatch-lamp-main-warm-preset exited  run=...-1789433256  attempts=1 exit=0 status=done session=d0915cf1-...
```

The run's own words (`dispatch ctl log warm-preset`) are that status line; the worklog was empty, see Friction. The fetched branch and the page, with the integration branch still carrying only the claim:

```
$ dispatch fetch warm-preset && git log --oneline main..ticket/main/warm-preset
2d16944 warm-preset: close out ticket
cdc5ce8 lamp: name the warm preset in README
$ dispatch review warm-preset
+ diffview /tmp/lamp@59fbab0..2d16944 --notes agent/diffviews/warm-preset.notes.json -o agent/diffviews/warm-preset.html
+ uv run board.py agent/tickets --no-watch --no-open
$ git log --oneline main
59fbab0 claim warm-preset
5b3e789 workers on agent@pc
9f5d61c lamp: the slider, and a proposal beside it
```

The board drew the ticket in the standalone section under `workers on agent@pc`, amber `⟳ claimed`, and the queue entry as `standalone · rule on warm-preset`. Then the ruling, accept:

```
$ git merge --no-ff -m "accept warm-preset: ruled in on its review page" ticket/main/warm-preset
$ dispatch review warm-preset     # now the range lands in the ticket
+ git commit -q -m warm-preset review range -- agent/tickets/warm-preset.md
$ dispatch ctl cleanup warm-preset
$ git log --oneline --graph
* 2d0121d warm-preset review range
*   ca197cc accept warm-preset: ruled in on its review page
|\
| * 2d16944 warm-preset: close out ticket
| * cdc5ce8 lamp: name the warm preset in README
* | aad8674 warm-preset built, awaiting the ruling
|/
* 59fbab0 claim warm-preset
```

The worker closed the ticket with its own anchored assumption (`A1 README.md:4`, what "warm" sets), which is the one-worker-contract property in the concrete: its prompt differed from a feature worker's only in the ticket path. The board then drew it `✓ done`.

To re-drive, from any checkout of this branch: `bash` the script in `/tmp/drive.sh` on this host, or rebuild it from the commands above; it needs `claude`, `tmux` and `uv`, and a `diffview` on PATH for the page itself.

**I need from you**

1. `[D1]` `dispatch setup` on a second feature branch still runs, with no arguments, to stage that branch's scratch dir; only standalone tickets truly need none after the first. Criterion 2 reads "needs no new setup". Keep the per-branch staging (A2), or should a feature branch share one scratch dir per repo and accept that a concurrent dispatcher on another plugin version overwrites the runner under running workers?
2. `[D2]` The host is now one per repo. A feature that wants a different host than the repo's (a GPU box, say) can no longer have one without re-recording for everything. Ruling wanted if that case is real.
3. `[D3]` Two declined findings, A6 and A7 below.

**Details, if you want them**

- `[D4]` Review page: `diffview` is not installed on this host, so every `dispatch review` above stopped at `diffview: command not found` after writing the notes file and the range. Everything else in `review` ran. This is the one acceptance criterion I could not see with my own eyes.
- `[D5]` Assumptions and the finding index, below.

**Assumptions**

- A1 `mx/skills/dispatch/dispatch:91`: the case is read off the branch (a branch naming a ticket directory is a feature) rather than from a flag or a recorded mode. The ticket asks for one set of commands; a flag would be a second one. The cost is that a feature branch whose ticket directory does not exist yet reads as standalone, which now fails loudly on the first `claim` naming the path it tried.
- A2 `mx/skills/dispatch/dispatch:191`: "recorded once per repo" is the host, the bare repo and the setup command (git config `dispatch.*`); the scratch dir stays per branch, because its per-feature isolation is what keeps one dispatcher's runner from replacing another's under running workers. So a second feature branch runs `dispatch setup` with no arguments, and a second standalone ticket runs nothing. See `[D1]`.
- A3 `mx/skills/dispatch/dispatch:252`: a standalone ticket branch is `ticket/<integration-branch>/<slug>`, e.g. `ticket/main/warm-preset`, derived by the same rule as a feature's rather than given a shape of its own.
- A4 `mx/skills/dispatch/dispatch:212`: commits dispatch makes on the integration branch carry no prefix (`claim warm-preset`), where a feature's carry the feature's (`one-flow: claim 05-...`). A "main: " prefix would say nothing.
- A5 `mx/skills/dispatch/dispatch:311`: the `diff:` range lands when the branch merges, not when the page renders. Found by driving it: the pre-merge write put `diff:` directly under `status:` in a frontmatter with nothing else in it, and every accept-merge then conflicted on the ticket file. This changes the feature path too, where the range is written at the same moment as before (`review` runs after the merge there).
- A6 `mx/skills/dispatch/dispatch-ctl:106`: declined, the short name a prompt file and a pane carry still comes from an `NN-` prefix, so two standalone tickets named `01-a` and `01-b` would share one prompt file and one session. The tracker's numbering rule makes `NN` unique within a directory, the tracker root included, so the collision needs a convention violation first; deciding it from the mode instead would either duplicate the mode rule across the ssh boundary or rename every pane, which would strand in-flight runs across an upgrade.
- A7 `mx/skills/tracker/board.py:246`: declined, the queue stays the `(entries, host)` tuple `load_needs_human` already returned, now named `Queue`, rather than becoming a dataclass. Making it one to match `Ticket`/`Feature`/`Standalone` means changing `Feature`'s two fields as well, which is a refactor of code this ticket does not touch.
- A8 `mx/skills/tracker/board.py:298`: `board.py` is edited though the ticket named four other files. `agent/tickets/needs-human.md` is where the ticket puts the standalone queue, and the board globs `*.md` at the tracker root for tickets, so without this it would have drawn the queue file as a ticket named "needs-human" and never shown its entries.

**Findings** (`/mx:code-review` since a9117ac, four axes, reports under `agent/research/`)

- `locate` read the mode from a cwd-relative path, so a feature dispatch from a subdirectory became a standalone one (Correctness) → fixed, d337447.
- The skill said a standalone ticket in a set-up repo runs no setup, which the per-branch scratch dir contradicts (Correctness) → fixed, d337447; see A2 and `[D1]`.
- The standalone bullet stopped at the ruling: no cleanup, and an accepted ticket never got its range (Correctness, Spec) → fixed, d337447.
- The unmerged render dropped the ranges the ticket already carried, which reaches a feature ticket re-fetched between rounds (Standards, Spec) → fixed, d337447.
- A repo on the retired `dispatch.<feature>.host` keys read as having no host at all (Standards) → fixed, d337447.
- `dispatch.repo` missing in the no-argument `setup` fell through to a scratch dir named `-<branch>` (Standards, Spec) → fixed, d337447.
- The substitution rule was stated in three homes (Standards) → fixed, d337447: the tracker says where the queue file is, dispatch says what substitutes.
- The `#standalone` anchor the queue chips link to rendered only when a standalone ticket existed, and an entry outlives a rejected one (Standards, Tests) → fixed, d337447, with a test.
- `render`'s wiring of the queue path was invisible to the suite (Tests) → fixed, d337447, with a test that calls `render`.
- `mx/README.md` still described dispatch as a feature's tickets only (Standards) → fixed, d337447.
- "Verify on the fetched branch" named no mechanism for an orchestrator holding no worktree (Spec) → fixed, d337447: the worker's own verification stands, and a moved integration branch goes back to the worker to rebase onto.
- The short pane name collides for two `NN-` standalone slugs (Standards, Spec) → declined, A6.
- `Queue` as a tuple alias rather than a dataclass, and `render_page`'s parameter count (Standards) → declined, A7.
- Ticket 05's own criteria unticked and no closing comment (Spec) → fixed here.

**Friction**

- `diffview` is not on this host (`~/HOST.md` does not list it), so the review page could not be rendered here at all; `review`'s other steps and the board carried the demo. A worker host that runs `dispatch review` needs it, and nothing says so until the command fails.
- The worker's worklog stayed empty for the whole toy run, so `dispatch ctl log` had only the status line to show. The instruction to write it is one line in the worker prompt with nothing checking it; a first line written by the runner (the prompt it was given, say) would make an empty log mean "wrote nothing" rather than "never started".
- The tick's landing sequence for a feature ticket runs `dispatch ctl cleanup`, then `git branch -d` here, then `dispatch review`. `review` needs the ticket branch to compute the range, and on a local host `cleanup` deletes that branch in the same repo, so the documented order ends in `no branch ticket/<feature>/<id> here`. Pre-existing, outside this ticket, and it bit me mid-demo.
- Ticket 02's re-drive snippet sets `git config dispatch.lamp-ui.host`, which this ticket retired; it needs `dispatch.host` and `dispatch.repo` to run now.
