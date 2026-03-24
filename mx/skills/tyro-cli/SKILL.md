---
name: tyro-cli
description: Must read guide on creating/editing CLIs or any Python script that accepts command-line arguments.
---

# CLI Scripts with tyro

All Python CLI scripts use tyro for argument parsing — never argparse, click, or fire. tyro generates CLIs from type annotations with zero boilerplate, and `--help` output is derived directly from docstrings and type hints.

## Core Principles

1. **`--help` is the documentation.** Every script must be fully self-documenting: module docstring with usage examples, every argument with a help string. A user running `--help` should never need to read source code.
2. **PEP 723 inline metadata** for standalone scripts. Declare tyro (and other deps) via inline metadata so scripts are runnable with `uv run` without project setup. If the script lives in a project with pyproject.toml and tyro is already a dependency, inline metadata is unnecessary.
3. **Lean over clever.** Simple dataclass with field docstrings covers 90% of use cases. Reach for advanced features (subcommands, nested configs) only when the CLI genuinely needs them.

## PEP 723 Inline Dependencies

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
```

Place at the top of the file. The script is then runnable via `uv run script.py --help`.

## Preferred Patterns

### Pattern 1: Simple Dataclass (default choice)

For scripts with a flat set of arguments (~5-30 flags).

```python
"""Process experiment data and generate reports.

Examples::

    uv run process.py --input data.csv --output report.html
    uv run process.py --input data.csv --format json --verbose
"""
from dataclasses import dataclass
from typing import Literal
import tyro

@dataclass
class Args:
    input: str
    """Path to the input data file."""
    output: str = "report.html"
    """Path to the output report."""
    format: Literal["html", "json", "csv"] = "html"
    """Output format."""
    verbose: bool = False
    """Enable verbose logging."""

if __name__ == "__main__":
    args = tyro.cli(Args, description=__doc__)
```

### Pattern 2a: Decorator Subcommands (preferred for extensible CLIs)

`tyro.extras.SubcommandApp` — click-inspired decorator API. Works with 1+ subcommands (unlike Union which needs 2+).

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

### Pattern 2b: Union Subcommands (static multi-command tools)

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

### Pattern 3: Nested Dataclasses (hierarchical configs)

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

## Documenting --help

### Module Docstring → Program Description

The module docstring (or `description=__doc__`) becomes the top-level help text. Structure it as:

1. One-line summary of what the script does
2. Blank line, then details/context if needed
3. `Examples::` section with concrete invocations (the `::` is reStructuredText convention, renders cleanly)

```python
"""Stress test for the TTS synthesis pipeline.

Simulates concurrent users with realistic playback patterns.
Auth: set PROD_TEST_EMAIL/PROD_TEST_PASSWORD in .env, or pass --token.

Examples::

    uv run stress_test.py --users 5
    uv run stress_test.py --token TOKEN --users 10 --speed 2
"""
```

### Field Docstrings → Argument Help

Triple-quoted strings immediately after a dataclass field become its `--help` text.

```python
@dataclass
class Args:
    learning_rate: float = 3e-4
    """Learning rate for the optimizer. Values between 1e-5 and 1e-2 are typical."""
```

### Function-Based CLIs

For function signatures, use Google-style docstrings with an `Args:` section:

```python
def main(input_path: str, verbose: bool = False) -> None:
    """Process files.

    Args:
        input_path: Path to the input file.
        verbose: Enable verbose logging.
    """
```

## Gotchas

### Newlines in Docstrings

tyro collapses single newlines to spaces (like HTML). To force a line break:
- Use a blank line (double newline) for paragraph breaks
- Start the next line with a non-alpha character (`-`, `*`, a number) — this forces a break

```python
# WRONG: renders as one line in --help
"""First line.
Second line."""

# RIGHT: preserved as separate lines
"""First line.

Second line."""

# RIGHT: bullet list preserved (lines start with -)
"""Choose a mode:
- fast: skip validation
- safe: full validation"""
```

### Booleans Need Defaults

A `bool` field without a default requires `--flag True` or `--flag False` (not just `--flag`). Always provide a default to get `--flag`/`--no-flag` toggle behavior:

```python
# BAD: requires --verbose True / --verbose False
verbose: bool

# GOOD: --verbose enables, --no-verbose disables
verbose: bool = False
```

### Optional Args Display

`str | None = None` shows as `{None}|STR` in help, which is ugly. No built-in fix — use `metavar=` via `tyro.conf.arg(metavar="VALUE")` to override, or provide a default string value instead of None where possible.

### Subcommand Argument Ordering

Arguments before the subcommand selector go to the parent parser. Arguments after go to the subcommand. Use `tyro.conf.CascadeSubcommandArgs` to relax this constraint if mixing shared args with subcommands.

### Comment Help Text Propagation

A comment block above consecutive fields applies to ALL of them (not just the first). Separate field groups with blank lines or use field docstrings instead.

```python
# BAD: this comment applies to BOTH fields
# Controls the learning rate
lr: float = 3e-4
weight_decay: float = 1e-2  # unintentionally gets "Controls the learning rate"

# GOOD: use field docstrings
lr: float = 3e-4
"""Controls the learning rate."""
weight_decay: float = 1e-2
"""L2 regularization coefficient."""
```

### `__post_init__` with `default=`

When passing `default=Config(...)` to `tyro.cli()`, `__post_init__` is called twice (once for the default, once for the parsed result). Avoid side effects in `__post_init__`; use `@property` for derived fields.

## Machine-Consumable Output

CLIs should be usable by both humans and programs (LLMs, scripts, pipelines). Don't build format converters into every CLI — emit JSON and let consumers transform it with `jq` (`@csv`, `@tsv`, etc.). Two flags handle the human/machine split:

### `--plain` — terse, undecorated text

Strips progress bars, unicode boxes, color codes, and decorative formatting. Emits compact text (TSV, plain prose, etc.). Use when the consumer wants readable text but not visual chrome.

```python
plain: bool = False
"""Terse output — no bars, no unicode, no color. For piping to LLMs or scripts."""
```

Make `--plain` affect all output paths — tables, progress indicators, summaries. The default (rich/human-friendly) stays unchanged.

### `--json` — structured data

For commands that list, query, or return structured data, add a `--json` flag that emits JSON. This lets consumers pipe to `jq` for filtering/transformation without fragile text parsing.

```python
json: bool = False
"""Emit JSON to stdout. Pipe to jq for filtering."""
```

When `--json` is active, emit valid JSON to stdout (errors/warnings still go to stderr). For list commands, emit a JSON array. For single-item queries, emit a JSON object. For other formats (csv, etc.), consumers can derive them from JSON via `jq`.

### JSON schemas in `--help`

For any command that supports `--json`, document the schema in its help text so consumers know the shape without trial and error. Include it in the command's docstring:

```python
"""List available resources.

JSON schema (--json)::

    [{"id": "str", "name": "str", "status": "available|reserved", "region": "str"}]

Examples::

    uv run tool.py list --json | jq '.[] | select(.status == "available")'
    uv run tool.py list --plain --region us-east
"""
```

This is especially valuable when the CLI is used as a tool by LLM agents — they can read `--help` once and know exactly what to `jq` for, instead of running exploratory commands to discover the output shape.

## Anti-Patterns

**String choices instead of Literal.** Use `Literal["a", "b"]` — not `str` with choices documented in the docstring. Literal gives type safety, auto-completion, and tyro generates proper `{a,b}` choices in help.

**Multiple `tyro.cli()` calls with `return_unknown_args`.** Calling `tyro.cli()` twice and passing leftovers to a second call is fragile. Use a single nested dataclass instead.

**`OmitArgPrefixes` with nested dataclasses.** Can cause name collisions if nested structs share field names. Only use for flat, single-dataclass CLIs.

**Overusing argparse habits.** No need for `add_argument`, `ArgumentParser`, or manual type conversion. If reaching for argparse patterns, there's a tyro way to do it.

## Useful Features Reference

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
