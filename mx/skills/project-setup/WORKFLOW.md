# Project setup in the mx workflow

- **Reproducible install**: a worker on another machine runs the install command as the first thing in a fresh worktree.
- **Git**: the code repo's `.gitignore` also carries `/agent/`, the agent repo below.
- **The agent repo** (`/mx:tracker`): a git repo of its own at `agent/`, and `agent/repos.toml` where the project's tickets land in repos beside the code repo (`tracker repos --help`). Its own `.gitignore` carries the ephemeral ones (`transcripts`, `sessions`, `diffviews`, `board.html*`, `.serve.*`, `show/**/out`). An existing project whose `agent/` its code repo tracks is split out of a clone of it, never in place: `git clone <repo> <tmp>`, `git -C <tmp> filter-repo --subdirectory-filter agent` (which rewrites that clone's whole history down to the directory, and refuses a clone anything has been done in), then the result becomes the project's `agent/` and the code repo drops the directory and gains the ignore rule in one commit. The ticket history survives; the code repo's does not move.
- **The tracker's hooks**: `tracker hook`, run in the agent repo, installs its commit check and its sync (`tracker check --help`, `tracker sync --help`).
