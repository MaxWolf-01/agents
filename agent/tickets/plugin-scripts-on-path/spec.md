---
status: confirmed
---

# Plugin scripts on PATH

## Problem Statement

`make harden` in a project's Makefile finds `harden.py` by globbing `~/.claude/plugins/cache/*/mx/*/skills/testing/`. That puts a harness path into a project file, ties the plugin to one harness's cache layout, and hides the script from a shell: `dispatch`, `dispatch-ctl` and `harden.py` have `--help` worth reading, and none of them is on `PATH`. The Makefile template and the dispatch skill's setup are the two callers.

Raised from review comment C15 on the testing-workflow implementation; left as the glob for that feature.

## Solution

The plugin ships a `bin/` directory, and the harness does the rest: Claude Code (since 2.1.91) adds every enabled plugin's `bin/` to the Bash tool's `PATH`, so inside any Claude session, a worker on the host included, `harden`, `dispatch` and `board` are bare commands. A project's Makefile calls `harden` by name and never sees the cache. The shell gets the same commands through one line in the dotfiles that puts the newest installed plugin version's `bin/` on `PATH`.

## User Stories

1. As a project maintainer, I want `make harden` to run without my Makefile naming any harness's cache layout, so that the Makefile works on every machine the plugin is installed on and says nothing about how it got there.
2. As an agent in a Claude session, I want `harden --help`, `dispatch --help` and `board --help` to answer by bare name, so that a skill can point at the help instead of a path assembled from the skill directory.
3. As a dispatch orchestrator, I want to type `dispatch setup ...` rather than `bash <skill-dir>/dispatch setup ...`, so that the command reads the same in the skill, the transcript and the shell.
4. As a dispatch worker on the worker host, I want the ticket's `make harden` and any bare plugin command to resolve there without a dotfiles install, so that a worker user with only `claude` and the plugin has what its tickets need.
5. As max at a terminal, I want `harden --help` and `dispatch --help` to work in a plain shell, so that reading a script's reference does not require starting a session.
6. As a plugin developer with the cache version symlinked to the checkout (README, Local development), I want the bare commands to run the checkout's scripts, so that an edit is live without a release.
7. As max, I want `HARDEN=<path> make harden` to keep pointing at another checkout, so that a harden fix can be tried on a project before it ships.

## Properties

- A project file (Makefile, config) never names the harness or its plugin cache.
- Every command the plugin puts on `PATH` answers `--help` with exit 0.
- Nothing in `bin/` runs from the plugin directory in a way that writes state there; a script that keeps state beside itself is never on `PATH`.

## Decisions

- **The harness owns the `PATH` inside sessions**. Claude Code appends each enabled plugin's `bin/` to the Bash tool's `PATH` (verified live on 2.1.266: this session's `PATH` already ends with the mx cache's `bin/`, and a probe script dropped there ran by bare name). No install step, no hook, no shim outside the plugin. Worker sessions run `claude` with the plugin installed, so they get it the same way.
- **`bin/` holds shims, the scripts stay beside their skills**. Each shim is a two-line executable that resolves its own real path (through the development symlink too) and execs the script next to the skill that documents it. The scripts keep their siblings (`mutmut_runner.py` beside `harden.py`, `run-worker.sh` beside `dispatch-ctl`), their tests, and the `dispatch setup` copy step that ships `dispatch-ctl`, the runner and the worker prompt to the host's scratch dir unchanged.
- **Three commands: `harden`, `dispatch`, `board`**. `dispatch-ctl` stays off `PATH`: it keeps its state (`config`, `manifest`, run files) beside itself and is meant to run from a feature's scratch dir; on `PATH` it would write that state into the plugin cache the first time someone ran it by hand. Its reference is reachable as `dispatch ctl --help` once a feature is set up, and the `dispatch` help says so.
- **The Makefile template calls `harden` by name**. `HARDEN ?= harden`; the target runs `$(HARDEN) $(ARGS)`, and when the command is missing it says where it comes from (a Claude session with the mx plugin, or the plugin's `bin/` on `PATH`) instead of failing on a bare `command not found`. The `HARDEN=<path>` override stays.
- **Skills name the bare commands**. Dispatch: `dispatch` replaces `bash <skill-dir>/dispatch`. Tracker: `board agent/tickets --watch` replaces `uv run <skill-dir>/board.py agent/tickets --watch`. Testing: `harden --help` replaces `uv run harden.py --help`. Inside the `dispatch` script itself the call to the board keeps its relative path: the script should not depend on its own `PATH` entry.
- **The shell**. One line in the dotfiles' `zsh/exports`, beside the `~/.claude/local` line that already puts a harness path on `PATH`, adding the newest installed mx version's `bin/`. Evaluated at shell start, so it follows `claude plugin update` with no hook. The line, from the round's demonstration (the `n` qualifier is load-bearing: lexical sort picks 0.1.9 over 0.1.40):

  ```zsh
  path=(~/.claude/plugins/cache/MaxWolf-01/mx/*/bin(Nn/[-1]) $path)
  ```

  Machines without the dotfiles (worker users on pc) don't get it and don't need it: their commands run inside sessions.
- **Worker host: nothing changes**. `dispatch setup` keeps copying `dispatch-ctl`, `run-worker.sh` and `worker-prompt.md` into the per-feature scratch dir, which is what pins one plugin version per run; workers get the bare commands from the harness.
- **Existing project Makefiles**: only the template carries the glob today (checked every Makefile under `~/repos`); nothing to migrate.

## Testing Decisions

- Seam: the plugin's `make check`, which every `release-*` target depends on. It runs each file in `bin/` with `--help` and fails on a nonzero exit. Oracle: the Property above. Prior art: the manifest parse checks in the same target.
- `harden`'s own tests keep driving `harden.py` by path; the shim adds nothing they should know.
- Properties: "no project file names the cache" is **reviewed** (Spec axis); "`--help` exits 0" is **executable** at `make check`; "no state written into the plugin dir" is **reviewed**.

## Out of Scope

- **A published package run through `uvx`**: a second release path beside the plugin's, a version that can drift from the installed plugin's, and `dispatch` is bash, not a Python entry point.
- **Symlinks written into `~/.local/bin` by the pre-push hook or `ccupdate`**: state outside version control, per machine, stale the moment a version dir moves; the harness already does the equivalent for sessions.
- **Moving the scripts into `bin/`**: their tests and helper modules would land on `PATH` as autocomplete noise or split from the script, and `dispatch setup`'s copy paths would change for nothing.
- **`dispatch review` calling `diffview` from the dotfiles**: the plugin already depends on max's `bin/` in that direction; a worker host without the dotfiles cannot render review pages. Real, pre-existing, and a different ticket.
