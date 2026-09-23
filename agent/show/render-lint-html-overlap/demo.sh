#!/usr/bin/env bash
# render-lint over HTML text drawn on top of other HTML text: the board's row marks
# colliding, as the failure that went unseen until this ticket, and the same marks on
# a grid. The page is rows.html beside this script.
#
# Usage: bash demo.sh [work-dir]
#
# Two runs of the same page. Broken, it fails with an overlap per collided row, each
# naming both texts, and reports the feature tag its box cuts off. Laid out on a grid
# (?fixed), the collisions are gone and the clipped tag alone leaves the run passing:
# a truncated title is sometimes the design. The crops are the point; open them.
set -eu

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
lint=$repo/mx/bin/render-lint
page=$here/rows.html
work=${1:-$(mktemp -d /tmp/render-lint-html-overlap.XXXX)}

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# Each run's claim, as something that can fail: the findings and the exit code together,
# since a kind that stopped failing the run would still print the same line.
run() { # <crops dir> <expected exit> <page> <expected kinds, one per line>
    crops=$work/$1; shift
    printf '$ render-lint %s --crops %s\n' "${2/#$repo\//}" "$crops"
    code=0
    "$lint" "$2" --crops "$crops" || code=$?
    kinds=$("$lint" "$2" --json | grep -o '"kind": "[a-z]*"' | cut -d'"' -f4) || true
    [ "$code" = "$1" ] && [ "$kinds" = "$3" ] || {
        printf 'FAIL: expected exit %s on\n%s\ngot exit %s on\n%s\n' "$1" "$3" "$code" "$kinds" >&2
        exit 1
    }
}

step "the marks at their own offsets: two rows whose text collides"
run collide 1 "$page" "clipped
overlap
overlap"

step "the same marks on a grid: the cut-off feature tag, and nothing colliding"
run grid 0 "$page?fixed" "clipped"

step "the crops are in $work"
ls "$work"/*
printf '\nopen the page itself at %s, and %s?fixed\n' "$page" "$page"
