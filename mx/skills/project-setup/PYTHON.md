# Python

- uv throughout: `uv init`, `uv add`, dependency groups (`dev` = test + lint tools); `uv_build` as the build backend if it's a package.
- **uv is the version oracle**: never trust memory for "latest", never hand-pin from it: `uv add` resolves latest by construction, `uvx <tool>@latest` runs the current release of ruff/ty/pre-commit, `uv python install` fetches the latest stable Python, `uvx pre-commit autoupdate` pins hook revs to their newest tags (rev-pinned, so the diff shows exactly what moved; review it).
- `requires-python`: latest stable; ML projects take what torch and friends support, typically one behind.
- Makefile from [assets/Makefile](assets/Makefile): the core targets wired to uv, plus the publishing pattern: `release-*` bumps `pyproject.toml`, commits, tags; `publish` builds, `uv publish`es, pushes with tags, and cuts a `gh release` with notes from the commit log.
- CLIs use tyro; load `/mx:tyro-cli` before writing one.
- ML project → load `/mx:ml`.
