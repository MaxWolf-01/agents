---
name: permissions-review
description: Review and update Claude Code's auto-approved command allowlist based on Bash commands that triggered permission prompts in recent sessions.
disable-model-invocation: true
---

# Permissions Review

Scan recent sessions for Bash commands that triggered permission prompts, then recommend and apply allowlist additions. Reduce friction for read-only / benign operations; keep state-modifying commands gated. The review is complete when every signature the scanner reports has landed in exactly one bucket: allowlisted, rejected, or raised with the user.

The scanner's `--help` says how Claude Code matches a command (per segment, with a built-in read-only set that bypasses settings.json) and what follows for the allowlist. Its copy of the built-in set goes stale between Claude Code versions: settle any doubt by **probing**, running the command in a live session. Running unprompted while absent from settings.json puts it in the built-in set.

## Safety bar

- **Allowlist**: pure reads, diagnostics, type checkers, build checks, DNS lookups, log viewers. Commands where accidental execution causes zero harm.
- **Never allowlist state mutations**: `git add/commit/push/reset/checkout/stash`, `docker exec/stop/rm/run/build`, `rm/mv/cp`, `sed -i`, file writes, database mutations, `npm install`, `uv add/sync`, `pip install`. Anything that modifies state, even benignly. (`mkdir -p *` and `chmod +x *` are standing exceptions the user granted deliberately; leave them.)
- **Never allowlist arbitrary code execution**: a wildcard on anything that runs code is equivalent to allowing everything, however read-only it looks. Interpreters and shells (`python`, `node`, `bash`, `eval`), package runners, task-runner wildcards (`make *`, `npm run *`, `cargo run *`), `gh api *` without `-X GET`. An exact invocation is fine (`Bash(make check)`); the wildcard is not. Standing exceptions in the global allowlist (`uv run *`, `uvx *`) are deliberate: keep them, don't widen them, don't add new ones without the user.
- **Judgment calls**, raise with the user:
  - `duckdb` / `sqlite3`: can write, but often used for analytics reads only. Project-local if allowed.
  - `bash <script>`: depends entirely on script content. Usually skip.
  - Project-specific `make` targets: safe if read-only, but varies. Always project-local, always exact.
  - `ssh * <command> *`: globs span spaces and a quoted remote command is one segment, so this matches any ssh call with that word anywhere in its remote command line (`ssh host docker exec $(docker ps -q) evil` passes `ssh * docker ps *`). A read-only-looking ssh pattern is a code-execution pattern.

## Process

### 1. Identify settings files

Global settings (always applies): `~/.claude/settings.json`. If this is a symlink (dotfiles), note the canonical path for editing.

Project-level settings (current project only): `<project-root>/.claude/settings.json`.

Read both to understand what's already allowed.

### 2. Run the scanner

```bash
uv run <skill-dir>/scripts/test_scan_unapproved.py
uv run <skill-dir>/scripts/scan_unapproved.py \
  ~/.claude/projects/ \
  <global_settings_path> [<project_settings_path>] \
  --days <N>
```

The tests cover the shell parsing the scanner depends on. They take a second; a failure means the numbers below are fiction.

`~/.claude/projects/` is the right default: friction rarely stays inside one project. Narrow to one project's directory when asked (`--help` names it).

Read `--show-auto-approved` when the blocked list looks suspiciously short, and after a Claude Code upgrade.

### 3. Categorize

Spot-check the top few entries against the safety bar: one that looks obviously harmless means the built-in set has drifted, which `--show-auto-approved` confirms.

Drop one-offs (fewer than ~3 occurrences) unless clearly recurring across projects, and cap recommendations at ~20 so the user can skim. Then place every remaining signature in one bucket of the safety bar and present a table: signature, count, bucket, one-line rationale.

### 4. Apply changes

Split additions:
- **Global** (`~/.dotfiles/claude/settings.json` or wherever the canonical source is): universal read-only commands useful across all projects.
- **Project-local** (`<project>/.claude/settings.json`): project-specific make targets, domain tools.
- **Clean up local**: remove local entries already covered by global, and promote local entries that are clearly project-agnostic.

Insert new entries in the appropriate section of the JSON, maintaining the existing grouping style (basic commands, search tools, nix, system, dev tooling, git, gh, ssh, docker). Preserve existing entries; de-duplicate; don't touch `permissions.deny` or other settings fields.

Format: `"Bash(<command_pattern> *)"`; the `*` at end matches any trailing arguments. Globs span spaces, so a `*` matches across argument boundaries rather than within one argument.

**Gotcha: trailing `*` requires at least one argument.** `"Bash(git status *)"` matches `git status -s` but NOT bare `git status`. For commands commonly called without arguments, add BOTH the bare and `*` variants:
```json
"Bash(git status)",
"Bash(git status *)",
```

### 5. Commit

Commit each settings file to its respective repo with a descriptive message.
