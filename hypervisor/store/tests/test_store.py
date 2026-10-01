"""The store's command line, past what lifelong-hypervisor#P2 and #P3 pin: the raw sidecar, import,
the view's header, and the compressions the forks write."""

import contextlib
import datetime
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import hv_store  # noqa: E402


def run(store: Path, *args: object, stdin: str = "") -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    given = io.TextIOWrapper(io.BytesIO(stdin.encode()), encoding="utf-8", newline="\n")
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch("sys.stdin", given):
        code = hv_store.main(["--dir", str(store), *map(str, args)])
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def store(tmp_path: Path) -> Path:
    assert run(tmp_path / "store", "init")[0] == 0
    return tmp_path / "store"


def answer_due(store: Path) -> None:
    while blocks := run(store, "due")[1].split():
        for block in blocks:
            assert run(store, "compress", block, stdin=f"summary of {block}")[0] == 0


def test_optmems_own_checks_pass_on_the_vendored_copy() -> None:
    done = subprocess.run([sys.executable, HERE.parent / "optmem" / "test.py"], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]


# ---------------------------------------------------------------- the raw sidecar

# Over 512 bytes, multi-byte, several lines, with whitespace a record would drop at both ends.
long_texts = st.builds(lambda head, tail: f"  {head}\n{'é' * 300}\r\n{tail}\t", st.text(max_size=200), st.text(max_size=200))


@settings(max_examples=25, deadline=None)
@given(long_texts)
def test_a_text_over_512_bytes_is_stored_whole_in_the_sidecar_and_read_back_whole(text: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "store"
        run(store, "init")
        run(store, "append", stdin="before")
        assert run(store, "append", stdin=text + "\n") == (0, "#1\n", "")
        run(store, "append", stdin="after")
        assert (store / "RAW" / "1").read_bytes() == text.encode()
        assert run(store, "raw", 1)[1] == text + "\n"
        _, view, _ = run(store, "view")
        entry = view.split("\n")[2]
        assert entry.startswith(f"{entry.split()[0]} #1 ") and entry.endswith(f"[raw: {len(text.encode())} bytes]")
        assert len(entry.split(" ", 2)[2].encode()) <= 512
        assert view.split("\n")[3].endswith(" #2 after")


def test_a_line_an_entry_holds_as_it_is_has_no_sidecar(store: Path) -> None:
    text = "ü" * 256  # 512 bytes exactly
    run(store, "append", stdin=text)
    assert run(store, "raw", 0)[1] == text + "\n"
    assert run(store, "view")[1].split("\n")[1].endswith(f" #0 {text}")
    assert not any((store / "RAW").iterdir())


def test_recall_searches_the_whole_text_of_a_sidecar_entry(store: Path) -> None:
    run(store, "append", stdin="x" * 600 + " needle")
    run(store, "append", stdin="hay")
    code, out, _ = run(store, "recall", "NEEDLE")
    assert code == 0 and out.count("\n") == 1 and " #0 " in out


# ---------------------------------------------------------------- import


def test_import_keeps_the_given_stamps_and_stamps_a_bare_date_at_midnight(store: Path) -> None:
    code, out, _ = run(store, "import", stdin="2026-01-11 first\n\n2026-01-11T09:30 second\n2026-02-01 third\n")
    assert code == 0, out
    lines = run(store, "view")[1].split("\n")[1:-1]
    assert lines == ["2026-01-11T00:00 #0 first", "2026-01-11T09:30 #1 second", "2026-02-01T00:00 #2 third"]


@pytest.mark.parametrize(
    "lines",
    [
        "2026-01-12 ok\n2026-01-11 earlier than the line before",
        "2026-01-12 ok\n2026-13-01 not a date",
        "2026-01-12 ok\n12:00 no date",
        "2026-01-12 ok\n2026-01-12   ",
    ],
)
def test_import_refuses_the_whole_input_over_one_bad_line(store: Path, lines: str) -> None:
    assert run(store, "import", stdin=lines)[0] == 1
    assert run(store, "view")[1].count("\n") == 1, "a refused import logged something"


def test_import_refuses_a_stamp_before_the_last_entry(store: Path) -> None:
    run(store, "import", stdin="2026-03-01 later")
    assert run(store, "import", stdin="2026-02-01 earlier")[0] == 1


# ---------------------------------------------------------------- the header


@pytest.mark.parametrize(
    ("at", "said"),
    [
        (datetime.datetime(2026, 10, 3, 9, 30, 59), "now 2026-10-03T09:30 (Sat), 3 weeks 2 days since the last entry, #0"),
        (datetime.datetime(2026, 9, 10, 13, 5), "now 2026-09-10T13:05 (Thu), 5 hours 5 minutes since the last entry, #0"),
        (datetime.datetime(2026, 9, 10, 8, 0, 40), "now 2026-09-10T08:00 (Thu), 0 minutes since the last entry, #0"),
        (datetime.datetime(2026, 9, 17, 8, 0), "now 2026-09-17T08:00 (Thu), 1 week since the last entry, #0"),
        (datetime.datetime(2026, 9, 10, 7, 0), "now 2026-09-10T07:00 (Thu), the last entry, #0, is stamped 1 hour later"),
    ],
)
def test_the_header_says_the_time_and_how_long_since_the_last_entry(store: Path, at: datetime.datetime, said: str) -> None:
    run(store, "import", stdin="2026-09-10T08:00 the entry")
    with mock.patch.object(hv_store, "now", return_value=at):
        assert run(store, "view")[1].split("\n")[0] == said


def test_the_header_of_an_empty_log_says_so(store: Path) -> None:
    with mock.patch.object(hv_store, "now", return_value=datetime.datetime(2026, 10, 1, 14, 7)):
        assert run(store, "view")[1] == "now 2026-10-01T14:07 (Thu), the log is empty\n"


def test_append_stamps_the_current_minute(store: Path) -> None:
    with mock.patch.object(hv_store, "now", return_value=datetime.datetime(2026, 10, 1, 14, 7, 59)):
        run(store, "append", stdin="stamped")
    assert run(store, "raw", 0)[1] == "stamped\n"
    assert run(store, "zoom", "0-1")[1] == "2026-10-01T14:07 #0 stamped\n"


# ---------------------------------------------------------------- compressions


@settings(max_examples=25, deadline=None)
@given(st.integers(2, 80), st.randoms(use_true_random=False))
def test_what_due_lists_lands_in_any_order(n: int, rnd) -> None:
    """The forks write in whatever order they finish."""
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "store"
        run(store, "init")
        for i in range(n):
            run(store, "append", stdin=f"entry {i}")
        written: list[str] = []
        while blocks := run(store, "due")[1].split():
            rnd.shuffle(blocks)
            for block in blocks:
                code, _, err = run(store, "compress", block, stdin=f"summary of {block}")
                assert code == 0, err
                written.append(block)
        # Every complete aligned block, from the definition, is written once.
        assert sorted(written) == sorted(f"{k * s}-{(k + 1) * s - 1}" for s in (2**e for e in range(1, 8)) for k in range(n // s))


def test_the_view_is_refused_while_a_compression_it_needs_is_outstanding(store: Path) -> None:
    for i in range(10):
        run(store, "append", stdin=f"entry {i}")
    code, out, err = run(store, "view", "--budget", 4)
    assert (code, out) == (1, "") and "0-3 4-7" in err
    answer_due(store)
    code, out, _ = run(store, "view", "--budget", 4)
    assert code == 0 and [line.split()[1] for line in out.split("\n")[1:-1]] == ["#0-3", "#4-7", "#8", "#9"]


@pytest.mark.parametrize(
    ("block", "summary", "why"),
    [
        ("0-3", "fine", "already written"),
        ("4-7", "fine", "not all logged"),
        ("2-5", "fine", "not a block"),
        ("4-5", "two\nlines", "one line"),
        ("4-5", "   ", "one line"),
        ("4-5", "x" * 513, "Too long"),
    ],
)
def test_compress_refuses_what_due_would_not_list_and_text_a_line_cannot_hold(store: Path, block: str, summary: str, why: str) -> None:
    for i in range(6):
        run(store, "append", stdin=f"entry {i}")
    for done in ("0-1", "0-3", "2-3"):
        assert run(store, "compress", done, stdin="written")[0] == 0
    code, _, err = run(store, "compress", block, stdin=summary)
    assert code == 1 and why in err


def test_a_command_other_than_init_refuses_a_missing_store(tmp_path: Path) -> None:
    code, _, err = run(tmp_path / "typo", "view")
    assert code == 1 and "init" in err and not (tmp_path / "typo").exists()


def test_init_leaves_a_store_as_it_is(store: Path) -> None:
    run(store, "append", stdin="x" * 600)
    before = {p: p.read_bytes() for p in store.rglob("*") if p.is_file() and not p.name.endswith(".lock")}
    assert run(store, "init")[0] == 0
    assert {p: p.read_bytes() for p in store.rglob("*") if p.is_file() and not p.name.endswith(".lock")} == before


def test_the_script_runs_as_a_process(store: Path) -> None:
    """The extension runs it through uv, outside this process."""
    done = subprocess.run(
        [sys.executable, HERE.parent / "hv_store.py", "--dir", store, "append"],
        input=b"from a process\r\nwith a CR\n",
        capture_output=True,
        env=dict(os.environ, PYTHONIOENCODING="latin-1"),
    )
    assert done.returncode == 0, done.stderr
    raw = subprocess.run([sys.executable, HERE.parent / "hv_store.py", "--dir", store, "raw", "0"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="latin-1"))
    assert raw.stdout == "from a process\r\nwith a CR\n".encode()
