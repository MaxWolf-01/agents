# Python

- uv throughout: `uv init`, `uv add`, dependency groups (`dev` = test + lint tools); `uv_build` as the build backend if it's a package.
- Latest released Python, latest ruff / ty / pre-commit — **verify current versions** (PyPI or GitHub releases) rather than trusting memory, and pin what the project pins.
- Makefile from [assets/Makefile](assets/Makefile): the core targets wired to uv, plus the publishing pattern — `release-*` bumps `pyproject.toml`, commits, tags; `publish` builds, `uv publish`es, pushes with tags, and cuts a `gh release` with notes from the commit log.
- CLIs use tyro — load `/mx:tyro-cli` before writing one.
