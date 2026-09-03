---
name: ml
description: "Conventions for ML projects: experiment structure, tracking, tensor code, hyperparameter tuning. Use when setting up an ML project, writing or running training experiments, or keeping a run's result as a figure or table."
---

# ML projects

**Every result worth keeping (a figure in a paper or blog post, a table, a run you'll want to rerun or show someone) is one make target with its flags frozen inside.** Reproduction is: hardware + clone + `make install` + `make figure-2a`. The target is the record of which invocation produced the artifact:

```make
figure-2a:
	uv run python -u experiments/train_baseline.py --seed 42 --n-steps 500 --out figures/2a
```

When an exploratory run graduates into a keeper, freeze its invocation as a target. Exploration itself calls the scripts directly, `uv run python -u experiments/<x>.py --seed 1 ...` (`-u` so tmux scrollback streams progress), and stays out of the Makefile: the tracker already records every run's config, so an unfrozen invocation is never lost; the Makefile holds the runs worth reproducing, by someone else or by you in three months.

## Experiments

- `experiments/` holds standalone tyro scripts, one per experiment (task × method): the browsable index of what's runnable. Never run experiments via `python -c`; a run that isn't a file isn't reproducible.
- Config = nested dataclasses: a `Config` per experiment, shared pieces (`WandbConfig`, `CheckpointConfig`, optimizer unions like `AdamConfig | SGDConfig`) in the package; entrypoint `tyro.cli(main, config=(tyro.conf.OmitArgPrefixes,))`.
- **Everything you might sweep or ablate is a CLI flag**, never hardcoded.

## Tracking

- wandb, as a nested `WandbConfig` dataclass; enable/disable via `mode="online" if cfg.wandb.enabled else "disabled"` at `wandb.init`; never `if wandb_enabled:` checks scattered through the code.
- Every run logs to wandb, through the experiment scripts; improve the infrastructure rather than bypassing it. The exception is a true smoke test, and the test for that label is: could it run in CI or as a pre-commit hook? Anything past that (real cycles, behavior you'll look at) is a run, and untracked runs are cycles spent on results that evaporate.
- `checkpoints/`, `logs/`, `wandb/` gitignored.

## Tensor code

- **einops strongly preferred** for rearranges/reductions; **einx** where einops runs out (a more expressive einops: general indexing, broadcasting, and elementwise ops in the same named-axis notation).
- Runtime shape checking: `torch-einops-utils` (lucidrains, on Codeberg) ships `shape`/`assert_shape`: einops-syntax validation (`s = shape(t, 'b s d'); s.b`) with no annotation machinery; jaxtyping + beartype is the annotation-based alternative (needs ruff `ignore = ["F722"]`). Pick per project. `torch-einops-utils` is also worth raiding for small tensor utilities before writing your own.
- Model files end in a `__main__` smoke check (tiny-dim instantiation, one dummy forward pass, shape/finiteness asserts), cheap enough for CI or a pre-commit hook, so the cheap breakages surface before a real run pays for them.
- ruff line-length 120.

## Hyperparameter tuning

`RobertTLange/autotune`: agent-assisted Optuna via `npx -y @roberttlange/autotune run experiments/<x>.py --trials N`: it proposes the search space from the script, confirms it with you, and runs trials without touching the file. Tyro scripts printing a metric line are already compatible. No YAML sweep configs.

Setup step: install its agent skill into the project with `npx -y skills add RobertTLange/autotune --skill autotune --agent claude-code -y`.
