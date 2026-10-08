# Machine-Consumable Output

The branch of [`tyro-cli`](SKILL.md) for a CLI whose output a program or an agent reads as well as a human.

CLIs should be usable by both humans and programs (LLMs, scripts, pipelines). Don't build format converters into every CLI; emit JSON and let consumers transform it with `jq` (`@csv`, `@tsv`, etc.). Two flags handle the human/machine split:

## `--plain`: terse, undecorated text

Strips progress bars, unicode boxes, color codes, and decorative formatting. Emits compact text (TSV, plain prose, etc.). Use when the consumer wants readable text but not visual chrome.

```python
plain: bool = False
"""Terse output: no bars, no unicode, no color. For piping to LLMs or scripts."""
```

Make `--plain` affect all output paths: tables, progress indicators, summaries. The default (rich/human-friendly) stays unchanged.

## `--json`: structured data

For commands that list, query, or return structured data, add a `--json` flag that emits JSON. This lets consumers pipe to `jq` for filtering/transformation without fragile text parsing.

```python
json: bool = False
"""Emit JSON to stdout. Pipe to jq for filtering."""
```

When `--json` is active, emit valid JSON to stdout (errors/warnings still go to stderr). For list commands, emit a JSON array. For single-item queries, emit a JSON object. For other formats (csv, etc.), consumers can derive them from JSON via `jq`.

## JSON schemas in `--help`

For any command that supports `--json`, document the schema in its help text so consumers know the shape without trial and error. Include it in the command's docstring:

```python
"""List available resources.

JSON schema (--json):

    [{"id": "str", "name": "str", "status": "available|reserved", "region": "str"}]

Examples:

    uv run tool.py list --json | jq '.[] | select(.status == "available")'
    uv run tool.py list --plain --region us-east
"""
```

This is especially valuable when the CLI is used as a tool by LLM agents; they can read `--help` once and know exactly what to `jq` for, instead of running exploratory commands to discover the output shape.
