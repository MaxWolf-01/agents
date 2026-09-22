#!/usr/bin/env bash
# The coverage check against the breakdown whose gap it was cut from: one-flow's
# spec and its nine tickets, retired from the tracker and read back out of git.
#
# Usage: bash demo.sh [work-dir]
#
# Three states of the same breakdown, the check run on each:
#   1. as it shipped, before properties carried ids
#   2. numbered, each criterion stamped with the property it paraphrases: the gap
#      the whole-feature review found, now as findings that name it
#   3. the gap closed: every property disposed of, the check clean
#
# Everything it writes is inside the work dir.
set -eu

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
check=$repo/mx/bin/property-coverage
retired=1f26781  # the commit that retired one-flow; its parent still holds the files
work=${1:-$(mktemp -d /tmp/property-coverage.XXXX)}/one-flow

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
run() { printf '$ property-coverage %s\n' "$1"; "$check" "$1" || true; }

mkdir -p "$work"
for f in spec 01-prose-catalogue 02-proposed-buildable 03-chat-reviewer 04-review-delivery \
         05-standalone-dispatch 06-worker-contract 07-flow-skills 08-host-per-spawn 09-whole-feature-review; do
    git -C "$repo" show "$retired^:agent/tickets/one-flow/$f.md" > "$work/$f.md"
done

step "1. as it shipped: fifteen properties, twelve criteria, no ids anywhere"
run "$work"

step "2. the spec numbered P1..P15, each criterion stamped with the property it paraphrases"
uv run --quiet python - "$work" <<'PY'
import re, sys
from pathlib import Path

work = Path(sys.argv[1])

# The spec's properties in the order they stand: ids are assigned once, and kept.
spec = work / "spec.md"
lines, n, inside = spec.read_text().splitlines(), 0, False
for i, line in enumerate(lines):
    if line.startswith("## "):
        inside = line == "## Properties"
    elif inside and line.startswith("- "):
        n += 1
        lines[i] = f"- P{n} {line[2:]}"
spec.write_text("\n".join(lines) + "\n")

# Each shipped criterion, and the property it paraphrases. The last is the one that
# paraphrases no property at all: its author reached for the id after the spec's last.
STAMP = [
    ("a rule about prose lives in one catalogue", "P8"),
    ("nothing built on a guess reaches the integration branch", "P12"),
    ("the unit of the flow stays one ticket", "P11"),
    ("a chat reply the user reads has been checked", "P9"),
    ("no finding a worker already fixed reaches the user", "P4"),
    ("one worker contract", "P7"),
    ("ticketed work always appears on the board", "P6"),
    ("every landing is demonstrated as the thing itself", "P15"),
    ("no step blocks on the user reading a brief", "P2"),
    ("the build never starts while the agent still has a question", "P14"),
    ("the implement skill addresses only the worker", "P16"),
]
for ticket in sorted(work.glob("[0-9][0-9]-*.md")):
    text = ticket.read_text()
    for phrase, id in STAMP:
        text = re.sub(rf"^(- \[.\] )Property, (reviewed: {re.escape(phrase)})", rf"\1Property {id}, \2", text, flags=re.M)
    ticket.write_text(text)
PY
run "$work"

step "3. the five properties that reached no ticket disposed of, the sixteenth criterion dropped"
uv run --quiet python - "$work" <<'PY'
import sys
from pathlib import Path

work = Path(sys.argv[1])

# Where each property no ticket held belongs, in the words of the slice that holds it.
ADD = {
    "06-worker-contract.md": [
        "- [ ] Property P1, reviewed: the prompt has the worker build from the ticket and its spec, never from a conversation it was not in.",
        "- [ ] Property P13, reviewed: an unratified call leaves the worker as an anchored assumption naming the spec mark it stands in for.",
    ],
    "04-review-delivery.md": [
        "- [ ] Property P5, reviewed: the landing message leads with the outcome, the demo and the user's calls; everything else sits behind a tag.",
        "- [ ] Property P10, reviewed: every landed slice has a review page before the user is asked to judge it.",
    ],
    # A property no one slice can make true says so where the others are disposed of.
    "09-whole-feature-review.md": [
        "- Property P3, unsliced: it holds across the flow rather than inside a slice; the review station every slice passes through is what makes it true, and this pass checks the feature against it whole.",
    ],
}
DROP = "Property P16, reviewed: the implement skill addresses only the worker"

for name, additions in ADD.items():
    ticket = work / name
    lines = [line for line in ticket.read_text().splitlines() if DROP not in line]
    last = max(i for i, line in enumerate(lines) if line.startswith("- ["))
    ticket.write_text("\n".join(lines[: last + 1] + additions + lines[last + 1 :]) + "\n")
PY
run "$work"

step "the breakdown this check would have passed is in $work"
