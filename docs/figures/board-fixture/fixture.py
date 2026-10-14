"""The demo project the board and review-page screenshots are taken of: its code, commit by commit.

`build.py` lays the repo down from these, so the history a review page shows is real and every
branch a ticket names exists. The project is invented: a small expenses app, "ledger", whose first
tree of tickets imports bank CSVs and whose second saves filtered views. `build.py` runs the suite
at the tip of every branch, so this code stays a worked example rather than something that only
looks like one.
"""

GLOSSARY = """\
# ledger

**Row**: one line of an imported statement, before it becomes an entry.
_Avoid_: record, item

**Entry**: a movement of money on an account, its amount in whole cents.
_Avoid_: transaction, txn

**Parse report**: what one upload produced: the rows that parsed, and every line that did not, with its reason.
"""

MAKEFILE = "test:\n\tuv run --with pytest pytest -q\n"

# --- main: the app before either tree ---------------------------------------

SKELETON = {
    "pytest.ini": "[pytest]\npythonpath = .\n",
    "ledger/__init__.py": '"""A small expenses app."""\n',
    "ledger/account.py": '''\
"""An account and the entries it holds."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entry:
    """One movement of money on an account: when, to or from whom, and how much in cents."""

    date: str
    payee: str
    cents: int


@dataclass
class Account:
    """The entries an account holds, in the order they were added."""

    entries: list[Entry] = field(default_factory=list)
''',
    "ledger/export.py": '''\
"""The CSV export the old account screen offered, kept until nothing calls it."""

import csv
from pathlib import Path

from ledger.account import Account

HEADER = ["date", "description", "amount"]


def export_csv(account: Account, path: Path) -> None:
    """Write the account's entries to `path`, under the column names the banks use."""
    with path.open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(HEADER)
        for entry in account.entries:
            writer.writerow([entry.date, entry.payee, f"{entry.cents / 100:.2f}"])
''',
    "tests/test_export.py": '''\
import csv

from ledger.account import Account, Entry
from ledger.export import export_csv


def test_export_round_trip(tmp_path) -> None:
    account = Account([Entry("2026-02-01", "Coffee Roasters", -480)])
    path = tmp_path / "export.csv"
    export_csv(account, path)
    with path.open() as written:
        rows = list(csv.reader(written))
    assert rows == [["date", "description", "amount"], ["2026-02-01", "Coffee Roasters", "-4.80"]]
''',
}

PIN = {".python-version": "3.13\n"}

# --- csv-import: the seam its grilling designed, stubbed by the orchestrator -

SEAM = {
    "ledger/importer.py": '''\
"""Turn an uploaded statement into rows an account can accept."""

from dataclasses import dataclass

DEFAULT_COLUMNS = {"date": "date", "payee": "description", "amount": "amount"}


@dataclass(frozen=True)
class Row:
    """One line of a statement, before it becomes an entry."""

    date: str
    payee: str
    cents: int


@dataclass(frozen=True)
class ParseReport:
    """What one upload produced: the rows that parsed, and the lines that did not."""

    rows: list[Row]
    rejected: list[tuple[int, str]]


def parse_rows(text: str, columns: dict[str, str]) -> list[Row]:
    """The rows of `text` that parsed, under a mapping of column name to field."""
    raise NotImplementedError


def parse_report(text: str, columns: dict[str, str]) -> ParseReport:
    """Every line of `text`, sorted into the rows that parsed and the ones that did not."""
    raise NotImplementedError
''',
}

# --- upload-and-parse-report ------------------------------------------------

PARSE_REPORT = {
    "ledger/importer.py": '''\
"""Turn an uploaded statement into rows an account can accept."""

import csv
from dataclasses import dataclass
from io import StringIO

DEFAULT_COLUMNS = {"date": "date", "payee": "description", "amount": "amount"}


@dataclass(frozen=True)
class Row:
    """One line of a statement, before it becomes an entry."""

    date: str
    payee: str
    cents: int


@dataclass(frozen=True)
class ParseReport:
    """What one upload produced: the rows that parsed, and the lines that did not."""

    rows: list[Row]
    rejected: list[tuple[int, str]]


def parse_rows(text: str, columns: dict[str, str]) -> list[Row]:
    """The rows of `text` that parsed, under a mapping of column name to field."""
    return parse_report(text, columns).rows


def parse_report(text: str, columns: dict[str, str]) -> ParseReport:
    """Parse every line, so the upload can be shown whole before anything is committed.

    A line the mapping cannot read is rejected with its number and the reason, never
    dropped: the report is what the human rules on before the import is committed.
    """
    rows: list[Row] = []
    rejected: list[tuple[int, str]] = []
    for number, record in enumerate(csv.DictReader(StringIO(text)), start=2):
        try:
            rows.append(
                Row(
                    date=required(record, columns["date"]),
                    payee=required(record, columns["payee"]),
                    cents=to_cents(required(record, columns["amount"])),
                )
            )
        except (KeyError, ValueError) as exc:
            rejected.append((number, str(exc)))
    return ParseReport(rows=rows, rejected=rejected)


def required(record: dict[str, str], column: str) -> str:
    """The column's value, or a ValueError naming the column that was blank."""
    value = (record.get(column) or "").strip()
    if not value:
        raise ValueError(f"{column} is blank")
    return value


def to_cents(amount: str) -> int:
    """Whole cents from a decimal amount, so no entry ever carries a rounded float."""
    whole, _, fraction = amount.replace(",", "").partition(".")
    sign = -1 if whole.startswith("-") else 1
    return int(whole) * 100 + int(fraction.ljust(2, "0")[:2]) * sign
''',
    "tests/test_importer.py": '''\
from ledger.importer import DEFAULT_COLUMNS, Row, parse_report, to_cents

STATEMENT = """date,description,amount
2026-02-01,Coffee Roasters,-4.80
2026-02-02,Salary,2400.00
2026-02-03,,-12.00
"""


def test_the_report_keeps_every_line_it_could_not_read() -> None:
    report = parse_report(STATEMENT, DEFAULT_COLUMNS)
    assert report.rows == [
        Row(date="2026-02-01", payee="Coffee Roasters", cents=-480),
        Row(date="2026-02-02", payee="Salary", cents=240000),
    ]
    assert [number for number, _ in report.rejected] == [4]


def test_every_line_is_accepted_or_reported_never_both() -> None:
    report = parse_report(STATEMENT, DEFAULT_COLUMNS)
    assert len(report.rows) + len(report.rejected) == len(STATEMENT.splitlines()) - 1


def test_an_amount_becomes_whole_cents() -> None:
    assert to_cents("-4.80") == -480
    assert to_cents("2,400") == 240000
''',
}

# --- map-columns-to-fields --------------------------------------------------

MAPPING = {
    "ledger/mapping.py": '''\
"""Which of a bank's columns is the date, the payee and the amount."""

from ledger.importer import DEFAULT_COLUMNS


def mapping_for(bank: str, remembered: dict[str, dict[str, str]]) -> dict[str, str]:
    """The mapping this bank arrived with last time, or the default to correct on screen."""
    return remembered.get(bank, DEFAULT_COLUMNS)


def remember(bank: str, columns: dict[str, str], remembered: dict[str, dict[str, str]]) -> None:
    """Keep this mapping, so the next statement from the same bank arrives already mapped."""
    remembered[bank] = dict(columns)
''',
    "tests/test_mapping.py": '''\
from ledger.importer import DEFAULT_COLUMNS
from ledger.mapping import mapping_for, remember


def test_a_bank_arrives_with_the_default_mapping_the_first_time() -> None:
    assert mapping_for("Ourbank", {}) == DEFAULT_COLUMNS


def test_a_corrected_mapping_comes_back_for_the_next_statement() -> None:
    remembered: dict[str, dict[str, str]] = {}
    remember("Ourbank", {"date": "booked", "payee": "counterparty", "amount": "value"}, remembered)
    assert mapping_for("Ourbank", remembered)["date"] == "booked"
''',
}

# --- commit-the-import ------------------------------------------------------

COMMIT_TEST = '''\
from ledger.account import Account
from ledger.commit import commit_import, dry_run
from ledger.importer import DEFAULT_COLUMNS

STATEMENT = """date,description,amount
2026-02-01,Coffee Roasters,-4.80
2026-02-02,Salary,2400.00
"""


def test_the_dry_run_and_the_commit_agree() -> None:
    account = Account()
    assert dry_run(account, STATEMENT, DEFAULT_COLUMNS) == commit_import(account, STATEMENT, DEFAULT_COLUMNS)
'''

COMMIT = {
    "ledger/commit.py": '''\
"""Turn a statement's accepted rows into entries on an account."""

from ledger.account import Account, Entry
from ledger.importer import parse_report


def commit_import(account: Account, text: str, columns: dict[str, str]) -> list[Entry]:
    """Add the statement's accepted rows to the account, skipping duplicates; the entries added."""
    added = dry_run(account, text, columns)
    account.entries.extend(added)
    return added


def dry_run(account: Account, text: str, columns: dict[str, str]) -> list[Entry]:
    """What committing this statement would add, so the human sees it before it lands.

    A row whose date, payee and amount match an entry already there is the same row twice,
    and is skipped.
    """
    settled = set(account.entries)
    entries = (Entry(row.date, row.payee, row.cents) for row in parse_report(text, columns).rows)
    return [entry for entry in entries if entry not in settled]
''',
    "tests/test_commit.py": COMMIT_TEST,
}

# --- the close-out's one fix, on csv-import's branch ------------------------

SETTLED = {"tests/test_commit.py": COMMIT_TEST + '''

def test_a_re_issued_statement_adds_nothing() -> None:
    account = Account()
    commit_import(account, STATEMENT, DEFAULT_COLUMNS)
    assert commit_import(account, STATEMENT, DEFAULT_COLUMNS) == []
'''}

# --- saved-views: filters-as-data -------------------------------------------

FILTERS = {
    "ledger/filters.py": '''\
"""The filter bar's state as one value: what saving, reopening and sharing a view store."""

from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode


@dataclass(frozen=True)
class Filters:
    """The date range, the accounts and the payee the entries are narrowed to; empty is all."""

    since: str = ""
    until: str = ""
    accounts: tuple[str, ...] = ()
    payee: str = ""

    def to_text(self) -> str:
        """The value as one line of text, the form a saved view and a link both carry."""
        return urlencode({"since": self.since, "until": self.until,
                          "accounts": ",".join(self.accounts), "payee": self.payee})

    @classmethod
    def from_text(cls, text: str) -> "Filters":
        """The value `to_text` wrote; a field the text leaves out is empty."""
        read = {key: values[0] for key, values in parse_qs(text, keep_blank_values=True).items()}
        return cls(read.get("since", ""), read.get("until", ""),
                   tuple(filter(None, read.get("accounts", "").split(","))), read.get("payee", ""))
''',
    "tests/test_filters.py": '''\
from ledger.filters import Filters


def test_a_filter_value_survives_the_round_trip_dates_included() -> None:
    value = Filters(since="2026-02-01", until="2026-02-28", accounts=("checking", "card"), payee="Coffee")
    assert Filters.from_text(value.to_text()) == value


def test_no_filter_is_every_entry() -> None:
    assert Filters.from_text(Filters().to_text()) == Filters()
''',
}

# --- flaky-export-test ------------------------------------------------------

STEADY = {
    "ledger/export.py": '''\
"""The CSV export the old account screen offered, kept until nothing calls it."""

import csv
from pathlib import Path
from typing import TextIO

from ledger.account import Account

HEADER = ["date", "description", "amount"]


def export_csv(account: Account, path: Path) -> None:
    """Write the account's entries to `path`, under the column names the banks use."""
    with path.open("w", newline="") as out:
        write_csv(account, out)


def write_csv(account: Account, out: TextIO) -> None:
    """Write the account's entries to an open text stream, a file or a buffer alike."""
    writer = csv.writer(out)
    writer.writerow(HEADER)
    for entry in account.entries:
        writer.writerow([entry.date, entry.payee, f"{entry.cents / 100:.2f}"])
''',
    "tests/test_export.py": '''\
import csv
from io import StringIO

from ledger.account import Account, Entry
from ledger.export import write_csv


def test_export_round_trip() -> None:
    account = Account([Entry("2026-02-01", "Coffee Roasters", -480)])
    out = StringIO()
    write_csv(account, out)
    rows = list(csv.reader(StringIO(out.getvalue())))
    assert rows == [["date", "description", "amount"], ["2026-02-01", "Coffee Roasters", "-4.80"]]
''',
}

# --- the worker's notes on upload-and-parse-report's review page ------------

NOTES = {
    "notes": [
        {
            "id": 1,
            "path": "ledger/importer.py",
            "line": 34,
            "end": 37,
            "side": "new",
            "text": "The parent ticket's P2 says a line the mapping cannot read is reported, not dropped, so "
                    "the report carries both lists and a test can count them against the upload. Rejecting "
                    "per line rather than per file is what keeps the mapping screen useful on a statement "
                    "with one bad row.",
        },
        {
            "id": 2,
            "path": "ledger/importer.py",
            "line": 62,
            "end": 66,
            "side": "new",
            "text": "Cents, not a float: the glossary's Entry carries an integer amount. One assumption I "
                    "could not settle from the ticket, flagged rather than guessed at: a statement in a "
                    "currency with three decimal places truncates here.",
        },
        {
            "id": 3,
            "path": "ledger/export.py",
            "text": "Read and deliberately left alone. `export_csv` writes the format this parser reads, "
                    "so it looked like a test oracle, but nothing calls it any more; retiring it is its "
                    "own ticket, not this slice's.",
        },
    ]
}
