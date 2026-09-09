# Python

- uv throughout: `uv init`, `uv add`, dependency groups (`dev` = test + lint tools); `uv_build` as the build backend if it's a package.
- **uv is the version oracle**: never trust memory for "latest", never hand-pin from it: `uv add` resolves latest by construction, `uvx <tool>@latest` runs the current release of ruff/ty/pre-commit, `uv python install` fetches the latest stable Python, `uvx pre-commit autoupdate` pins hook revs to their newest tags (rev-pinned, so the diff shows exactly what moved; review it).
- `requires-python`: latest stable; ML projects take what torch and friends support, typically one behind.
- Makefile from [assets/Makefile](assets/Makefile): the core targets wired to uv, plus the publishing pattern: `release-*` bumps `pyproject.toml`, commits, tags; `publish` builds, `uv publish`es, pushes with tags, and cuts a `gh release` with notes from the commit log.
- CLIs use tyro; load `/mx:tyro-cli` before writing one.
- ML project → load `/mx:ml`.
- Ruff's complexity rule is off by default: `select` gains `C901` and `[tool.ruff.lint.mccabe] max-complexity = 10`, the number a project raises or lowers for itself.

## Testing

- `uv add --group dev hypothesis`, and `tests/properties/` for the checks that run over generated inputs (`/mx:testing`). Hypothesis is the only testing dependency the project takes on: harden runs mutmut and coverage from its own environment, so neither belongs in the dev group.
- Hypothesis takes two profiles in `tests/conftest.py`, picked up with `settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))`: `harden`, so a mutation run costs a small example budget instead of the full one, and `fuzz`, the budget `make fuzz` runs until you stop it. Hypothesis keeps what either one finds in `.hypothesis/`, and the ordinary suite replays it from there.

  ```python
  settings.register_profile("harden", max_examples=25, deadline=None)
  settings.register_profile("fuzz", max_examples=5000, deadline=None)
  ```

- mutmut's config, in `pyproject.toml`, is what scopes `make harden`:

  ```toml
  [tool.mutmut]
  source_paths = ["src/<package>/"]
  pytest_add_cli_args_test_selection = ["tests/"]
  mutate_only_covered_lines = true
  ```

- `mutants/`, `.coverage` and `.hypothesis/` are gitignored, and `[tool.pytest.ini_options] testpaths = ["tests"]` keeps pytest out of the copies of the suite that mutmut leaves in `mutants/`.
- `COVERAGE_CORE=sysmon` wherever else coverage is collected (CI, a local `--cov` run); harden's `--help` says why it is the tracer to pin.
- `make fuzz` needs nothing beyond hypothesis. Coverage guidance is the optional upgrade: `uv add --group dev hypofuzz` where its non-commercial licence fits the project, and the target uses it as soon as it imports; where the licence does not fit, Atheris drives the same property tests through Hypothesis' `fuzz_one_input`.
