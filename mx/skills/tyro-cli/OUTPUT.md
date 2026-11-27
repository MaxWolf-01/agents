# Machine-consumable output

A CLI serves both humans and programs (LLMs, scripts, pipelines). It emits JSON and leaves other formats to the consumer's `jq` (`@csv`, `@tsv`), rather than building in converters.

## `--plain`: terse, undecorated text

Compact text (TSV, plain prose) with no progress bars, unicode boxes, color codes or other decoration, for a consumer that wants readable text without the chrome.

```python
plain: bool = False
"""Terse output: no bars, no unicode, no color. For piping to LLMs or scripts."""
```

`--plain` covers every output path: tables, progress indicators, summaries. The default output stays rich, for humans.

## `--json`: structured data

A command that lists, queries or returns structured data gets a `--json` flag.

```python
json: bool = False
"""Emit JSON to stdout. Pipe to jq for filtering."""
```

Under `--json`, stdout carries valid JSON; errors and warnings still go to stderr.

## JSON schemas in `--help`

A command with `--json` documents the JSON's schema in its docstring, so a consumer knows the shape without trial and error:

```python
"""List available resources.

JSON schema (--json):

    [{"id": "str", "name": "str", "status": "available|reserved", "region": "str"}]

Examples:

    uv run tool.py list --json | jq '.[] | select(.status == "available")'
    uv run tool.py list --plain --region us-east
"""
```
