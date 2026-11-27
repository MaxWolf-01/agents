---
name: ml
description: "Conventions for ML projects: experiment structure, tracking, tensor code, hyperparameter tuning. Use when setting up an ML project, writing or running training experiments, or keeping a run's result as data and the figure or table drawn from it."
---

# ML projects

**Every result worth keeping (a figure in a paper or blog post, a table, a run you'll want to rerun or show someone) is data, and two make targets with their flags frozen inside: one runs the experiment and writes the data, the other draws the figure or table from it.** Reproduction is: hardware + clone + `make install` + `make results-2a figure-2a`; redrawing is `make figure-2a` alone, on any host, in seconds. The targets are the record of which invocation produced the artifact:

```make
results-2a:
	uv run python -u experiments/train_baseline.py --seed 42 --n-steps 500 --out results/2a

figure-2a:
	uv run python experiments/plot.py results/2a --out figures/2a
```

The data, under `results/<id>/`, is committed when it is small (the run's metrics as JSONL, its log), and kept where the project keeps large files when it is not, with `figure-2a` fetching it from there.
Where the project has no place for large files, ask the user for one: results written to a gitignored directory in a worktree are lost with the worktree.

When an exploratory run graduates into a keeper, freeze its invocation as the pair of targets. Exploration calls the scripts directly, `uv run python -u experiments/<x>.py --seed 1 ...` (`-u` so tmux scrollback streams progress), and stays out of the Makefile, which holds only the runs worth reproducing; the tracker already records every run's config.

## Experiments

- `experiments/` holds standalone tyro scripts, one per experiment (task × method): the browsable index of what's runnable. Every run starts from a file, never from `python -c`, so it can be reproduced.
- Config = nested dataclasses: a `Config` per experiment, shared pieces (`WandbConfig`, `CheckpointConfig`, optimizer unions like `AdamConfig | SGDConfig`) in the package; entrypoint `tyro.cli(main, config=(tyro.conf.OmitArgPrefixes,))`.
- **Everything you might sweep or ablate is a CLI flag**, never hardcoded.

## Tracking

- wandb, as a nested `WandbConfig` dataclass; enable/disable via `mode="online" if cfg.wandb.enabled else "disabled"` at `wandb.init`; never `if wandb_enabled:` checks scattered through the code.
- Every run logs to wandb through the experiment scripts; where the infrastructure is in the way, improve it rather than bypass it. Only a true smoke test goes untracked, and a check is one only if it could run in CI or as a pre-commit hook; anything past that (real cycles, behavior you'll look at) is a run, and its results evaporate untracked.
- `checkpoints/`, `logs/`, `wandb/` gitignored.

## Tensor code

- **einops strongly preferred** for rearranges/reductions; **einx** where einops runs out.
- Runtime shape checking, chosen per project: `torch-einops-utils` (lucidrains, on Codeberg), whose `shape`/`assert_shape` validate in einops syntax (`s = shape(t, 'b s d'); s.b`) without annotations, or jaxtyping + beartype for annotation-based checks (needs ruff `ignore = ["F722"]`). Look in `torch-einops-utils` for a small tensor utility before writing your own.
- Model files end in a `__main__` smoke check (tiny-dim instantiation, one dummy forward pass, shape/finiteness asserts) cheap enough for CI or a pre-commit hook.
- ruff line-length 120.

## Hyperparameter tuning

`RobertTLange/autotune`: agent-assisted Optuna via `npx -y @roberttlange/autotune run experiments/<x>.py --trials N`: it proposes the search space from the script, confirms it with you, and runs trials without touching the file. Tune with it rather than with YAML sweep configs; a tyro script that prints a metric line already works with it.

At project setup, install its agent skill into the project with `npx -y skills add RobertTLange/autotune --skill autotune --agent claude-code -y`.
