#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.14"
# dependencies = ["tyro"]
# ///
"""Build the demo tracker the board's checks render: a git repo for a fictional bookkeeping CLI,
"ledger", whose tickets exercise every element the board shows: every ticket status, every
priority and every size, tickets the user is in the loop for and tickets no worker is kept from,
so that each of a row's marks is laid out somewhere.

Two trees (a parent ticket with six child tickets, one with three) and eleven tickets in no tree,
two builds waiting on a ruling with their branches unmerged and their questions in the tracker's
copy, where `dispatch review` imported them from the worker's report, one build stopped on two
questions of which one is ruled, one ticket whose only question is ruled, one ticket with no
question at all, review pages beside the tickets, acceptance criteria a build in review has half
met, a property cited by the criterion that takes it on, demo scripts and a figure under
agent/show, and four sessions on the commits: three with a transcript under the claude/ config
directory this writes, one worker on another host with none.

    demo_tracker.py /tmp/demo        # build it, print the tracker root
    CLAUDE_CONFIG_DIR=/tmp/demo/claude board /tmp/demo/agent/tickets --no-watch --no-open
"""

# Promoted from agent/prototypes/board-orients/demo-tracker/build.sh (retired with the feature, in
# git history), and converted to the one-ticket model `agent/tickets/ticket-file-contract.md`
# decides: one flat file per ticket, the slug as its id, `parent` for the tree, `needs-user` for a
# ticket worked with the user.

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

def local_sessions(repo: Path) -> dict[str, dict]:
    """The sessions this machine has a transcript of, and what the board shows for each: the title,
    and the directory the session ran in.

    Two of them ran in the ledger itself, which is the repo this builds, so their resume command is
    one that can be run. The third ran in a worktree dispatch has since removed, which is where
    every locally dispatched session ends up: its directory is gone and it is resumable all the
    same.
    """
    return {
        S1: {"title": "Grilling the CSV import", "ai_title": "Grilling the CSV import", "cwd": str(repo)},
        S2: {"title": "Dispatching csv-import, wave 1", "ai_title": "Wave 1 of csv-import",
             "renamed": "Dispatching csv-import, wave 1", "cwd": f"{repo}-csv-import"},
        S3: {"title": "Triage after the holidays", "ai_title": "Triage after the holidays", "cwd": str(repo)},
    }


@dataclass(frozen=True)
class Demo:
    """A built demo tracker: where its pieces are, and the sessions on its commits."""

    repo: Path
    root: Path  # agent/tickets, what the board is pointed at
    transcripts: Path  # this machine's transcripts: $CLAUDE_CONFIG_DIR/projects/<project>/<session id>.jsonl
    sessions: dict[str, dict]  # session id -> the title the board should show, and the cwd, for the ones with a transcript


def build(dest: Path) -> Demo:
    """Write the demo tracker into `dest`, rebuilding it from scratch."""
    repo = Path(dest).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    for stale in (repo / ".git", repo / "agent", repo / "src", repo / "claude"):
        shutil.rmtree(stale, ignore_errors=True)
    # claude/ is a CLAUDE_CONFIG_DIR of its own, so the board reads the fixture's sessions by
    # pointing at it and the demo's resume commands are the ones the fixture's transcripts answer
    demo = Demo(repo, repo / "agent" / "tickets", repo / "claude" / "projects", local_sessions(repo))
    write(repo / ".gitignore", "agent/board.html*\nagent/diffviews/\nclaude/\n")
    git(repo, "init", "-q", "-b", "master")

    csv_import(repo)
    commit(repo, S1, "2026-09-14T10:12:00+02:00", "csv-import: the parent ticket and six slices", "agent/tickets")
    saved_views(repo)
    commit(repo, S1, "2026-09-15T16:40:00+02:00", "saved-views: a parent ticket and three slices", "agent/tickets")
    alone(repo)
    commit(repo, S3, "2026-09-16T09:05:00+02:00", "tickets: work filed during triage", "agent/tickets")

    # the orchestrator claims, a worker builds map-columns on its ticket branch, the orchestrator flips it
    set_status(repo / "agent/tickets/parse-rows.md", "done")
    for claimed in ("agent/tickets/map-columns.md", "agent/tickets/duplicate-rule.md", "agent/tickets/speed-up-tests.md"):
        set_status(repo / claimed, "claimed")
    commit(repo, S2, "2026-09-17T11:20:00+02:00", "csv-import: parse-rows landed; claim map-columns, duplicate-rule and speed-up-tests", "agent/tickets")
    build_in_review(repo)
    stopped_on_questions(repo)
    review_pages(repo)
    transcripts(demo.transcripts, demo.sessions)
    return demo


# ---- the tree csv-import: a parent ticket, child tickets in every status ----


def csv_import(repo: Path) -> None:
    write(repo / "agent/tickets/csv-import.md", """---
status: open
priority: 1
size: XL
---

# CSV import

## Brief

Transactions reach the ledger by hand today: the user reads a bank's CSV export and types each row. This is the whole of reading one in instead.

## Properties

- P1 An import never leaves part of a file in the ledger: all rows land, or none.
- P2 A row already in the ledger is skipped and named in the report, never written twice.

## Acceptance criteria

- [ ] Every child ticket is done, and this ticket's close-out has run over the whole output.
""")
    write(repo / "agent/tickets/parse-rows.md", """---
status: open
parent: csv-import
priority: 1
size: S
---

# Parse the rows

## Brief

The importer reads a bank's CSV export into typed rows and names each line it cannot read, with its line number.

## What to build

A reader for the four export formats the users' banks produce, returning rows and a list of unreadable lines.
""")
    write(repo / "agent/tickets/map-columns.md", """---
status: open
parent: csv-import
blocked-by: [parse-rows]
priority: 1
size: M
gh: [ledger-org/ledger#57]
---

# Map columns once per bank

## Brief

You tell the importer once which column holds the date, the amount and the payee; it remembers that per bank and never asks again.

## What to build

The first import from a bank asks for the mapping and stores it; later imports from that bank use it silently.

## Acceptance criteria

- [ ] The second import from a bank asks nothing and maps the columns the first one did.
- [ ] `csv-import#P1`, reviewed: a mapping that fails halfway writes nothing.
""")
    write(repo / "agent/tickets/duplicate-rule.md", """---
status: open
parent: csv-import
blocked-by: [parse-rows]
priority: 2
size: S
---

# Skip rows already imported

## Brief

Importing the same export twice adds nothing the second time; the skipped rows are named in the report.

## What to build

A row matches an existing transaction on date, amount and payee.

## Acceptance criteria

- [ ] `csv-import#P2`: the second import of one file adds nothing and names every row it skipped.
""")
    write(repo / "agent/tickets/commit-import.md", """---
status: open
parent: csv-import
blocked-by: [map-columns]
priority: 2
size: M
---

# One transaction per import

## Brief

An import either lands whole or not at all, so a crash halfway never leaves half a bank statement in the ledger.

## What to build

The rows of one import are written in one database transaction.
""")
    write(repo / "agent/tickets/import-report.md", """---
status: proposed
parent: csv-import
blocked-by: [duplicate-rule, commit-import]
priority: 3
size: S
---

# The import report

## Brief

After an import, one screen lists the rows added and the rows skipped, with the reason for each skip.

## What to build

Proposed by the orchestrator from duplicate-rule's closing comment: the skipped rows have nowhere to be seen.
""")
    write(repo / "agent/tickets/encoding-sniff.md", """---
status: open
parent: csv-import
priority: 3
size: XS
---

# Latin-1 exports

## Brief

Two banks still export Latin-1; the importer detects it so "Müller" does not arrive as "MÃ¼ller".

## What to build

Detect the encoding from the file's bytes before parsing.
""")


# ---- the tree saved-views: a parent ticket, tickets the user is in the loop for, an edge out ----


def saved_views(repo: Path) -> None:
    write(repo / "agent/tickets/saved-views.md", """---
status: open
priority: 3
size: L
---

# Saved views

## Brief

A filtered list of transactions has to be rebuilt by hand every time. This is the whole of keeping one.
""")
    write(repo / "agent/tickets/view-storage.md", """---
status: open
parent: saved-views
priority: 3
size: S
---

# Where saved views live

## Brief

Find out whether a saved view belongs in the ledger file or beside it; the answer decides whether views survive a sync.

## Questions

- [D1] **Which store keeps a view across a sync without a migration?** The ledger file travels with the data; a file beside it does not.
""")
    write(repo / "agent/tickets/share-link.md", """---
status: open
parent: saved-views
blocked-by: [view-storage, commit-import]
priority: 4
size: M
---

# Share a view as a link

## Brief

A saved view gets a link another user of the same ledger can open, showing the same filter.

## What to build

Waits on the storage answer and on imports writing in one transaction.
""")
    write(repo / "agent/tickets/view-list-shape.md", """---
status: open
parent: saved-views
needs-user: true
priority: 2
size: M
---

# The shape of the view list

## Brief

Three layouts for the list of saved views are drawn side by side; you pick one by looking at them.

## Questions

- [D1] **A sidebar, a command palette, or tabs over the transaction list?** Each is drawn; the pick is yours in front of the render.
""")


# ---- tickets in no tree: one the user is in the loop for, one stopped on a question, a blocked one ----


def alone(repo: Path) -> None:
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
needs-user: true
priority: 1
size: M
---

# Retire the QIF exporter

## Brief

The old QIF exporter has three users left and blocks the storage rewrite; decide whether it goes and what those three get instead.

## Questions

- [D1] **Drop it, keep it read-only, or move its users to the CSV export?** Dropping it costs three users an export they run monthly; keeping it read-only keeps the storage rewrite waiting.
- [D2] **Ask the three users what they export QIF for.** Whether the CSV export already covers it is the thing nobody here knows, and only you can ask them.
""")
    write(repo / "agent/tickets/pick-a-date-library.md", """---
status: open
priority: 3
size: S
---

# A date library

## Brief

Four date formats across the users' banks; find the library that parses all four without per-bank code.

## Questions

- [D1] **Which library, and what does it cost in install size?** The candidates differ by a factor of ten in size.
""")
    write(repo / "agent/tickets/read-the-bank-formats.md", """---
status: open
priority: 4
size: S
---

# The banks' own formats

## Brief

Collect what each of the four banks documents about its export, so the mapping work starts from paper rather than from guesses.

## What to build

Read the four banks' export documentation and write down the columns each one names.
""")
    write(repo / "agent/tickets/staging-credentials.md", """---
status: open
needs-user: true
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
blocked-by: [commit-import]
priority: 4
size: S
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
    write(repo / "agent/tickets/reconcile-statements.md", """---
status: open
priority: 4
size: L
---

# Reconcile a bank statement

## Brief

Tick off a month's transactions against the bank's own statement, so the ledger is known to agree with the bank.

## What to build

A side-by-side view of the two, matching on date and amount, with the unmatched rows listed.
""")
    write(repo / "agent/tickets/storage-rewrite.md", """---
status: open
priority: 5
size: XL
---

# One file per year

## Brief

The single ledger file grows without bound; splitting it per year keeps a decade of books openable, and every command has to learn the new layout.

## What to build

Proposed from the QIF exporter's grilling: the exporter blocks on the same layout question.
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


# ---- two builds waiting on a ruling, their reports imported into the tracker's copy ----


def build_in_review(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "ticket/map-columns")
    write(repo / "src/mapping.py", '"""Column mappings, remembered per bank."""\n')
    commit(repo, S4, "2026-09-18T14:02:00+02:00", "map-columns: the mapping step", "src")
    git(repo, "checkout", "-q", "master")

    # the orchestrator's import: the worker's closing comment, its questions and the review flip
    ticket = repo / "agent/tickets/map-columns.md"
    set_status(ticket, "review")
    ticket.write_text(ticket.read_text().replace("- [ ] The second import", "- [x] The second import"))
    append(ticket, """
## Questions

- [D1] **Remember the mapping per bank or per file name?** Per bank asks one more question on the first import; per file name breaks when a bank renames its export.
- [D2] **Amounts with a comma as the decimal separator** are read as thousands today. Guess from the file, or ask once per bank?
- [D3] **The mappings live in `~/.config/ledger/mappings.toml`.** Fine there, or beside the ledger file so they travel with it?

## Comments

The mapping step is built and remembers a bank's layout, on `ticket/map-columns`, not merged.

**Demo**

    agent/show/map-columns/demo

**Details, if you want them**

- [D4] Assumptions
  - A1 `src/mapping.py:1`: one mapping per bank, keyed by the export's header row.
""")
    write(repo / "agent/show/map-columns/demo", """#!/usr/bin/env bash
# Imports a sample export twice: the first run asks for the mapping, the second uses it.
echo "== first import from Sparkasse: asks for the columns"
echo "date column? Buchungstag   amount column? Betrag   payee column? Empfänger"
echo "== second import: no questions"
echo "12 rows read, 12 added"
""", executable=True)
    write(repo / "agent/show/map-columns/mapping.svg", """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 120" font-family="serif" font-size="13">
  <rect x="10" y="20" width="140" height="80" fill="none" stroke="#8a7f72"/>
  <text x="22" y="45">Buchungstag</text><text x="22" y="67">Betrag</text><text x="22" y="89">Empfänger</text>
  <rect x="210" y="20" width="140" height="80" fill="none" stroke="#8a7f72"/>
  <text x="222" y="45">date</text><text x="222" y="67">amount</text><text x="222" y="89">payee</text>
  <path d="M150 41 H210 M150 63 H210 M150 85 H210" stroke="#426724"/>
</svg>
""")
    commit(repo, S2, "2026-09-18T15:30:00+02:00", "map-columns for review", "agent/tickets/map-columns.md", "agent/show/map-columns")

    git(repo, "checkout", "-q", "-b", "ticket/speed-up-tests")
    write(repo / "src/conftest.py", '"""One template database per session, copied per test."""\n')
    commit(repo, S4, "2026-09-19T10:45:00+02:00", "speed-up-tests: a template database per session", "src")
    git(repo, "checkout", "-q", "master")

    ticket = repo / "agent/tickets/speed-up-tests.md"
    set_status(ticket, "review")
    append(ticket, """
## Questions

- [D1] **Two tests still build their own database** because they migrate it; leave them, or move them to a slow suite?
- [D2] **The template is rebuilt when a migration file changes.** Enough, or also on a schema change made by hand?

## Comments

The suite runs in 48 seconds, down from four minutes, on `ticket/speed-up-tests`, not merged.

**Demo**

    agent/show/speed-up-tests/demo

**Details, if you want them**

- [D3] Friction: the CI cache key did not include the migrations directory.
""")
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
    for page in ("agent/diffviews/map-columns.html", "agent/diffviews/speed-up-tests.html"):
        write(repo / page, f"<!doctype html>\n<title>{Path(page).stem}</title>\n<p>the diff, as diffview renders it\n")


def transcripts(root: Path, sessions: dict[str, dict]) -> None:
    """The transcript of each session this machine has one for; the fourth is a worker on another
    host and has none here.

    S2 also carries the `/rename` name, so a reader has both to tell apart; the other two have only
    Claude Code's own title, which is what every transcript on this machine carries.
    """
    for sid, info in sessions.items():
        transcript(root, sid, info["cwd"], info["ai_title"], info.get("renamed"))


def transcript(root: Path, session: str, cwd: str, ai_title: str, renamed: str | None = None) -> None:
    """One session's transcript, where and as Claude Code writes them: under a directory per
    working directory, every non-alphanumeric character dashed, with the title as an `ai-title`
    record and a `/rename` name as a summary record."""
    path = root / re.sub(r"[^A-Za-z0-9]", "-", cwd) / f"{session}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {"type": "user", "sessionId": session, "cwd": cwd},
        {"type": "ai-title", "aiTitle": ai_title, "sessionId": session},
    ]
    if renamed:
        lines.append({"type": "summary", "customTitle": renamed, "sessionId": session})
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
