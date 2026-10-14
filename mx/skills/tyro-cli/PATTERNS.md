# Subcommands, nested configs and tyro.conf

The branch of [`tyro-cli`](SKILL.md) for a CLI that outgrows Pattern 1: subcommands, nested configs, and the `tyro.conf` features beyond a plain field.

## Pattern 2a: decorator subcommands (preferred for extensible CLIs)

`tyro.extras.SubcommandApp`: click-inspired decorator API. Works with 1+ subcommands (unlike Union which needs 2+).

```python
import tyro
from tyro.extras import SubcommandApp

app = SubcommandApp()

@app.command(name="train")
def train(args: TrainArgs) -> None:
    """Train a model."""
    ...

@app.command(name="eval")
def eval(args: EvalArgs) -> None:
    """Evaluate a checkpoint."""
    ...

if __name__ == "__main__":
    app.cli(description=__doc__, config=(tyro.conf.OmitArgPrefixes,))
```

- `description` goes on `.cli()`, not `SubcommandApp()`.
- `OmitArgPrefixes` avoids `--args.` prefix from the function parameter name.

## Pattern 2b: union subcommands (static multi-command tools)

When subcommands are known at type-definition time and you want pure type-based dispatch.

**Limitation:** Python collapses `Union[X]` to `X`, so this requires 2+ variants. For a single subcommand, use Pattern 2a instead.

```python
from dataclasses import dataclass
from typing import Annotated
import tyro

@dataclass
class Train:
    """Train the model."""
    epochs: int = 10
    """Number of training epochs."""
    lr: float = 3e-4
    """Learning rate."""

@dataclass
class Eval:
    """Evaluate a checkpoint."""
    checkpoint: Annotated[str, tyro.conf.Positional]
    """Path to model checkpoint."""

Cmd = (
    Annotated[Train, tyro.conf.subcommand(name="train", prefix_name=False)]
    | Annotated[Eval, tyro.conf.subcommand(name="eval", prefix_name=False)]
)

if __name__ == "__main__":
    cmd = tyro.cli(Cmd, description=__doc__)
```

### Subcommand argument ordering

Arguments before the subcommand selector go to the parent parser. Arguments after go to the subcommand. Use `tyro.conf.CascadeSubcommandArgs` to relax this constraint if mixing shared args with subcommands.

## Pattern 3: nested dataclasses (hierarchical configs)

When arguments naturally group into subsections. Creates dot-prefixed flags like `--optimizer.lr`.

```python
@dataclass
class OptimizerConfig:
    lr: float = 3e-4
    """Learning rate."""
    weight_decay: float = 1e-2
    """Weight decay coefficient."""

@dataclass
class Config:
    optimizer: OptimizerConfig
    seed: int = 0
    """Random seed."""

config = tyro.cli(Config)
```

**`OmitArgPrefixes` with nested dataclasses** can cause name collisions if nested structs share field names. Only use it for flat, single-dataclass CLIs.

## Useful features reference

| Feature | Usage | When |
|---|---|---|
| Positional args | `Annotated[str, tyro.conf.Positional]` | Natural positional CLI args (paths, names) |
| Variadic positional | `Annotated[list[str], tyro.conf.Positional]` | Multiple positional args (`script.py a b c`) |
| Short aliases | `Annotated[str, tyro.conf.arg(aliases=["-v"])]` | Common flags that deserve short forms |
| Custom arg config | `tyro.conf.arg(name=, help=, metavar=, aliases=)` | Fine-grained control over a single argument |
| Choices | `Literal["a", "b", "c"]` | Constrained string values |
| Enum choices | `MyEnum` (name-based) or `tyro.conf.EnumChoicesFromValues[MyEnum]` (value-based) | When enum objects are needed downstream |
| Omit prefixes | `tyro.cli(Args, config=(tyro.conf.OmitArgPrefixes,))` | Single flat dataclass, avoid `--args.field` |
| Repeat flags | `tyro.conf.UseAppendAction[list[str]]` | `--tag foo --tag bar` instead of `--tag foo bar` |
| Subcommand defaults | `tyro.conf.subcommand(name="x", default=X())` | Pre-filled subcommand defaults |
| Cascade args | `config=(tyro.conf.CascadeSubcommandArgs,)` | Flexible arg ordering with subcommands |
| Suppress field | `field: tyro.conf.Suppress[int] = 42` | Hide internal fields from CLI entirely |
| Fixed field | `field: tyro.conf.Fixed[int] = 42` | Show in help but don't allow override |
