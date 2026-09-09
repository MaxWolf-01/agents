#!/bin/bash
# Validate a Mermaid diagram by parsing and rendering it with the official CLI.
# Usage: validate.sh diagram.mmd [output.svg]
#   Exit 0 with an ASCII preview when the diagram parses and renders; nonzero
#   with the parser's error otherwise. The SVG lands at output.svg when given,
#   else in a temp file that is removed again. The preview (beautiful-mermaid)
#   is best effort: an unsupported diagram type prints a warning, not a failure.
#   Needs Node and npx; the first run downloads a headless Chromium through
#   Puppeteer (PUPPETEER_EXECUTABLE_PATH points it at an installed one).

set -euo pipefail

usage() { sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; }
case ${1:-} in
    -h|--help) usage; exit 0 ;;
    "") usage >&2; exit 1 ;;
esac

INPUT="$1"
OUTPUT="${2:-}"

if [ ! -f "$INPUT" ]; then
    echo "Error: File not found: $INPUT"
    exit 1
fi

CLEANUP=0
if [ -z "$OUTPUT" ]; then
    OUTPUT=$(mktemp /tmp/mermaid_validate.XXXXXX.svg)
    CLEANUP=1
fi

trap 'if [ "$CLEANUP" -eq 1 ]; then rm -f "$OUTPUT"; fi' EXIT

echo "Validating: $INPUT"

# Use mermaid-cli (mmdc) to parse and render. Errors mean invalid syntax.
# Filter out JS stack traces, keep only the parse error.
if npx -y @mermaid-js/mermaid-cli -i "$INPUT" -o "$OUTPUT" -q 2> >(grep -vE '^\s*at |^Parser3?\.' >&2); then
    echo "✓ Mermaid OK"
    echo ""
    echo "ASCII preview:"
    if ! MERMAID_INPUT="$INPUT" npx -y --package beautiful-mermaid node -e '
const fs = require("node:fs");
const path = require("node:path");
const binPath = process.env.PATH.split(":")[0];
const moduleRoot = path.dirname(binPath);
const { renderMermaidAscii } = require(path.join(moduleRoot, "beautiful-mermaid"));
const text = fs.readFileSync(process.env.MERMAID_INPUT, "utf8");
process.stdout.write(renderMermaidAscii(text));
process.stdout.write("\n");
'; then
        echo "Warning: ASCII preview failed (diagram type may be unsupported)."
    fi
    if [ "$CLEANUP" -eq 0 ]; then
        echo "Rendered to: $OUTPUT"
    fi
else
    echo "✗ Mermaid validation failed"
    exit 1
fi
