# Subcommands, nested configs and tyro.conf

## Pattern 2a: decorator subcommands (preferred for extensible CLIs)

`tyro.extras.SubcommandApp`, a click-style decorator API, works with one subcommand; a union needs two.

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
- `OmitArgPrefixes` drops the parameter name's `--args.` prefix.

## Pattern 2b: union subcommands (static multi-command tools)

For subcommands known when the types are defined, dispatched on type alone.

**Limitation:** Python collapses `Union[X]` to `X`, so this needs 2+ variants; a single subcommand uses Pattern 2a.

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

Arguments before the subcommand selector go to the parent parser, arguments after it to the subcommand. `tyro.conf.CascadeSubcommandArgs` relaxes this where shared arguments mix with subcommands.

## Pattern 3: nested dataclasses (hierarchical configs)

For arguments that group into subsections, as dot-prefixed flags like `--optimizer.lr`.

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

**`OmitArgPrefixes` with nested dataclasses** collides names wherever nested structs share a field name, so use it only on a flat, single-dataclass CLI.

## A flag with an optional value

`--image` alone means one thing, `--image shot.png` another (argparse's `nargs="?"`). tyro has no marker for it, and `PrimitiveConstructorSpec(nargs="?")` is internal; a constructor taking zero or more values does it:

```python
def _one_image(values: list[str]) -> Path | bool:
    if len(values) > 1:
        raise ValueError("--image takes one FILE at most")
    return Path(values[0]) if values else True

IMAGE = tyro.constructors.PrimitiveConstructorSpec(
    nargs="*", metavar="[FILE]", instance_from_str=_one_image,
    is_instance=lambda x: isinstance(x, (bool, Path)),
    str_from_instance=lambda x: [str(x)] if isinstance(x, Path) else [])

@dataclass
class Put:
    source: Annotated[Path, tyro.conf.Positional]
    image: Annotated[Path | bool, IMAGE, tyro.conf.arg(help_behavior_hint="(default: none)")] = False
```

- Without `help_behavior_hint`, `--help` prints `(default: )`.
- The flag takes words up to the next flag. It leaves one for a required positional only when that word is the last on the line: `--image page.html` and `page.html --image` parse, `--image page.html --title T` reads `page.html` as the image and fails on the missing positional.

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
