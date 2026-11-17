# Machine-consumable output

CLIs should be usable by both humans and programs (LLMs, scripts, pipelines). Don't build format converters into every CLI; emit JSON and let consumers transform it with `jq` (`@csv`, `@tsv`, etc.). Two flags handle the human/machine split:

## `--plain`: terse, undecorated text

Strips progress bars, unicode boxes, color codes, and decorative formatting. Emits compact text (TSV, plain prose, etc.). Use when the consumer wants readable text but not visual chrome.

```python
plain: bool = False
"""Terse output: no bars, no unicode, no color. For piping to LLMs or scripts."""
```

Make `--plain` affect all output paths: tables, progress indicators, summaries. The default (rich/human-friendly) stays unchanged.

## `--json`: structured data

For commands that list, query, or return structured data, add a `--json` flag that emits JSON.

```python
json: bool = False
"""Emit JSON to stdout. Pipe to jq for filtering."""
```

When `--json` is active, emit valid JSON to stdout (errors/warnings still go to stderr).

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
