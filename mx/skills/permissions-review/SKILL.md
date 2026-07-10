---
name: permissions-review
description: Review and update Claude Code's auto-approved command allowlist based on Bash commands that triggered permission prompts in recent sessions.
disable-model-invocation: true
---

# Permissions Review

Scan recent sessions for Bash commands that triggered permission prompts, then recommend and apply allowlist additions. Reduce friction for read-only / benign operations; keep state-modifying commands gated. The review is complete when every signature the scanner reports has landed in exactly one bucket: allowlisted, rejected, or raised with the user.

## Safety bar

- **Allowlist**: pure reads, diagnostics, type checkers, build checks, DNS lookups, log viewers. Commands where accidental execution causes zero harm.
- **Never allowlist — state mutations**: `git add/commit/push/reset/checkout/stash`, `docker exec/stop/rm/run/build`, `rm/mv/cp/mkdir/chmod`, `sed -i`, file writes, database mutations, `npm install`, `uv add/sync`, `pip install`. Anything that modifies state, even benignly.
- **Never allowlist — arbitrary code execution**: a wildcard on anything that runs code is equivalent to allowing everything, however read-only it looks. Interpreters and shells (`python`, `node`, `bash`, `eval`), package runners, task-runner wildcards (`make *`, `npm run *`, `cargo run *`), `gh api *` without `-X GET`. An exact invocation is fine (`Bash(make check)`); the wildcard is not. Standing exceptions in the global allowlist (`uv run *`, `uvx *`, the `ssh * <read-cmd>` patterns backed by the `ssh-docker-guard` hook) are deliberate — keep them, don't widen them, don't add new ones without the user.
- **Judgment calls** — raise with the user:
  - `duckdb` / `sqlite3` — can write, but often used for analytics reads only. Project-local if allowed.
  - `bash <script>` — depends entirely on script content. Usually skip.
  - Project-specific `make` targets — safe if read-only, but varies. Always project-local, always exact.

## Process

### 1. Identify settings files

Global settings (always applies): `~/.claude/settings.json`. If this is a symlink (dotfiles), note the canonical path for editing.

Project-level settings (current project only): `<project-root>/.claude/settings.json`.

Read both to understand what's already allowed.

### 2. Run the scanner

```bash
uv run <skill-dir>/scripts/scan_unapproved.py \
  <sessions_dir> \
  <global_settings_path> [<project_settings_path>] \
  --days <N>
```

- `<sessions_dir>`: `~/.claude/projects/<project-path-encoded>/` (path encoding: replace `/` with `-`, strip leading slash)
- `--days N`: how far back to scan (default 30, user may request 60+)
- Run with `--help` for full usage

The script reads the actual allowlist from the settings files, so it stays in sync. Output is JSON: `[{signature, count, example}, ...]` sorted by frequency.

### 3. Filter, then categorize

The scanner flags anything not matching the allowlist files — but Claude Code auto-allows many read-only commands internally, and those never prompt, so an entry for them is dead weight. Drop them first:

- **Any args**: `cat`, `head`, `tail`, `wc`, `stat`, `ls`, `echo`, `date`, `diff`, `df`, `du`, `id`, `uname`, `free`, `uptime`, `basename`, `dirname`, `realpath`, `readlink`, `cut`, `tr`, `which`, `type`, `seq`, `sleep`, `nproc`, `strings`.
- **With validated safe flags**: `grep`/`rg`, `fd`, `jq`, `sort`, `uniq`, `find` (blocks `-delete`/`-exec`), `sed` (read-only expressions), `ps`, `lsof`, `pgrep`, `ss`, `tree`, `man`, `file`, `hostname`, `sha256sum`, `md5sum`, `xargs`, `base64`.
- **Zero args only**: `pwd`, `whoami`.
- **All git and gh read subcommands**: `git status/log/diff/show/blame/branch/tag/remote/ls-files/rev-parse/describe/reflog/...`, `gh pr view/list/diff/checks`, `gh issue view/list`, `gh run list/view`, `gh api` (GET), `gh auth status`, ...
- **Docker reads**: `docker ps/images/logs/inspect`.

The set is version-dependent — when unsure whether a command still prompts, test it rather than guessing.

Of what remains, drop one-offs (fewer than ~3 occurrences) unless clearly recurring across projects, and cap recommendations at ~20 so the user can skim. Then place every remaining signature in one bucket of the safety bar and present a table: signature, count, bucket, one-line rationale.

### 4. Apply changes

Split additions:
- **Global** (`~/.dotfiles/claude/settings.json` or wherever the canonical source is): universal read-only commands useful across all projects.
- **Project-local** (`<project>/.claude/settings.json`): project-specific make targets, domain tools.
- **Clean up local**: remove local entries already covered by global, and promote local entries that are clearly project-agnostic.

Insert new entries in the appropriate section of the JSON, maintaining the existing grouping style (basic commands, search tools, nix, system, dev tooling, git, gh, ssh, docker). Preserve existing entries; de-duplicate; don't touch `permissions.deny` or other settings fields.

Format: `"Bash(<command_pattern> *)"` — the `*` at end matches any trailing arguments.

**Gotcha — trailing `*` requires at least one argument.** `"Bash(git status *)"` matches `git status -s` but NOT bare `git status`. For commands commonly called without arguments, add BOTH the bare and `*` variants:
```json
"Bash(git status)",
"Bash(git status *)",
```

For SSH remote commands: `"Bash(ssh * <command> *)"` — the first `*` matches the hostname. Same trailing-`*` caveat applies: `"Bash(ssh * nvidia-smi)"` is needed alongside the `*` variant for bare invocations.

**Gotcha — SSH glob patterns are inherently over-broad.** `ssh * docker ps *` matches ANY SSH command containing "docker ps" anywhere in the string, including `ssh host docker exec $(docker ps -q) evil-cmd`. The `*` wildcards match across the full command, not just individual arguments. This means "read-only" SSH docker patterns can be exploited to run `docker exec/run/stop/rm` over SSH without approval.

Mitigation: the mx plugin includes a `PreToolUse` hook (`hooks/ssh-docker-guard.sh`) that acts as a deny-list — it blocks SSH commands containing dangerous docker subcommands (`exec`, `run`, `stop`, `rm`, `kill`, `build`, `push`, `pull`, `restart`, `update`, `create`) regardless of what the glob allowlist permits. If reviewing SSH docker patterns, verify this hook is active rather than trying to fix it at the glob level.

### 5. Commit

Commit each settings file to its respective repo with a descriptive message.
