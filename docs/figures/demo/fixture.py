"""The demo project the board and review-page screenshots are taken of.

One dict per commit, so `build.py` can lay the repo down from scratch and the
history a review page needs is real. The project is invented: a small expenses
app whose first feature imports bank CSVs and whose second saves filtered views.
`build.py` runs the suite at HEAD, so this code stays a worked example rather
than something that only looks like one.
"""

CONTEXT = """\
# ledger

**Row**: one line of an imported statement, before it becomes an entry.
_Avoid_: record, item

**Entry**: a row the import accepted, stored against an account.
_Avoid_: transaction, txn
"""

MAKEFILE = "test:\n\tuv run --with pytest --with hypothesis pytest -q\n\nharden:\n\tharden $(ARGS)\n"

# --- 01 the skeleton -------------------------------------------------------

C1 = {
    "pytest.ini": "[pytest]\npythonpath = .\n",
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
    """The rows of `text` that parsed, under a mapping of column name to field."""
    raise NotImplementedError
''',
    "tests/test_importer.py": '''\
import pytest

from ledger.importer import parse_rows


def test_the_importer_is_not_built_yet() -> None:
    with pytest.raises(NotImplementedError):
        parse_rows("", {})
''',
}

# --- 02 the properties, and the seams they need ----------------------------

C2 = {
    "ledger/importer.py": '''\
"""Turn an uploaded statement into rows the account can accept."""

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
    "ledger/commit.py": '''\
"""Turn accepted rows into entries against an account."""

from dataclasses import dataclass, field

from ledger.importer import Row


@dataclass
class Account:
    """The entries an account holds."""

    entries: list[Row] = field(default_factory=list)


def commit_import(account: Account, text: str, columns: dict[str, str]) -> list[Row]:
    """Add the statement's accepted rows to the account, skipping duplicates; the entries added."""
    raise NotImplementedError
''',
    "tests/properties/__init__.py": "",
    "tests/properties/generators.py": '''\
"""Whole statements, so the properties explore the space the importer actually meets."""

from hypothesis import strategies as st

DATES = st.sampled_from(["2026-02-01", "2026-02-02", "2026-02-03", "2026-03-11"])
PAYEES = st.text(alphabet=st.characters(categories=("L", "N", "Zs"), blacklist_characters=',"'), min_size=1, max_size=12)
AMOUNTS = st.integers(min_value=-500_000, max_value=500_000).map(lambda c: f"{c / 100:.2f}")


@st.composite
def statements(draw: st.DrawFn) -> str:
    """A CSV statement: the header the default mapping expects, then rows, some unreadable."""
    lines = ["date,description,amount"]
    for _ in range(draw(st.integers(min_value=0, max_value=6))):
        date, payee, amount = draw(DATES), draw(PAYEES), draw(AMOUNTS)
        if draw(st.booleans()):
            payee = ""  # a line the mapping cannot read: the report must keep it
        lines.append(f"{date},{payee},{amount}")
    return "\\n".join(lines) + "\\n"
''',
    "tests/properties/test_import.py": '''\
"""The properties the import spec states, as checks over generated statements.

Each is an expected failure while the behaviour it tests does not exist, naming the
ticket that lifts it; at a stub only the not-implemented exception counts.
"""

import pytest
from hypothesis import given

from ledger.commit import Account, commit_import
from ledger.importer import DEFAULT_COLUMNS, parse_report, parse_rows

from .generators import statements


@given(statements())
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 02-upload-and-parse-report")
def test_every_accepted_row_carries_a_date_a_payee_and_an_amount(statement: str) -> None:
    for row in parse_rows(statement, DEFAULT_COLUMNS):
        assert row.date and row.payee and isinstance(row.cents, int)


@given(statements())
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 02-upload-and-parse-report")
def test_a_line_is_either_accepted_or_reported_never_both(statement: str) -> None:
    report = parse_report(statement, DEFAULT_COLUMNS)
    body = [line for line in statement.split("\\n")[1:] if line.strip()]  # not splitlines: CSV breaks on \\n alone
    assert len(report.rows) + len(report.rejected) == len(body)


@given(statements())
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 04-commit-the-import")
def test_importing_the_same_statement_twice_adds_no_entry_the_second_time(statement: str) -> None:
    account = Account()
    commit_import(account, statement, DEFAULT_COLUMNS)
    settled = len(account.entries)
    commit_import(account, statement, DEFAULT_COLUMNS)
    assert len(account.entries) == settled
''',
}

# --- 03 the parse report ---------------------------------------------------

C3 = {
    "ledger/importer.py": '''\
"""Turn an uploaded statement into rows the account can accept."""

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


def test_an_amount_becomes_whole_cents() -> None:
    assert to_cents("-4.80") == -480
    assert to_cents("2,400") == 240000
''',
    "tests/properties/test_import.py": '''\
"""The properties the import spec states, as checks over generated statements.

Each is an expected failure while the behaviour it tests does not exist, naming the
ticket that lifts it; at a stub only the not-implemented exception counts.
"""

import pytest
from hypothesis import given

from ledger.commit import Account, commit_import
from ledger.importer import DEFAULT_COLUMNS, parse_report, parse_rows

from .generators import statements


@given(statements())
def test_every_accepted_row_carries_a_date_a_payee_and_an_amount(statement: str) -> None:
    for row in parse_rows(statement, DEFAULT_COLUMNS):
        assert row.date and row.payee and isinstance(row.cents, int)


@given(statements())
def test_a_line_is_either_accepted_or_reported_never_both(statement: str) -> None:
    report = parse_report(statement, DEFAULT_COLUMNS)
    body = [line for line in statement.split("\\n")[1:] if line.strip()]  # not splitlines: CSV breaks on \\n alone
    assert len(report.rows) + len(report.rejected) == len(body)


@given(statements())
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 04-commit-the-import")
def test_importing_the_same_statement_twice_adds_no_entry_the_second_time(statement: str) -> None:
    account = Account()
    commit_import(account, statement, DEFAULT_COLUMNS)
    settled = len(account.entries)
    commit_import(account, statement, DEFAULT_COLUMNS)
    assert len(account.entries) == settled
''',
}

# --- 04 the mapping ---------------------------------------------------------

C4 = {
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

# --- 05 the commit ----------------------------------------------------------

C5 = {
    "ledger/commit.py": '''\
"""Turn accepted rows into entries against an account."""

from dataclasses import dataclass, field

from ledger.importer import Row, parse_report


@dataclass
class Account:
    """The entries an account holds."""

    entries: list[Row] = field(default_factory=list)


def commit_import(account: Account, text: str, columns: dict[str, str]) -> list[Row]:
    """Add the statement's accepted rows to the account, skipping duplicates; the entries added."""
    added = dry_run(account, text, columns)
    account.entries.extend(added)
    return added


def dry_run(account: Account, text: str, columns: dict[str, str]) -> list[Row]:
    """What committing this statement would add, so the human sees it before it lands."""
    settled = set(account.entries)
    return [row for row in parse_report(text, columns).rows if row not in settled]
''',
    "tests/test_commit.py": '''\
from ledger.commit import Account, commit_import, dry_run
from ledger.importer import DEFAULT_COLUMNS

STATEMENT = """date,description,amount
2026-02-01,Coffee Roasters,-4.80
2026-02-02,Salary,2400.00
"""


def test_the_dry_run_and_the_commit_agree() -> None:
    account = Account()
    assert dry_run(account, STATEMENT, DEFAULT_COLUMNS) == commit_import(account, STATEMENT, DEFAULT_COLUMNS)


''',
    "tests/properties/test_import.py": C3["tests/properties/test_import.py"]
        .replace(
            '@given(statements())\n@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by 04-commit-the-import")\n',
            "@given(statements())\n",
        )
        .replace("import pytest\nfrom hypothesis", "from hypothesis")
        .replace(
            "Each is an expected failure while the behaviour it tests does not exist, naming the\nticket that lifts it; at a stub only the not-implemented exception counts.",
            "All three hold now. One written ahead of its behaviour would carry a strict expected\nfailure naming the ticket that lifts it.",
        ),
}


# --- the orchestrator's notes on 02's review page ---------------------------

NOTES = {
    "notes": [
        {
            "id": 1,
            "path": "ledger/importer.py",
            "line": 34,
            "end": 37,
            "side": "new",
            "text": "The spec says a line the mapping cannot read is shown, not dropped, so the report "
                    "carries both lists and the second property can count them against the upload. "
                    "Rejecting per line rather than per file is what keeps the mapping screen useful "
                    "on a statement with one bad row.",
        },
        {
            "id": 2,
            "path": "ledger/importer.py",
            "line": 62,
            "end": 66,
            "side": "new",
            "text": "Cents, not a float: the glossary's Entry carries an integer amount. One assumption "
                    "I could not settle from the spec, flagged rather than guessed at: a statement in "
                    "a currency with three decimal places truncates here.",
        },
        {
            "id": 3,
            "path": "ledger/commit.py",
            "text": "Read and deliberately left alone. The third property still names "
                    "04-commit-the-import, and this ticket does not touch the commit seam; its stub "
                    "is what keeps the property collecting until then.",
        },
    ]
}

# --- the orchestrator's own fix, from the harden report ---------------------

C6 = {"tests/test_commit.py": C5["tests/test_commit.py"].rstrip("\n") + '\n\n\ndef test_a_re_issued_statement_adds_nothing() -> None:\n    account = Account()\n    commit_import(account, STATEMENT, DEFAULT_COLUMNS)\n    assert commit_import(account, STATEMENT, DEFAULT_COLUMNS) == []\n'}
