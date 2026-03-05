---
name: permissions-review
description: This skill should be used when the user asks to "review permissions", "update allowlist", "check unapproved commands", "what's getting prompted", "audit bash permissions", "reduce prompts", "permission audit", or wants to review and update Claude Code's auto-approved command allowlist based on recent usage.
---

# Permissions Review

Scan recent sessions for Bash commands that triggered permission prompts, then recommend additions to the allowlist. The goal is to reduce friction for read-only / benign operations while keeping write operations and state-modifying commands gated.

## Philosophy

Two permission paradigms exist:

1. **Supervised agents** (current workflow) — work in a shared repo under user oversight. Only read-only, non-destructive commands get allowlisted. Writes, state mutations, and anything that could conflict with parallel agents stays prompted.
2. **Sandboxed agents** — isolated machines with `--dangerously-skip-permissions`, making PRs. No allowlist needed.

This skill is for paradigm 1. The allowlist safety bar:

- **Allowlist**: Pure reads, diagnostics, type checkers, test runners, build checks, DNS lookups, log viewers. Commands where accidental execution causes zero harm.
- **Never allowlist**: `git add/commit/push/reset/restore`, `docker exec/stop/rm/run`, `rm/mv/cp`, `ssh * docker exec/stop/restart`, file writes, database mutations, `npm install`, `pip install`. Anything that modifies state, even benignly.

## Process

### 1. Identify settings files

Global settings (always applies):
```
~/.claude/settings.json
```
If this is a symlink (common with dotfiles), note the canonical path for editing.

Project-level settings (applies to current project only):
```
<project-root>/.claude/settings.json
```

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

### 3. Categorize results

Present results in a table, grouped by safety:

**Safe to allowlist** — pure RO, zero side effects:
- System diagnostics: `df`, `free`, `uptime`, `dig`, `ps`, `id`, `wc`, `stat`, `file`
- Dev tooling: `uv run`, `uvx`, `ty`, `npx tsc`, `npm view`, `make test-*`, `make check`
- Git reads: `git fetch`, `git worktree list`, `git cherry`
- Docker reads: `docker ps`, `docker logs`, `docker inspect`, `docker images`
- SSH remote reads: `ssh * <any-of-the-above>`

**Never allowlist** — state modifications:
- Git writes: `git add`, `git commit`, `git push`, `git reset`, `git checkout`, `git stash`
- Docker writes: `docker exec`, `docker stop`, `docker rm`, `docker run`, `docker build`
- File mutations: `rm`, `mv`, `cp`, `mkdir`, `chmod`, `sed -i`
- Package managers: `npm install`, `uv add`, `uv sync`, `pip install`
- Compound commands (chained with `&&`, `||`, `;`) — these bypass pattern matching anyway

**Judgment calls** — discuss with user:
- `duckdb` — can write, but often used for analytics reads only. Project-local if allowed.
- `sqlite3` — same as duckdb.
- `curl` — can POST/DELETE, but locally already allowed. SSH-tunneled version is consistent.
- `bash <script>` — depends entirely on script content. Usually skip.
- Project-specific `make` targets — safe if RO, but varies. Always project-local.

### 4. Apply changes

Split additions:
- **Global** (`~/.dotfiles/claude/settings.json` or wherever the canonical source is): universal RO commands useful across all projects.
- **Project-local** (`<project>/.claude/settings.json`): project-specific make targets, domain tools.

Insert new entries in the appropriate section of the JSON, maintaining the existing grouping style (basic commands, search tools, nix, system, dev tooling, git, gh, ssh, docker).

Format: `"Bash(<command_pattern> *)"` — the `*` at end matches any trailing arguments.

**Gotcha — trailing `*` requires at least one argument.** `"Bash(git status *)"` matches `git status -s` but NOT bare `git status`. For commands that are commonly called without arguments, add BOTH the bare and `*` variants:
```json
"Bash(git status)",
"Bash(git status *)",
```

For SSH remote commands: `"Bash(ssh * <command> *)"` — the first `*` matches the hostname. Same trailing-`*` caveat applies: `"Bash(ssh * nvidia-smi)"` is needed alongside the `*` variant for bare invocations.

### 5. Commit

Commit each settings file to its respective repo with a descriptive message.
