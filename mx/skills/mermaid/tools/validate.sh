#!/bin/bash
# Validate a Mermaid diagram by parsing and drawing it with Pele.
# Usage: validate.sh diagram.mmd [output.svg]
#   Exit 0 with an ASCII preview when the diagram parses and draws; nonzero
#   with Pele's error otherwise, at its line and column. The SVG lands at
#   output.svg when given. The preview (beautiful-mermaid) is best effort: an
#   unsupported diagram type prints a warning, not a failure.
#   Needs Node 20 or later and npm, and no browser. The first run installs Pele
#   as package-lock.json beside this script pins it, version and hash, under
#   ${XDG_CACHE_HOME:-~/.cache}/mx-pele.

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

# One install per lockfile, so a new pin installs beside the old one rather than over it. It is
# built in a directory of its own and moved into place whole, so a run that starts while another is
# installing never finds half of one.
HERE=$(cd "$(dirname "$0")" && pwd)
PELE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}/mx-pele/$(sha256sum "$HERE/package-lock.json" | cut -c1-16)"
if [ ! -d "$PELE_HOME/node_modules/pele" ]; then
    mkdir -p "$(dirname "$PELE_HOME")"
    BUILD=$(mktemp -d "$PELE_HOME.XXXXXX")
    trap 'rm -rf "$BUILD"' EXIT
    cp "$HERE/package.json" "$HERE/package-lock.json" "$BUILD/"
    npm ci --prefix "$BUILD" --no-audit --no-fund --silent >&2
    mv -T "$BUILD" "$PELE_HOME" 2>/dev/null || true  # another run's install got there first
fi

echo "Validating: $INPUT"

if PELE="$PELE_HOME/node_modules/pele/dist/pele.js" node --input-type=module - "$INPUT" "$OUTPUT" <<'JS'; then
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const { render, PeleError } = await import(pathToFileURL(process.env.PELE));
const [input, output] = process.argv.slice(2);
try {
  const { svg } = render(readFileSync(input, "utf8"));
  if (output) writeFileSync(output, svg);
} catch (e) {
  if (!(e instanceof PeleError)) throw e;
  console.error(`${input}${e.line ? `:${e.line}:${e.column}` : ""}: ${e.message}`);  // the message quotes the line
  process.exit(1);
}
JS
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
    if [ -n "$OUTPUT" ]; then
        echo "Rendered to: $OUTPUT"
    fi
else
    echo "✗ Mermaid validation failed"
    exit 1
fi
