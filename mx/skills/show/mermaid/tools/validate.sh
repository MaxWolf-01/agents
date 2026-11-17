#!/bin/bash
# Validate a Mermaid diagram by parsing and drawing it with Pele.
# Usage: validate.sh diagram.mmd [output.svg]
#   Exit 0 with an ASCII preview when the diagram parses and draws; nonzero
#   with Pele's error otherwise, at its line and column. The SVG lands at
#   output.svg when given. The preview (beautiful-mermaid) is best effort: an
#   unsupported diagram type prints a warning, not a failure.
#   Needs Node 20 or later and npm, and no browser. The first run installs Pele
#   and the preview as package-lock.json beside this script pins them, version
#   and hash, under ${XDG_CACHE_HOME:-~/.cache}/mx-mermaid.

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
DEPS="${XDG_CACHE_HOME:-$HOME/.cache}/mx-mermaid/$(sha256sum "$HERE/package-lock.json" | cut -c1-16)"
if [ ! -d "$DEPS/node_modules/pele" ]; then
    mkdir -p "$(dirname "$DEPS")"
    BUILD=$(mktemp -d "$DEPS.XXXXXX")
    trap 'rm -rf "$BUILD"' EXIT
    cp "$HERE/package.json" "$HERE/package-lock.json" "$BUILD/"
    npm ci --prefix "$BUILD" --no-audit --no-fund --silent >&2
    mv -T "$BUILD" "$DEPS" 2>/dev/null || rm -rf "$BUILD"  # another run's install got there first
fi

echo "Validating: $INPUT"

MODULES="$DEPS/node_modules" exec node --input-type=module - "$INPUT" "$OUTPUT" <<'JS'
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const from = (path) => import(pathToFileURL(`${process.env.MODULES}/${path}`));
const { render, PeleError } = await from("pele/dist/pele.js");
const [input, output] = process.argv.slice(2);
const source = readFileSync(input, "utf8");
try {
  const { svg } = render(source);
  if (output) writeFileSync(output, svg);
} catch (e) {
  if (!(e instanceof PeleError)) throw e;
  console.error(`${input}${e.line ? `:${e.line}:${e.column}` : ""}: ${e.message}`);  // the message quotes the line
  console.log("✗ Mermaid validation failed");
  process.exit(1);
}
console.log("✓ Mermaid OK\n\nASCII preview:");
try {
  const { renderMermaidAscii } = await from("beautiful-mermaid/dist/index.js");
  console.log(renderMermaidAscii(source));
} catch (e) {
  console.log(`Warning: ASCII preview failed (diagram type may be unsupported): ${e.message}`);
}
if (output) console.log(`Rendered to: ${output}`);
JS
