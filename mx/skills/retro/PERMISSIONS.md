# Permissions: the data and the bar

What the workflow retro's permissions worker reads, and the bar a rule it proposes is held to.

## The data

- **Denials in the digests** are `! DENIED <tool> (<kind>)` lines. `automode-blocked` is the auto mode classifier refusing a call; `permission-rule`, a deny or ask rule of the settings; `user-rejected`, max saying no at a prompt; `interrupted`, max stopping the call. A digest from before the kind was recorded says `denial`.
- **`permissions/<profile>/scan.json`** is `scan_unapproved.py` over the period's Bash calls of the profile's interactive sessions: `would_prompt`, the segments no allowlist rule of the profile covers and Claude Code's built-in read-only set does not approve, by signature and count; `auto_approved`, those the built-in set approves. It reads the profile's own settings alone, so a command a project's `.claude/settings.json` allows is counted as prompting; and under auto mode an uncovered command goes to the classifier rather than to max. The built-in set is version-dependent: a signature under `auto_approved` that the digests show prompting means the scanner's copy is stale.
- **`rules.json`** is each settings file's `permissions` and `autoMode`, as the profile sets them; **`auto-mode.json`**, the auto mode config in effect, the shipped defaults where the profile sets none. Where `auto-mode.failed` stands in its place, the config could not be read.

## The bar

- **Allowlist**: pure reads, diagnostics, type checkers, build checks, DNS lookups, log viewers: commands where an accidental run does no harm.
- **State mutations stay gated**: `git add/commit/push/reset/checkout/stash`, `docker exec/stop/rm/run/build`, `rm/mv/cp`, `sed -i`, file writes, database mutations, `npm install`, `uv add/sync`, `pip install`; anything that changes state, however benign. `mkdir -p *` and `chmod +x *` are standing exceptions max granted deliberately.
- **Arbitrary code execution stays gated**: a wildcard on anything that runs code allows everything, however read-only it looks: interpreters and shells (`python`, `node`, `bash`, `eval`), package runners, task-runner wildcards (`make *`, `npm run *`, `cargo run *`), `gh api *` without `-X GET`. An exact invocation is fine (`Bash(make check)`); the wildcard is not. The global `uv run *` and `uvx *` are deliberate exceptions: kept, never widened, and none added without max.
- **Judgment calls**, proposed with the trade-off named:
  - `duckdb` / `sqlite3`: can write, but mostly used for reads; project-local if at all.
  - `bash <script>`: depends on the script.
  - a project's `make` targets: project-local and exact.
  - `ssh * <command> *`: a glob spans spaces and a quoted remote command is one segment, so this matches any ssh call with that word anywhere in its remote command (`ssh host docker exec $(docker ps -q) evil` passes `ssh * docker ps *`). A read-only-looking ssh pattern is a code-execution pattern.
- **A rule's shape**: `"Bash(<command pattern> *)"`, the trailing `*` matching the arguments, a glob spanning argument boundaries. A trailing ` *` needs at least one argument: `Bash(git status *)` misses bare `git status`, so a command often run bare gets both forms. A rule proposed globally is one every project could use; a project's own goes in its `.claude/settings.json`.
