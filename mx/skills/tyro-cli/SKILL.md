---
name: tyro-cli
description: "Python CLIs with tyro, and PEP 723 scripts for `uv run`. Use when writing or editing any Python script that takes command-line arguments, or making a script runnable with `uv run`."
---

# CLI Scripts with tyro

All Python CLI scripts use tyro for argument parsing, never argparse, click, or fire. tyro generates CLIs from type annotations with zero boilerplate, and `--help` output is derived directly from docstrings and type hints.

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

Place at the top of the file. The script is then runnable via `uv run script.py --help`. Converting a script that already exists, `dependencies` lists every third-party package its imports need, and its code stays as it is: moving its parsing to tyro is a change of its own.

### Shebang for PEP 723 scripts

**Always use `--script`** when the shebang invokes `uv run` on a file with inline metadata:

```python
#!/usr/bin/env -S uv run --script --quiet
```

Without `--script`, uv doesn't detect the inline metadata block and falls back to project resolution. If there's no project, it recurses infinitely (`uv run` invokes the script, which invokes `uv run` again via the shebang) and hits the 100-call recursion limit.

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

- Subcommands, nested configs, positional or repeated args, short aliases, the rest of `tyro.conf`: [PATTERNS.md](PATTERNS.md).
- Output a program or an agent reads (`--plain`, `--json`, a JSON schema in `--help`): [OUTPUT.md](OUTPUT.md).

## Documenting --help

### Scope: the CLI, not the workflow

`--help` describes the tool: what each flag accepts, what it rejects, what the tool does with it. Process lives elsewhere: who runs this, in what order, what to do with the output. A help string that prescribes process is a second copy of a policy some skill or doc already owns, and it is the copy nobody updates when the policy changes.

```python
# BAD: schema plus a process rule owned by the workflow doc
notes: str = ""
"""JSON notes file. Schema: {...}. Pick each id once, leave a gap when a note is dropped, never renumber."""

# GOOD: what the flag accepts, and the constraint the loader enforces
notes: str = ""
"""JSON notes file. Schema: {...}. Ids must be unique."""
```

The test: would the sentence still hold for a caller using this tool in a different workflow? If not, it belongs in that workflow's document. Self-documenting (Core Principle 1) means nobody must read the *source* to drive the tool, not that `--help` carries the process the tool is used in.

### Module Docstring → Program Description

The module docstring (or `description=__doc__`) becomes the top-level help text. Structure it as:

1. One-line summary of what the script does
2. Blank line, then details/context if needed
3. `Examples:` section with concrete invocations. Don't use `::` (reST convention); tyro renders it literally and it looks ugly in `--help` output.

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

tyro collapses single newlines to spaces (like HTML). To force a line break:
- Use a blank line (double newline) for paragraph breaks
- Start the next line with a non-alpha character (`-`, `*`, a number); this forces a break

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

`str | None = None` shows as `{None}|STR` in help, which is ugly. No built-in fix: use `metavar=` via `tyro.conf.arg(metavar="VALUE")` to override, or provide a default string value instead of None where possible.

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

## Anti-Patterns

**String choices instead of Literal.** Use `Literal["a", "b"]`, not `str` with choices documented in the docstring. Literal gives type safety, auto-completion, and tyro generates proper `{a,b}` choices in help.

**Multiple `tyro.cli()` calls with `return_unknown_args`.** Calling `tyro.cli()` twice and passing leftovers to a second call is fragile. Use a single nested dataclass instead.

**Overusing argparse habits.** No need for `add_argument`, `ArgumentParser`, or manual type conversion. If reaching for argparse patterns, there's a tyro way to do it.
