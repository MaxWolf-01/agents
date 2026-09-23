#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.14"
# dependencies = ["tyro"]
# ///
"""Build the demo tracker the board's checks render: a git repo for a fictional bookkeeping CLI,
"ledger", whose tickets exercise every element the board shows.

Two features (a confirmed spec with six slices, a draft spec with three tickets, two of them
decisions), eight standalone tickets covering every decision type, two builds waiting on a ruling
on their ticket branches with their questions there, one build stopped on two questions of which
one is ruled, one ticket whose only question is ruled, a needs-human queue, review pages beside the
tickets, demo scripts and a figure under agent/show, and four sessions on the commits: three with a
transcript under the transcripts directory this writes, one worker on another host with none.

    demo_tracker.py /tmp/demo        # build it, print the tracker root
"""

# Promoted from agent/prototypes/board-orients/demo-tracker/build.sh, with its tickets moved to the
# ticket file the board-orients spec decides: the H1 as the short name, `## Brief`, `## Questions`
# with `Ruled` lines, priority and size in frontmatter.

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import tyro

S1 = "a1f3c9e2-4b7d-4e21-9c35-7d2e8f1b6a04"  # grilling the CSV import
S2 = "b52e7d10-9a3c-4f68-8e17-3c9b2a5d4e81"  # orchestrating csv-import
S3 = "c7d04a58-1e2f-4b93-a6c8-5f0e9d3b7c12"  # loose triage
S4 = "d9e1b2c3-7f40-4a5b-8c6d-2e3f4a5b6c7d"  # a worker on agent@pc: no transcript here

TRANSCRIBED = {  # the sessions whose transcript is on this machine: what the board shows for each
    S1: {"title": "Grilling the CSV import", "ai_title": "Grilling the CSV import", "cwd": "/home/max/repos/ledger"},
    S2: {"title": "Dispatching csv-import, wave 1", "ai_title": "Wave 1 of csv-import",
         "renamed": "Dispatching csv-import, wave 1", "cwd": "/home/max/repos/ledger-csv-import"},
    S3: {"title": "Triage after the holidays", "ai_title": "Triage after the holidays", "cwd": "/home/max/repos/ledger"},
}


@dataclass(frozen=True)
class Demo:
    """A built demo tracker: where its pieces are, and the sessions on its commits."""

    repo: Path
    root: Path  # agent/tickets, what the board is pointed at
    transcripts: Path  # stands in for ~/.claude/projects: <project>/<session id>.jsonl
    sessions: dict[str, dict]  # session id -> the title the board should show, and the cwd, for the ones with a transcript


def build(dest: Path) -> Demo:
    """Write the demo tracker into `dest`, rebuilding it from scratch."""
    repo = Path(dest).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    for stale in (repo / ".git", repo / "agent", repo / "src", repo / "transcripts"):
        shutil.rmtree(stale, ignore_errors=True)
    demo = Demo(repo, repo / "agent" / "tickets", repo / "transcripts", TRANSCRIBED)
    write(repo / ".gitignore", "agent/board.html*\nagent/diffviews/\ntranscripts/\n")
    git(repo, "init", "-q", "-b", "master")

    csv_import(repo)
    commit(repo, S1, "2026-09-14T10:12:00+02:00", "csv-import: spec and six slices", "agent/tickets/csv-import")
    saved_views(repo)
    commit(repo, S1, "2026-09-15T16:40:00+02:00", "saved-views: draft spec and three tickets", "agent/tickets/saved-views")
    standalone(repo)
    commit(repo, S3, "2026-09-16T09:05:00+02:00", "tickets: standalone work filed during triage", "agent/tickets")

    # the orchestrator claims, a worker builds 02 on its ticket branch, the orchestrator flips it
    set_status(repo / "agent/tickets/csv-import/01-parse-rows.md", "done")
    for claimed in ("agent/tickets/csv-import/02-map-columns.md", "agent/tickets/csv-import/03-duplicate-rule.md", "agent/tickets/speed-up-tests.md"):
        set_status(repo / claimed, "claimed")
    commit(repo, S2, "2026-09-17T11:20:00+02:00", "csv-import: 01 landed; claim 02 and 03; claim speed-up-tests", "agent/tickets")
    build_in_review(repo)
    stopped_on_questions(repo)
    review_pages(repo)
    transcripts(demo.transcripts)
    return demo


# ---- the feature csv-import: a confirmed spec, tickets in every status, local edges ----


def csv_import(repo: Path) -> None:
    write(repo / "agent/tickets/csv-import/spec.md", """---
status: confirmed
---

# CSV import

## Problem Statement

Transactions reach the ledger by hand today: the user reads a bank's CSV export and types each row.

## Properties

- An import never leaves part of a file in the ledger: all rows land, or none.
- A row already in the ledger is skipped and named in the report, never written twice.
""")
    write(repo / "agent/tickets/csv-import/01-parse-rows.md", """---
status: open
priority: 1
size: S
---

# Parse the rows

## Brief

The importer reads a bank's CSV export into typed rows and names each line it cannot read, with its line number.

## What to build

A reader for the four export formats the users' banks produce, returning rows and a list of unreadable lines.
""")
    write(repo / "agent/tickets/csv-import/02-map-columns.md", """---
status: open
priority: 1
size: M
blocked-by: [01]
gh: [ledger-org/ledger#57]
---

# Map columns once per bank

## Brief

You tell the importer once which column holds the date, the amount and the payee; it remembers that per bank and never asks again.

## What to build

The first import from a bank asks for the mapping and stores it; later imports from that bank use it silently.

## Acceptance criteria

- [ ] Property, reviewed: a mapping that fails halfway writes nothing.
""")
    write(repo / "agent/tickets/csv-import/03-duplicate-rule.md", """---
status: open
priority: 2
size: S
blocked-by: [01]
---

# Skip rows already imported

## Brief

Importing the same export twice adds nothing the second time; the skipped rows are named in the report.

## What to build

A row matches an existing transaction on date, amount and payee.
""")
    write(repo / "agent/tickets/csv-import/04-commit-import.md", """---
status: open
priority: 2
size: M
blocked-by: [02]
---

# One transaction per import

## Brief

An import either lands whole or not at all, so a crash halfway never leaves half a bank statement in the ledger.

## What to build

The rows of one import are written in one database transaction.
""")
    write(repo / "agent/tickets/csv-import/05-import-report.md", """---
status: proposed
priority: 3
size: S
blocked-by: [03, 04]
---

# The import report

## Brief

After an import, one screen lists the rows added and the rows skipped, with the reason for each skip.

## What to build

Proposed by the orchestrator from 03's closing comment: the skipped rows have nowhere to be seen.
""")
    write(repo / "agent/tickets/csv-import/06-encoding-sniff.md", """---
status: open
priority: 3
size: XS
---

# Latin-1 exports

## Brief

Two banks still export Latin-1; the importer detects it so "Müller" does not arrive as "MÃ¼ller".

## What to build

Detect the encoding from the file's bytes before parsing.
""")


# ---- the feature saved-views: a draft spec, decision tickets, a cross-feature edge ----


def saved_views(repo: Path) -> None:
    write(repo / "agent/tickets/saved-views/spec.md", """---
status: draft
---

# Saved views

## Problem Statement

A filtered list of transactions has to be rebuilt by hand every time.
""")
    write(repo / "agent/tickets/saved-views/01-view-storage.md", """---
status: open
type: research
priority: 3
size: S
---

# Where saved views live

## Brief

Find out whether a saved view belongs in the ledger file or beside it; the answer decides whether views survive a sync.

## Questions

- [D1] **Which store keeps a view across a sync without a migration?** The ledger file travels with the data; a file beside it does not.
""")
    write(repo / "agent/tickets/saved-views/02-share-link.md", """---
status: open
priority: 4
size: M
blocked-by: [01, csv-import/04]
---

# Share a view as a link

## Brief

A saved view gets a link another user of the same ledger can open, showing the same filter.

## What to build

Waits on the storage answer and on imports writing in one transaction.
""")
    write(repo / "agent/tickets/saved-views/03-view-list-shape.md", """---
status: open
type: prototype
priority: 2
size: M
---

# The shape of the view list

## Brief

Three layouts for the list of saved views are drawn side by side; you pick one by looking at them.

## Questions

- [D1] **A sidebar, a command palette, or tabs over the transaction list?** Each is drawn; the pick is yours in front of the render.
""")


# ---- standalone tickets: each decision type, a question that stops a build, a blocked one ----


def standalone(repo: Path) -> None:
    write(repo / "agent/tickets/flaky-upload-test.md", """---
status: open
priority: 1
size: XS
---

# The flaky upload test

## Brief

`test_upload` times out on slow CI machines, failing one run in ten; the fix waits on which of two remedies you want.

## What to build

Make the test deterministic on slow machines.
""")
    write(repo / "agent/tickets/retire-legacy-exporter.md", """---
status: open
type: grilling
priority: 1
size: M
---

# Retire the QIF exporter

## Brief

The old QIF exporter has three users left and blocks the storage rewrite; decide whether it goes and what those three get instead.

## Questions

- [D1] **Drop it, keep it read-only, or move its users to the CSV export?** Dropping it costs three users an export they run monthly; keeping it read-only keeps the storage rewrite waiting.
""")
    write(repo / "agent/tickets/pick-a-date-library.md", """---
status: open
type: research
priority: 3
size: S
---

# A date library

## Brief

Four date formats across the users' banks; find the library that parses all four without per-bank code.

## Questions

- [D1] **Which library, and what does it cost in install size?** The candidates differ by a factor of ten in size.
""")
    write(repo / "agent/tickets/staging-credentials.md", """---
status: open
type: legwork
priority: 2
size: XS
---

# Sandbox credentials

## Brief

The importer can only be tried against real exports with sandbox access; someone has to sign up and put the key where the tests find it.

## Questions

- [D1] **Whose card does the sandbox go on?** It is free for a year, then billed.
  - Ruled 2026-09-16: the team card.

## What to do

Sign up for the sandbox, store the key in the test secrets.
""")
    # the queue the board reads until the spec's ticket 10 migrates it into the tickets it belongs to
    write(repo / "agent/tickets/needs-human.md", "- the QIF exporter's three users :: ask them what they export it for, before retire-legacy-exporter is decided\n")
    write(repo / "agent/tickets/speed-up-tests.md", """---
status: open
priority: 2
size: S
gh: [ledger-org/ledger#42]
---

# A faster test suite

## Brief

The suite takes four minutes because every test builds its own database; sharing one template database brings it under a minute.

## What to build

A session-scoped template database, copied per test.
""")
    write(repo / "agent/tickets/export-to-xlsx.md", """---
status: open
priority: 4
size: S
blocked-by: [csv-import/04]
---

# Export to Excel

## Brief

Accountants ask for .xlsx; the export reuses the import's transaction boundary, so it waits on it.

## What to build

An `export --xlsx` command.
""")
    write(repo / "agent/tickets/tidy-cli-help.md", """---
status: proposed
priority: 4
size: XS
---

# Tidy the CLI help

## Brief

`ledger --help` lists twenty commands alphabetically; the four daily ones should come first.

## What to build

Proposed by a worker's closing comment: the help order cost it a search.
""")
    write(repo / "agent/tickets/upgrade-python.md", """---
status: done
priority: 3
size: XS
---

# Python 3.14

## Brief

The project runs and tests on Python 3.14.

## What to build

Bump the interpreter pin and fix the two deprecations.
""")


# ---- two builds waiting on a ruling, their questions on their ticket branches ----


def build_in_review(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "ticket/csv-import/02-map-columns")
    write(repo / "src/mapping.py", '"""Column mappings, remembered per bank."""\n')
    ticket = repo / "agent/tickets/csv-import/02-map-columns.md"
    set_status(ticket, "review")
    append(ticket, """
## Questions

- [D1] **Remember the mapping per bank or per file name?** Per bank asks one more question on the first import; per file name breaks when a bank renames its export.
- [D2] **Amounts with a comma as the decimal separator** are read as thousands today. Guess from the file, or ask once per bank?
- [D3] **The mappings live in `~/.config/ledger/mappings.toml`.** Fine there, or beside the ledger file so they travel with it?

## Comments

The mapping step is built and remembers a bank's layout; on branch `ticket/csv-import/02-map-columns`, not merged.

**Demo**

    agent/show/csv-import/02-map-columns/demo

**Details, if you want them**

- [D4] Assumptions
  - A1 `src/mapping.py:1`: one mapping per bank, keyed by the export's header row.
""")
    commit(repo, S4, "2026-09-18T14:02:00+02:00", "csv-import: 02-map-columns, the mapping step", "src", "agent/tickets/csv-import/02-map-columns.md")
    git(repo, "checkout", "-q", "master")

    set_status(ticket, "review")
    write(repo / "agent/show/csv-import/02-map-columns/demo", """#!/usr/bin/env bash
# Imports a sample export twice: the first run asks for the mapping, the second uses it.
echo "== first import from Sparkasse: asks for the columns"
echo "date column? Buchungstag   amount column? Betrag   payee column? Empfänger"
echo "== second import: no questions"
echo "12 rows read, 12 added"
""", executable=True)
    write(repo / "agent/show/csv-import/02-map-columns/mapping.svg", """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 120" font-family="serif" font-size="13">
  <rect x="10" y="20" width="140" height="80" fill="none" stroke="#8a7f72"/>
  <text x="22" y="45">Buchungstag</text><text x="22" y="67">Betrag</text><text x="22" y="89">Empfänger</text>
  <rect x="210" y="20" width="140" height="80" fill="none" stroke="#8a7f72"/>
  <text x="222" y="45">date</text><text x="222" y="67">amount</text><text x="222" y="89">payee</text>
  <path d="M150 41 H210 M150 63 H210 M150 85 H210" stroke="#426724"/>
</svg>
""")
    commit(repo, S2, "2026-09-18T15:30:00+02:00", "csv-import: 02-map-columns for review", "agent/tickets/csv-import/02-map-columns.md", "agent/show/csv-import")

    git(repo, "checkout", "-q", "-b", "ticket/master/speed-up-tests")
    write(repo / "src/conftest.py", '"""One template database per session, copied per test."""\n')
    ticket = repo / "agent/tickets/speed-up-tests.md"
    set_status(ticket, "review")
    append(ticket, """
## Questions

- [D1] **Two tests still build their own database** because they migrate it; leave them, or move them to a slow suite?
- [D2] **The template is rebuilt when a migration file changes.** Enough, or also on a schema change made by hand?

## Comments

The suite runs in 48 seconds, down from four minutes; on branch `ticket/master/speed-up-tests`, not merged.

**Demo**

    agent/show/speed-up-tests/demo

**Details, if you want them**

- [D3] Friction: the CI cache key did not include the migrations directory.
""")
    commit(repo, S4, "2026-09-19T10:45:00+02:00", "speed-up-tests: a template database per session", "src", "agent/tickets/speed-up-tests.md")
    git(repo, "checkout", "-q", "master")

    set_status(ticket, "review")
    write(repo / "agent/show/speed-up-tests/demo", """#!/usr/bin/env bash
# Runs the suite twice and prints the wall time of each run.
echo "== before: 4 min 02 s"
echo "== after: 48 s"
""", executable=True)
    commit(repo, S2, "2026-09-19T11:10:00+02:00", "speed-up-tests for review", "agent/tickets/speed-up-tests.md", "agent/show/speed-up-tests")


# ---- a build stopped on two questions; one answered later through a Ruled line ----


def stopped_on_questions(repo: Path) -> None:
    ticket = repo / "agent/tickets/flaky-upload-test.md"
    append(ticket, """
## Questions

- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing.
- [D2] **Keep the test in the fast suite?** It takes four seconds with either fix.

## Comments

**2026-09-20** Stopped before building: the remedy is a design choice.
""")
    commit(repo, S3, "2026-09-20T17:15:00+02:00", "flaky-upload-test: stopped on two questions", "agent/tickets/flaky-upload-test.md")
    text = ticket.read_text().replace(
        "- [D2] **Keep the test in the fast suite?** It takes four seconds with either fix.",
        "- [D2] **Keep the test in the fast suite?** It takes four seconds with either fix.\n  - Ruled 2026-09-21: keep it in the fast suite.",
    )
    ticket.write_text(text)
    commit(repo, S1, "2026-09-21T09:30:00+02:00", "flaky-upload-test: D2 ruled", "agent/tickets/flaky-upload-test.md")


def review_pages(repo: Path) -> None:
    """What dispatch renders for a build waiting on a ruling; gitignored, so they are written, not committed."""
    for page in ("agent/diffviews/csv-import/02-map-columns.html", "agent/diffviews/speed-up-tests.html"):
        write(repo / page, f"<!doctype html>\n<title>{Path(page).stem}</title>\n<p>the diff, as diffview renders it\n")


def transcripts(root: Path) -> None:
    """A transcript per session, where and as Claude Code writes them: one directory per working
    directory, every non-alphanumeric character dashed, and the title as an `ai-title` record.

    S2 also carries the `/rename` name, so a reader has both to tell apart; the other two have only
    Claude Code's own title, which is what every transcript on this machine carries.
    """
    for sid, info in TRANSCRIBED.items():
        path = root / re.sub(r"[^A-Za-z0-9]", "-", info["cwd"]) / f"{sid}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            {"type": "user", "sessionId": sid, "cwd": info["cwd"]},
            {"type": "ai-title", "aiTitle": info["ai_title"], "sessionId": sid},
        ]
        if renamed := info.get("renamed"):
            lines.append({"type": "summary", "customTitle": renamed, "sessionId": sid})
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))


# ---- writing it ------------------------------------------------------------


def write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if executable:
        path.chmod(0o755)


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text() + text)


def set_status(path: Path, status: str) -> None:
    lines = path.read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("status: "):
            lines[i] = f"status: {status}\n"
            break
    path.write_text("".join(lines))


def git(repo: Path, *args: str, when: str | None = None) -> str:
    """git in the demo repo, run off the machine's identity, hooks and signing key."""
    done = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=demo", "-c", "user.email=demo@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        capture_output=True, text=True,
        env=os.environ | ({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when} if when else {}),
    )
    assert done.returncode == 0, f"git {' '.join(args)} failed in {repo}: {done.stderr.strip()}"
    return done.stdout.strip()


def commit(repo: Path, session: str, when: str, message: str, *paths: str) -> None:
    """One commit carrying the `Session:` trailer every session's commits carry."""
    git(repo, "add", "--", *paths)
    git(repo, "commit", "-q", "-m", message, "-m", f"Session: {session}", when=when)


@dataclass
class Args:
    dest: Annotated[Path, tyro.conf.Positional]
    """Directory to build the demo tracker in; anything this script wrote there before is replaced."""


def main(args: Args) -> None:
    print(build(args.dest).root)


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
