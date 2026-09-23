#!/usr/bin/env bash
# Builds a demo tracker for the board-orients prototype: a small git repo for a fictional
# bookkeeping CLI, "ledger", whose tickets exercise every element the board renders.
# Rerun to rebuild from scratch; it removes only what it creates here, then renders the board.
#
#   agent/prototypes/board-orients/demo-tracker/build.sh [output directory, default /var/tmp/board-orients-demo]
#
# Its tickets follow the prototype's reading (questions under a closing comment's "I need from you",
# a "Ruled: D2" line, a `name:` field), not yet the spec's ticket file.
set -euo pipefail

proto=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/board.py
here=${1:-/var/tmp/board-orients-demo}
mkdir -p "$here"
here=$(cd "$here" && pwd)
cd "$here"
rm -rf .git agent src README.md .gitignore board.html board.html.stamp.js

# Three sessions on this machine (in sessions.json, standing in for their transcripts) and one
# worker session on another host, which the board leaves out.
S1=a1f3c9e2-4b7d-4e21-9c35-7d2e8f1b6a04   # grilling the CSV import
S2=b52e7d10-9a3c-4f68-8e17-3c9b2a5d4e81   # orchestrating csv-import
S3=c7d04a58-1e2f-4b93-a6c8-5f0e9d3b7c12   # loose triage
S4=d9e1b2c3-7f40-4a5b-8c6d-2e3f4a5b6c7d   # a worker on agent@pc: no transcript here

cat > sessions.json <<EOF
{
  "$S1": {"title": "Grilling the CSV import", "cwd": "/home/max/repos/ledger"},
  "$S2": {"title": "Dispatching csv-import, wave 1", "cwd": "/home/max/repos/ledger-csv-import"},
  "$S3": {"title": "Triage after the holidays", "cwd": "/home/max/repos/ledger"}
}
EOF
printf 'themes: {}\ntickets: {}\nvirtual: {}\n' > fixture.yaml

git init -q -b master
printf 'build.sh\nsessions.json\nfixture.yaml\nboard.html*\nagent/diffviews/\nshots/\n' > .gitignore

commit() { # <session> <date> <message> <paths...>
    local sid=$1 date=$2 msg=$3; shift 3
    git add -- "$@"
    GIT_AUTHOR_DATE=$date GIT_COMMITTER_DATE=$date git -c user.name=demo -c user.email=demo@example.invalid \
        -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -q -m "$msg" -m "Session: $sid"
}
put() { mkdir -p "$(dirname "$1")"; cat > "$1"; }

# ---- the feature csv-import: a confirmed spec, tickets in every status, local edges ----
put agent/tickets/csv-import/spec.md <<'EOF'
---
status: confirmed
---

# CSV import

## Problem Statement

Transactions reach the ledger by hand today: the user reads a bank's CSV export and types each row.

## Properties

- P1 An import never leaves part of a file in the ledger: all rows land, or none.
- P2 A row already in the ledger is skipped and named in the report, never written twice.
EOF

put agent/tickets/csv-import/01-parse-rows.md <<'EOF'
---
status: open
priority: 1
size: S
name: Parse the rows
---

# Parse a bank's CSV export into rows the importer can check

## Brief

The importer reads a bank's CSV export into typed rows and names each line it cannot read, with its line number.

## What to build

A reader for the four export formats the users' banks produce, returning rows and a list of unreadable lines.
EOF

put agent/tickets/csv-import/02-map-columns.md <<'EOF'
---
status: open
priority: 1
size: M
name: Map columns once per bank
blocked-by: [01]
gh: [ledger-org/ledger#57]
---

# Map a CSV's columns onto ledger fields, remembered per bank

## Brief

You tell the importer once which column holds the date, the amount and the payee; it remembers that per bank and never asks again.

## What to build

The first import from a bank asks for the mapping and stores it; later imports from that bank use it silently.

## Acceptance criteria

- [ ] Property P1, reviewed: a mapping that fails halfway writes nothing.
EOF

put agent/tickets/csv-import/03-duplicate-rule.md <<'EOF'
---
status: open
priority: 2
size: S
name: Skip rows already imported
blocked-by: [01]
---

# Skip a row that is already in the ledger

## Brief

Importing the same export twice adds nothing the second time; the skipped rows are named in the report.

## What to build

A row matches an existing transaction on date, amount and payee.
EOF

put agent/tickets/csv-import/04-commit-import.md <<'EOF'
---
status: open
priority: 2
size: M
name: One transaction per import
blocked-by: [02]
---

# Write an import in one transaction

## Brief

An import either lands whole or not at all, so a crash halfway never leaves half a bank statement in the ledger.

## What to build

The rows of one import are written in one database transaction.
EOF

put agent/tickets/csv-import/05-import-report.md <<'EOF'
---
status: proposed
priority: 3
size: S
name: The import report
blocked-by: [03, 04]
---

# Show what an import added and what it skipped

## Brief

After an import, one screen lists the rows added and the rows skipped, with the reason for each skip.

## What to build

Proposed by the orchestrator from 03's closing comment: the skipped rows have nowhere to be seen.
EOF

put agent/tickets/csv-import/06-encoding-sniff.md <<'EOF'
---
status: open
priority: 3
size: XS
name: Latin-1 exports
---

# Read Latin-1 exports without mangling umlauts

## Brief

Two banks still export Latin-1; the importer detects it so "Müller" does not arrive as "MÃ¼ller".

## What to build

Detect the encoding from the file's bytes before parsing.
EOF

commit "$S1" 2026-09-14T10:12:00+02:00 "csv-import: spec and six slices" agent/tickets/csv-import

# ---- the feature saved-views: a draft spec, decision tickets, a cross-feature edge ----
put agent/tickets/saved-views/spec.md <<'EOF'
---
status: draft
---

# Saved views

## Problem Statement

A filtered list of transactions has to be rebuilt by hand every time.
EOF

put agent/tickets/saved-views/01-view-storage.md <<'EOF'
---
status: open
type: research
priority: 3
size: S
name: Where saved views live
---

# Where saved views are stored

## Brief

Find out whether a saved view belongs in the ledger file or beside it; the answer decides whether views survive a sync.

## Question

Which store keeps a view across a sync without a migration?
EOF

put agent/tickets/saved-views/02-share-link.md <<'EOF'
---
status: open
priority: 4
size: M
name: Share a view as a link
blocked-by: [01, csv-import/04]
---

# Share a saved view as a link

## Brief

A saved view gets a link another user of the same ledger can open, showing the same filter.

## What to build

Waits on the storage answer and on imports writing in one transaction.
EOF

put agent/tickets/saved-views/03-view-list-shape.md <<'EOF'
---
status: open
type: prototype
priority: 2
size: M
name: The shape of the view list
---

# The shape of the saved-view list

## Brief

Three layouts for the list of saved views are drawn side by side; you pick one by looking at them.

## Question

A sidebar, a command palette, or tabs over the transaction list?
EOF

commit "$S1" 2026-09-15T16:40:00+02:00 "saved-views: draft spec and three tickets" agent/tickets/saved-views

# ---- standalone tickets: each decision type, a question that stops a build, a blocked one ----
put agent/tickets/flaky-upload-test.md <<'EOF'
---
status: open
priority: 1
size: XS
name: The flaky upload test
---

# `test_upload` fails one CI run in ten

## Brief

The upload test times out on slow CI machines; the fix waits on which of two remedies you want.

## What to build

Make the test deterministic on slow machines.
EOF

put agent/tickets/retire-legacy-exporter.md <<'EOF'
---
status: open
type: grilling
priority: 1
size: M
name: Retire the QIF exporter
---

# Whether the QIF exporter goes, and what replaces it for its last users

## Brief

The old QIF exporter has three users left and blocks the storage rewrite; decide whether it goes and what those three get instead.

## Question

Drop it, keep it read-only, or move its users to the CSV export?
EOF

put agent/tickets/pick-a-date-library.md <<'EOF'
---
status: open
type: research
priority: 3
size: S
name: A date library
---

# Which date library parses every bank's date format

## Brief

Four date formats across the users' banks; find the library that parses all four without per-bank code.

## Question

Which library, and what does it cost in install size?
EOF

put agent/tickets/staging-credentials.md <<'EOF'
---
status: open
type: legwork
priority: 2
size: XS
name: Sandbox credentials
---

# Read-only credentials for the bank's sandbox

## Brief

The importer can only be tried against real exports with sandbox access; someone has to sign up and put the key where the tests find it.

## What to do

Sign up for the sandbox, store the key in the test secrets.
EOF

put agent/tickets/speed-up-tests.md <<'EOF'
---
status: open
priority: 2
size: S
name: A faster test suite
gh: [ledger-org/ledger#42]
---

# The test suite runs in under a minute

## Brief

The suite takes four minutes because every test builds its own database; sharing one template database brings it under a minute.

## What to build

A session-scoped template database, copied per test.
EOF

put agent/tickets/export-to-xlsx.md <<'EOF'
---
status: open
priority: 4
size: S
name: Export to Excel
blocked-by: [csv-import/04]
---

# Export a ledger view to an Excel file

## Brief

Accountants ask for .xlsx; the export reuses the import's transaction boundary, so it waits on it.

## What to build

An `export --xlsx` command.
EOF

put agent/tickets/tidy-cli-help.md <<'EOF'
---
status: proposed
priority: 4
size: XS
name: Tidy the CLI help
---

# The CLI's help text lists commands in the order people use them

## Brief

`ledger --help` lists twenty commands alphabetically; the four daily ones should come first.

## What to build

Proposed by a worker's closing comment: the help order cost it a search.
EOF

put agent/tickets/upgrade-python.md <<'EOF'
---
status: done
priority: 3
size: XS
name: Python 3.14
---

# Run on Python 3.14

## Brief

The project runs and tests on Python 3.14.

## What to build

Bump the interpreter pin and fix the two deprecations.
EOF

commit "$S3" 2026-09-16T09:05:00+02:00 "tickets: standalone work filed during triage" agent/tickets

# ---- the orchestrator claims, a worker builds 02 on its ticket branch, the orchestrator flips it ----
sed -i 's/^status: open$/status: done/' agent/tickets/csv-import/01-parse-rows.md
sed -i 's/^status: open$/status: claimed/' agent/tickets/csv-import/02-map-columns.md agent/tickets/csv-import/03-duplicate-rule.md agent/tickets/speed-up-tests.md
commit "$S2" 2026-09-17T11:20:00+02:00 "csv-import: 01 landed; claim 02 and 03; claim speed-up-tests" agent/tickets

git checkout -q -b ticket/csv-import/02-map-columns
put src/mapping.py <<'EOF'
"""Column mappings, remembered per bank."""
EOF
sed -i 's/^status: claimed$/status: review/' agent/tickets/csv-import/02-map-columns.md
cat >> agent/tickets/csv-import/02-map-columns.md <<'EOF'

## Comments

The mapping step is built and remembers a bank's layout; on branch `ticket/csv-import/02-map-columns`, not merged.

**Demo**

    agent/show/csv-import/02-map-columns/demo

**I need from you**

- [D1] **Remember the mapping per bank or per file name?** Per bank asks one more question on the first import; per file name breaks when a bank renames its export.
- [D2] **Amounts with a comma as the decimal separator** are read as thousands today. Guess from the file, or ask once per bank?
- [D3] **The mappings live in `~/.config/ledger/mappings.toml`.** Fine there, or beside the ledger file so they travel with it?

**Details, if you want them**

- [D4] Assumptions
  - A1 `src/mapping.py:1`: one mapping per bank, keyed by the export's header row.
EOF
commit "$S4" 2026-09-18T14:02:00+02:00 "csv-import: 02-map-columns, the mapping step" src agent/tickets/csv-import/02-map-columns.md
git checkout -q master

sed -i 's/^status: claimed$/status: review/' agent/tickets/csv-import/02-map-columns.md
put agent/show/csv-import/02-map-columns/demo <<'EOF'
#!/usr/bin/env bash
# Imports a sample export twice: the first run asks for the mapping, the second uses it.
echo "== first import from Sparkasse: asks for the columns"
echo "date column? Buchungstag   amount column? Betrag   payee column? Empfänger"
echo "== second import: no questions"
echo "12 rows read, 12 added"
EOF
chmod +x agent/show/csv-import/02-map-columns/demo
put agent/show/csv-import/02-map-columns/mapping.svg <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 120" font-family="serif" font-size="13">
  <rect x="10" y="20" width="140" height="80" fill="none" stroke="#8a7f72"/>
  <text x="22" y="45">Buchungstag</text><text x="22" y="67">Betrag</text><text x="22" y="89">Empfänger</text>
  <rect x="210" y="20" width="140" height="80" fill="none" stroke="#8a7f72"/>
  <text x="222" y="45">date</text><text x="222" y="67">amount</text><text x="222" y="89">payee</text>
  <path d="M150 41 H210 M150 63 H210 M150 85 H210" stroke="#426724"/>
</svg>
EOF
commit "$S2" 2026-09-18T15:30:00+02:00 "csv-import: 02-map-columns for review" agent/tickets/csv-import/02-map-columns.md agent/show/csv-import

git checkout -q -b ticket/master/speed-up-tests
put src/conftest.py <<'EOF'
"""One template database per session, copied per test."""
EOF
sed -i 's/^status: claimed$/status: review/' agent/tickets/speed-up-tests.md
cat >> agent/tickets/speed-up-tests.md <<'EOF'

## Comments

The suite runs in 48 seconds, down from four minutes; on branch `ticket/master/speed-up-tests`, not merged.

**Demo**

    agent/show/speed-up-tests/demo

**I need from you**

1. `[D1]` **Two tests still build their own database** because they migrate it; leave them, or move them to a slow suite?
2. `[D2]` **The template is rebuilt when a migration file changes.** Enough, or also on a schema change made by hand?

**Details, if you want them**

- [D3] Friction: the CI cache key did not include the migrations directory.
EOF
commit "$S4" 2026-09-19T10:45:00+02:00 "speed-up-tests: a template database per session" src agent/tickets/speed-up-tests.md
git checkout -q master

sed -i 's/^status: claimed$/status: review/' agent/tickets/speed-up-tests.md
put agent/show/speed-up-tests/demo <<'EOF'
#!/usr/bin/env bash
# Runs the suite twice and prints the wall time of each run.
echo "== before: 4 min 02 s"
echo "== after: 48 s"
EOF
chmod +x agent/show/speed-up-tests/demo
commit "$S2" 2026-09-19T11:10:00+02:00 "speed-up-tests for review" agent/tickets/speed-up-tests.md agent/show/speed-up-tests

# ---- a build stopped on two questions; one answered later through a Ruled line ----
cat >> agent/tickets/flaky-upload-test.md <<'EOF'

## Comments

**2026-09-20** Stopped before building: the remedy is a design choice.

**I need from you**

- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing.
- [D2] **Keep the test in the fast suite?** It takes four seconds with either fix.
EOF
commit "$S3" 2026-09-20T17:15:00+02:00 "flaky-upload-test: stopped on two questions" agent/tickets/flaky-upload-test.md
cat >> agent/tickets/flaky-upload-test.md <<'EOF'

**2026-09-21** The user's answer to D2, relayed:

Ruled: D2 (keep it in the fast suite)
EOF
commit "$S1" 2026-09-21T09:30:00+02:00 "flaky-upload-test: D2 ruled" agent/tickets/flaky-upload-test.md

# ---- review pages, as dispatch renders them for the two builds waiting on a ruling ----
mkdir -p agent/diffviews/csv-import
diffview "$here@$(git merge-base master ticket/csv-import/02-map-columns)..ticket/csv-import/02-map-columns" \
    -o "$here/agent/diffviews/csv-import/02-map-columns.html" >/dev/null
diffview "$here@$(git merge-base master ticket/master/speed-up-tests)..ticket/master/speed-up-tests" \
    -o "$here/agent/diffviews/speed-up-tests.html" >/dev/null

# ---- the board ----
BOARD_PROTO_FIXTURE="$here/fixture.yaml" BOARD_PROTO_SESSIONS="$here/sessions.json" \
    uv run "$proto" "$here/agent/tickets" --no-watch --no-open --out "$here/board.html"
