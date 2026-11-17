---
name: tyro-cli
description: "Python CLIs with tyro, and PEP 723 scripts for `uv run`. Use when writing or editing any Python script that takes command-line arguments, or making a script runnable with `uv run`."
---

# CLI Scripts with tyro

All Python CLI scripts use tyro for argument parsing, never argparse, click, or fire.

## Core Principles

1. **`--help` is the documentation.** Every script carries a module docstring with usage examples and a help string on every argument, so nobody running `--help` needs to read the source.
2. **PEP 723 inline metadata** for standalone scripts: declare tyro and the other dependencies inline, so `uv run` runs the script without project setup. A script inside a project whose pyproject.toml already depends on tyro needs none.

## PEP 723 Inline Dependencies

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
```

When converting an existing script, list every third-party package its imports need in `dependencies` and leave its code as it is: moving its parsing to tyro is a change of its own.

### Shebang for PEP 723 scripts

**Always use `--script`** when the shebang invokes `uv run` on a file with inline metadata:

```python
#!/usr/bin/env -S uv run --script --quiet
```

Without `--script`, uv ignores the inline metadata and falls back to project resolution; with no project, the shebang re-invokes `uv run` until it hits the 100-call recursion limit.

## Preferred Patterns

### Pattern 1: Simple Dataclass (default choice)

For scripts with a flat set of arguments (~5-30 flags).

```python
"""Process experiment data and generate reports.

Examples:

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

### Subcommands, nested configs, machine output

- Subcommands, nested configs, positional or repeated args, a flag whose value is optional (`--image` or `--image FILE`), short aliases, the rest of `tyro.conf`: [PATTERNS.md](PATTERNS.md).
- Output a program or an agent reads (`--plain`, `--json`, a JSON schema in `--help`): [OUTPUT.md](OUTPUT.md).

## Documenting --help

### Scope: the CLI, not the workflow

`--help` describes the tool: what each flag accepts, what it rejects, what the tool does with it. Process (who runs it, in what order, what to do with the output) belongs to the skill or doc that owns the policy; a copy in a help string is the one nobody updates when the policy changes.

```python
# BAD: schema plus a process rule owned by the workflow doc
notes: str = ""
"""JSON notes file. Schema: {...}. Pick each id once, leave a gap when a note is dropped, never renumber."""

# GOOD: what the flag accepts, and the constraint the loader enforces
notes: str = ""
"""JSON notes file. Schema: {...}. Ids must be unique."""
```

The test: would the sentence still hold for a caller using this tool in a different workflow? If not, it belongs in that workflow's document. Core Principle 1 means nobody must read the *source* to drive the tool, not that `--help` carries the process around it.

### Module Docstring → Program Description

The module docstring, passed as `description=__doc__`, becomes the top-level help text: a one-line summary, a blank line, details if needed, then an `Examples:` section of concrete invocations. Write `Examples:` with one colon; tyro prints reST's `::` literally.

```python
"""Stress test for the TTS synthesis pipeline.

Simulates concurrent users with realistic playback patterns.
Auth: set PROD_TEST_EMAIL/PROD_TEST_PASSWORD in .env, or pass --token.

Examples:

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

tyro collapses a single newline to a space. A blank line keeps a paragraph break, and a line starting with a non-alphabetic character (`-`, `*`, a digit) keeps its own line.

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

A `bool` field without a default takes `--flag True` or `--flag False`, not a bare `--flag`. Give it a default to get the `--flag`/`--no-flag` toggle:

```python
# BAD: requires --verbose True / --verbose False
verbose: bool

# GOOD: --verbose enables, --no-verbose disables
verbose: bool = False
```

### Optional Args Display

`str | None = None` shows as `{None}|STR` in help. Override it with `tyro.conf.arg(metavar="VALUE")`, or give a string default instead of None where one makes sense.

### Comment Help Text Propagation

A comment block above consecutive fields becomes the help of all of them, not just the first. Separate field groups with blank lines, or use field docstrings.

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

With `default=Config(...)` passed to `tyro.cli()`, `__post_init__` runs twice, once for the default and once for the parsed result. Keep it free of side effects, and compute derived fields as `@property`.

## Anti-Patterns

**String choices instead of Literal.** Type a choice as `Literal["a", "b"]`, not as `str` with the choices in its docstring: Literal gives type safety and completion, and tyro lists `{a,b}` in help.

**Multiple `tyro.cli()` calls with `return_unknown_args`.** Handing one call's leftovers to a second is fragile; parse once, into one nested dataclass.
