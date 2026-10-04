# Python

- uv throughout: `uv init`, `uv add`, dependency groups (`dev` = test + lint tools); `uv_build` as the build backend if it's a package.
- **uv is the version oracle**: never trust memory for "latest", never hand-pin from it: `uv add` resolves latest by construction, `uvx <tool>@latest` runs the current release of ruff/ty/pre-commit, `uv python install` fetches the latest stable Python, `uvx pre-commit autoupdate` pins hook revs to their newest tags (rev-pinned, so the diff shows exactly what moved; review it).
- `requires-python`: latest stable; ML projects take what torch and friends support, typically one behind.
- Makefile from [assets/Makefile](assets/Makefile): the core targets wired to uv, plus the publishing pattern: `release-*` bumps `pyproject.toml`, commits, tags; `publish` builds, `uv publish`es, pushes with tags, and cuts a `gh release` with notes from the commit log.
- CLIs use tyro; load `/mx:tyro-cli` before writing one.
- ML project → load `/mx:ml`.
- Ruff's complexity rule is off by default: `select` gains `C901` and `[tool.ruff.lint.mccabe] max-complexity = 10`, the number a project raises or lowers for itself.

## Testing

- Property tests (`/mx:testing`) use Hypothesis, added to the dev group with the first one; `.hypothesis/` is gitignored.
- A project on SQLAlchemy's async engine sets `[tool.coverage.run] concurrency = ["thread", "greenlet"]` for its coverage runs (CI, a local `--cov`), or coverage's default tracer records nothing after an `await` into the engine and warns about nothing.
