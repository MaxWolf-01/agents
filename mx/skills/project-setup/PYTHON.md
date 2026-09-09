# Python

- uv throughout: `uv init`, `uv add`, dependency groups (`dev` = test + lint tools); `uv_build` as the build backend if it's a package.
- **uv is the version oracle**: never trust memory for "latest", never hand-pin from it: `uv add` resolves latest by construction, `uvx <tool>@latest` runs the current release of ruff/ty/pre-commit, `uv python install` fetches the latest stable Python, `uvx pre-commit autoupdate` pins hook revs to their newest tags (rev-pinned, so the diff shows exactly what moved; review it).
- `requires-python`: latest stable; ML projects take what torch and friends support, typically one behind.
- Makefile from [assets/Makefile](assets/Makefile): the core targets wired to uv, plus the publishing pattern: `release-*` bumps `pyproject.toml`, commits, tags; `publish` builds, `uv publish`es, pushes with tags, and cuts a `gh release` with notes from the commit log.
- CLIs use tyro; load `/mx:tyro-cli` before writing one.
- ML project → load `/mx:ml`.
- Ruff's complexity rule is off by default: `select` gains `C901` and `[tool.ruff.lint.mccabe] max-complexity = 10`, the number a project raises or lowers for itself.

## Testing

- `uv add --group dev hypothesis hypofuzz`, and `tests/properties/` for the checks that run over generated inputs (`/mx:testing`). Those two are the testing dependencies the project takes on: harden runs mutmut and coverage from its own environment, so neither belongs in the dev group.
- Hypothesis takes two profiles in `tests/conftest.py`, picked up with `settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))`: `harden`, so a mutation run costs a small example budget instead of the full one, and `fuzz`, the budget `make fuzz` runs until you stop it where the project has no HypoFuzz. Hypothesis keeps what either one finds in `.hypothesis/`, and the ordinary suite replays it from there.

  ```python
  settings.register_profile("harden", max_examples=25, deadline=None)
  settings.register_profile("fuzz", max_examples=5000, deadline=None)
  ```

- A property ahead of its seam (`/mx:testing`) is marked `@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 03-<slug>")`, with `raises=AssertionError` where the seam exists and lacks the behaviour; a file whose properties share one lifter sets the mark once as `pytestmark`. A seam's stub is its signature over `raise NotImplementedError`.

- mutmut's config, in `pyproject.toml`, is what scopes `make harden`:

  ```toml
  [tool.mutmut]
  source_paths = ["src/<package>/"]
  pytest_add_cli_args_test_selection = ["tests/"]
  mutate_only_covered_lines = true
  ```

- `mutants/`, `.coverage` and `.hypothesis/` are gitignored, and `[tool.pytest.ini_options] testpaths = ["tests"]` keeps pytest out of the copies of the suite that mutmut leaves in `mutants/`.
- A project with greenlet installed (SQLAlchemy's async engine brings it) names it in the coverage config, or coverage records nothing after an `await` into the engine and warns about nothing; harden refuses to measure until it is set. The value replaces the default rather than adding to it, so `thread` stays in the list:

  ```toml
  [tool.coverage.run]
  concurrency = ["thread", "greenlet"]
  ```
- HypoFuzz is licensed for non-commercial use, which is the user's call per project: ask, and drop the dependency where they rule it a problem. Without it `make fuzz` loops the `fuzz` profile instead, and Atheris drives the same property tests through Hypothesis' `fuzz_one_input` where a project wants coverage guidance anyway.
