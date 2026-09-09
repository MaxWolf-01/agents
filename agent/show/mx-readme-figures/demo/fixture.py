"""The demo project the board and review-page screenshots are taken of.

One dict per file, and three commits' worth of code, so `build.py` can lay the
repo down from scratch. The project is invented: a small expenses app whose
first feature imports bank CSVs and whose second saves filtered views.
"""

CONTEXT = """\
# ledger

**Row**: one line of an imported statement, before it becomes an entry.
_Avoid_: record, item

**Entry**: a row the import accepted, stored against an account.
_Avoid_: transaction, txn
"""

MAKEFILE = "test:\n\tuv run pytest -q\n\nharden:\n\tharden $(ARGS)\n"

C1 = {
    "ledger/__init__.py": '"""A small expenses app."""\n',
    "ledger/importer.py": '''\
"""Turn an uploaded statement into rows the account can accept."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    """One line of a statement, before it becomes an entry."""

    date: str
    payee: str
    cents: int


def parse_rows(text: str, columns: dict[str, str]) -> list[Row]:
    """Parse the uploaded text into rows, under a mapping of column name to field."""
    raise NotImplementedError
''',
    "tests/test_importer.py": '''\
import pytest

from ledger.importer import parse_rows


def test_an_empty_upload_parses_to_no_rows() -> None:
    with pytest.raises(NotImplementedError):
        parse_rows("", {})
''',
}

C2 = {
    "tests/properties/test_import.py": '''\
"""The properties the import spec states, as checks over generated statements.

An expected failure names the ticket that lifts it; the behaviour does not exist
yet, and at a stub only the not-implemented exception counts as the failure.
"""

import pytest
from hypothesis import given

from ledger.importer import parse_rows

from .generators import statements


@given(statements())
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 02-upload-and-parse-report")
def test_every_accepted_row_carries_a_date_a_payee_and_an_amount(statement: str) -> None:
    for row in parse_rows(statement, DEFAULT_COLUMNS):
        assert row.date and row.payee and isinstance(row.cents, int)


@given(statements())
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 02-upload-and-parse-report")
def test_a_row_is_either_accepted_or_reported_never_both(statement: str) -> None:
    report = parse_report(statement, DEFAULT_COLUMNS)
    assert len(report.rows) + len(report.rejected) == report.line_count


@given(statements())
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 04-commit-the-import")
def test_importing_the_same_statement_twice_adds_no_entry_the_second_time(statement: str) -> None:
    once = commit_import(statement)
    assert commit_import(statement) == once
''',
}

C3 = {
    "ledger/importer.py": '''\
"""Turn an uploaded statement into rows the account can accept."""

import csv
from dataclasses import dataclass
from io import StringIO


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

    @property
    def line_count(self) -> int:
        return len(self.rows) + len(self.rejected)


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
                    date=record[columns["date"]].strip(),
                    payee=record[columns["payee"]].strip(),
                    cents=to_cents(record[columns["amount"]]),
                )
            )
        except (KeyError, ValueError) as exc:
            rejected.append((number, str(exc)))
    return ParseReport(rows=rows, rejected=rejected)


def to_cents(amount: str) -> int:
    """Whole cents from a decimal amount, so no entry ever carries a rounded float."""
    whole, _, fraction = amount.strip().replace(",", "").partition(".")
    return int(whole) * 100 + int(fraction.ljust(2, "0")[:2]) * (-1 if whole.startswith("-") else 1)
''',
    "tests/test_importer.py": '''\
from ledger.importer import Row, parse_report, to_cents

STATEMENT = """date,description,amount
2026-02-01,Coffee Roasters,-4.80
2026-02-02,Salary,2400.00
2026-02-03,,-12.00
"""
COLUMNS = {"date": "date", "payee": "description", "amount": "amount"}


def test_the_report_keeps_every_line_it_could_not_read() -> None:
    report = parse_report(STATEMENT, COLUMNS)
    assert report.rows == [
        Row(date="2026-02-01", payee="Coffee Roasters", cents=-480),
        Row(date="2026-02-02", payee="Salary", cents=240000),
    ]
    assert [number for number, _ in report.rejected] == [4]


def test_an_amount_becomes_whole_cents() -> None:
    assert to_cents("-4.80") == -480
    assert to_cents("2,400") == 240000
''',
}

NOTES = {
    "notes": [
        {
            "id": 1,
            "path": "ledger/importer.py",
            "line": 38,
            "end": 44,
            "side": "new",
            "text": "The spec says a rejected line is shown, not dropped, so the report carries both "
                    "lists and the ticket's second property can count them. Rejecting per line rather "
                    "than per file is what lets the mapping screen stay useful on a statement with one "
                    "bad row.",
        },
        {
            "id": 2,
            "path": "ledger/importer.py",
            "line": 58,
            "end": 61,
            "side": "new",
            "text": "Cents, not a float: the glossary's Entry is an integer amount. Assumption I could "
                    "not settle from the spec: a statement that writes amounts in a currency with three "
                    "decimal places would truncate here. Flagged for the debrief rather than guessed at.",
        },
        {
            "id": 3,
            "path": "tests/properties/test_import.py",
            "text": "Read and deliberately left alone. Two of the three expected failures name this "
                    "ticket and are lifted by it; the third names 04-commit-the-import and stays.",
        },
    ]
}
