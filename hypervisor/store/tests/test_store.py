"""The store's command line, past what lifelong-hypervisor#P2 and #P3 pin: the raw sidecar, import,
the view's header, and the compressions the forks write."""

import contextlib
import datetime
import io
import os
import random
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
    piped = io.TextIOWrapper(io.BytesIO(stdin.encode()), encoding="utf-8", newline="\n")
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch("sys.stdin", piped):
        code = hv_store.main(["--dir", str(store), *map(str, args)])
    return code, out.getvalue(), err.getvalue()


AT = datetime.datetime(2026, 10, 1, 14, 7)


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
        assert run(store, "init")[0] == 0
        with mock.patch.object(hv_store, "now", return_value=AT):
            assert run(store, "append", stdin="before")[0] == 0
            assert run(store, "append", stdin=text + "\n") == (0, "#1\n", "")
            assert run(store, "append", stdin="after")[0] == 0
        assert (store / "RAW" / "1").read_bytes() == text.encode()
        assert run(store, "raw", 1)[1] == text + "\n"
        _, view, _ = run(store, "view")
        entry = view.split("\n")[2]
        assert entry.startswith("2026-10-01T14:07 #1 ") and entry.endswith(f"[raw: {len(text.encode())} bytes]")
        # The gist holds 512 bytes; its marker sits outside them, as the stamp does.
        assert len(entry.split(" ", 2)[2].removesuffix(f" [raw: {len(text.encode())} bytes]").encode()) <= 512
        assert view.split("\n")[3] == "2026-10-01T14:07 #2 after"


def test_a_line_an_entry_holds_as_it_is_has_no_sidecar(store: Path) -> None:
    text = "ü" * 256  # 512 bytes exactly
    run(store, "append", stdin=text)
    assert run(store, "raw", 0)[1] == text + "\n"
    assert run(store, "view")[1].split("\n")[1].endswith(f" #0 {text}")
    assert not any((store / "RAW").iterdir())


@pytest.mark.parametrize("text", ["  indented", "trailing tab\t", "\u2028"])
def test_a_short_line_with_whitespace_at_its_ends_reads_back_whole(store: Path, text: str) -> None:
    assert run(store, "append", stdin=text)[0] == 0
    assert run(store, "raw", 0)[1] == text + "\n"


def test_a_sidecar_left_by_a_run_that_died_does_not_shadow_the_next_entry(store: Path) -> None:
    # A sidecar written before its entry was logged, by a run killed in between.
    (store / "RAW" / "1").write_text("the dead run's text")
    run(store, "append", stdin="first")
    run(store, "append", stdin="second")
    assert run(store, "raw", 1)[1] == "second\n"
    assert run(store, "recall", "dead run")[1] == ""


def test_stdin_that_is_not_utf8_is_refused(store: Path) -> None:
    piped = io.TextIOWrapper(io.BytesIO(b"caf\xe9"), encoding="latin-1")
    with contextlib.redirect_stderr(io.StringIO()) as err, mock.patch("sys.stdin", piped):
        assert hv_store.main(["--dir", str(store), "append"]) == 1
    assert "UTF-8" in err.getvalue() and run(store, "view")[1].count("\n") == 1


def test_recall_searches_the_whole_text_of_a_sidecar_entry(store: Path) -> None:
    run(store, "append", stdin="x" * 600 + " needle")
    run(store, "append", stdin="hay")
    code, out, _ = run(store, "recall", "NEEDLE")
    assert code == 0 and out.count("\n") == 1 and " #0 " in out


def test_recall_past_its_cap_keeps_the_newest_matches_and_says_how_many_matched(store: Path) -> None:
    run(store, "import", stdin="".join(f"2026-01-01 match {i} {'x' * 480}\n" for i in range(60)))
    code, out, _ = run(store, "recall", "match")
    printed = out.removesuffix("\n").split("\n")
    assert code == 0 and printed[-1].startswith("(the newest ") and " of 60 matches" in printed[-1]
    kept = int(printed[-1].split()[2])
    assert 0 < kept < 60 and len(printed) == kept + 1
    assert [line.split()[1] for line in printed[:-1]] == [f"#{i}" for i in range(60 - kept, 60)]
    assert len(out.encode()) < 20_000 + 600


# ---------------------------------------------------------------- the gist


@pytest.mark.parametrize("gist", ["the fork's gist", "g" * 512])
def test_a_given_gist_is_logged_in_place_of_a_text_the_entry_cannot_hold(store: Path, gist: str) -> None:
    text = "a final answer\n" + "x" * 600
    with mock.patch.object(hv_store, "now", return_value=AT):
        assert run(store, "append", "--gist", gist, stdin=text)[:2] == (0, "#0\n")
    assert run(store, "view")[1].split("\n")[1] == f"2026-10-01T14:07 #0 {gist} [raw: {len(text.encode())} bytes]"
    assert run(store, "raw", 0)[1] == text + "\n"


def test_a_gist_is_unused_when_the_entry_holds_the_text_itself(store: Path) -> None:
    assert run(store, "append", "--gist", "a gist", stdin="short enough")[0] == 0
    assert run(store, "zoom", "0-1")[1].endswith(" #0 short enough\n")


def test_a_gist_is_stripped_as_a_compression_is(store: Path) -> None:
    assert run(store, "append", "--gist", "  padded\t", stdin="x" * 600)[0] == 0
    assert run(store, "zoom", "0-1")[1].endswith(" #0 padded [raw: 600 bytes]\n")


@pytest.mark.parametrize("text", ["x" * 600, "short enough"])
@pytest.mark.parametrize(("gist", "why"), [("two\nlines", "one line"), ("   ", "one line"), ("g" * 513, "too long"), ("ü" * 257, "too long")])
def test_a_gist_a_line_cannot_hold_is_refused_and_nothing_is_logged(store: Path, text: str, gist: str, why: str) -> None:
    code, _, err = run(store, "append", "--gist", gist, stdin=text)
    assert code == 1 and f"A gist is {why}" in err
    assert run(store, "view")[1].count("\n") == 1


# ---------------------------------------------------------------- import


def test_import_keeps_the_given_stamps_and_stamps_a_bare_date_at_midnight(store: Path) -> None:
    code, out, _ = run(store, "import", stdin="2026-01-11 first\n\n2026-01-11T09:30 second\n2026-02-01 third\n")
    assert code == 0, out
    lines = run(store, "view")[1].split("\n")[1:-1]
    assert lines == ["2026-01-11T00:00 #0 first", "2026-01-11T09:30 #1 second", "2026-02-01T00:00 #2 third"]


def test_import_puts_a_line_over_512_bytes_in_the_sidecar(store: Path) -> None:
    text = "ä" * 300
    assert run(store, "import", stdin=f"2026-01-01 {text}\n")[0] == 0
    assert run(store, "raw", 0)[1] == text + "\n"
    assert run(store, "view")[1].split("\n")[1].endswith("[raw: 600 bytes]")


@pytest.mark.parametrize(
    "lines",
    [
        "2026-01-12 ok\n2026-01-11 earlier than the line before",
        "2026-01-12 ok\n2026-13-01 not a date",
        "2026-01-12 ok\n12:00 no date",
        "2026-01-12 ok\n2026-1-13T0:0 not zero-padded",
        "2026-01-12 ok\n2026-01-12   ",
    ],
)
def test_import_refuses_the_whole_input_over_one_bad_line(store: Path, lines: str) -> None:
    assert run(store, "import", stdin=lines)[0] == 1
    assert run(store, "view")[1].count("\n") == 1, "a refused import logged something"


def test_import_refuses_a_stamp_before_the_last_entry(store: Path) -> None:
    assert run(store, "import", stdin="2026-03-01 later")[0] == 0
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
    assert run(store, "import", stdin="2026-09-10T08:00 the entry")[0] == 0
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
            for block in blocks:
                lo, hi = map(int, block.split("-"))
                if hi - lo + 1 > 16:  # compressed from its two halves, which have to be written
                    mid = (lo + hi + 1) // 2
                    assert {f"{lo}-{mid - 1}", f"{mid}-{hi}"} <= set(written), f"{block} listed before its halves"
            rnd.shuffle(blocks)
            for block in blocks:
                code, _, err = run(store, "compress", block, stdin=f"summary of {block}")
                assert code == 0, err
                written.append(block)
        # Every complete aligned block, from the definition, is written once.
        assert sorted(written) == sorted(f"{k * s}-{(k + 1) * s - 1}" for s in (2**e for e in range(1, 8)) for k in range(n // s))


def test_a_burst_leaves_its_whole_backlog_due_in_one_round_and_written_in_parallel(store: Path, tmp_path: Path) -> None:
    """A turn that logs a burst of tool calls: every block its entries complete, up to RAW_MAX, is
    due at once, and the forks write all of it concurrently, each its own process, in no set order."""
    rnd = random.Random(16)
    for burst in range(4):
        for i in range(16 * burst, 16 * burst + 16):
            run(store, "append", stdin=f"tool call {i}")
        blocks = run(store, "due")[1].split()
        assert set(blocks) >= {f"{16 * burst + k * s}-{16 * burst + (k + 1) * s - 1}" for s in (2, 4, 8, 16) for k in range(16 // s)}
        while blocks:
            write_in_parallel(store, tmp_path, rnd.sample(blocks, len(blocks)))
            blocks = run(store, "due")[1].split()
    # memo's own tree, the ticket's oracle, holds every block of the 64 entries: none is left held.
    for s in (2, 4, 8, 16, 32, 64):
        for lo in range(0, 64, s):
            assert hv_store.memo.tree_get(store, lo, lo + s) == f"summary of {lo}-{lo + s - 1}"
    assert run(store, "view", "--budget", 1)[1].split("\n")[1].endswith(" #0-63 summary of 0-63")


def write_in_parallel(store: Path, tmp_path: Path, blocks: list[str]) -> None:
    """One process per block, all started before any is waited on, each reading its compression
    from a file so none waits on another's stdin."""
    forks = []
    for block in blocks:
        (given := tmp_path / f"{block}.txt").write_text(f"summary of {block}")
        with open(given, "rb") as stdin:
            forks.append(subprocess.Popen([sys.executable, HERE.parent / "hv_store.py", "--dir", store, "compress", block], stdin=stdin, stderr=subprocess.PIPE))
    for fork in forks:
        _, err = fork.communicate(timeout=120)
        assert fork.returncode == 0, err


def test_a_block_written_early_is_read_before_the_blocks_before_it_land(store: Path) -> None:
    for i in range(8):
        run(store, "append", stdin=f"entry {i}")
    assert run(store, "compress", "4-5", stdin="early")[0] == 0
    assert "4-5" not in run(store, "due")[1].split()
    assert run(store, "zoom", "4-7")[1].split("\n")[0].endswith(" #4-5 early")
    assert run(store, "compress", "4-5", stdin="again")[2].endswith("already written.\n")
    for block in ("0-3", "6-7"):
        assert run(store, "compress", block, stdin=f"{block} text")[0] == 0
    # The view of 8 entries in 3 lines is 0-3, 4-5, 6-7: two of them held, 0-1 and 2-3 not written.
    assert [line.split(" ", 2)[2] for line in run(store, "view", "--budget", 3)[1].splitlines()[1:]] == ["0-3 text", "early", "6-7 text"]
    for block in ("2-3", "0-1"):  # 0-1 lands last, and moves the blocks held behind it into the tree
        assert run(store, "compress", block, stdin=f"{block} text")[0] == 0
    assert [line.split(" ", 2)[2] for line in run(store, "zoom", "0-7")[1].splitlines()] == ["0-3 text", "(not compressed yet)"]
    assert [line.split(" ", 2)[2] for line in run(store, "zoom", "4-7")[1].splitlines()] == ["early", "6-7 text"]
    tree = [hv_store.memo.tree_get(store, lo, lo + 2) for lo in range(0, 8, 2)]
    assert tree == ["0-1 text", "2-3 text", "early", "6-7 text"], "a block left held once the blocks before it landed"


def test_a_move_into_the_tree_cut_short_resumes_at_the_next_write_to_its_level(store: Path) -> None:
    for i in range(8):
        run(store, "append", stdin=f"entry {i}")
    assert run(store, "compress", "2-3", stdin="2-3 text")[0] == 0
    # A run killed after holding 0-1 and before moving it: the level's front stays held.
    hv_store.held_path(store, 0, 2).write_text("0-1 text")
    assert run(store, "compress", "4-5", stdin="4-5 text")[0] == 0
    assert [hv_store.memo.tree_get(store, lo, lo + 2) for lo in range(0, 6, 2)] == ["0-1 text", "2-3 text", "4-5 text"]
    assert run(store, "due")[1].split() == ["6-7", "0-3", "4-7", "0-7"]


def test_a_block_whose_halves_are_not_written_is_not_due(store: Path) -> None:
    for i in range(32):
        run(store, "append", stdin=f"entry {i}")
    code, _, err = run(store, "compress", "0-31", stdin="too soon")
    assert code == 1 and "not due yet" in err


def test_the_view_is_refused_while_a_compression_it_needs_is_outstanding(store: Path) -> None:
    for i in range(10):
        run(store, "append", stdin=f"entry {i}")
    code, out, err = run(store, "view", "--budget", 4)
    assert (code, out) == (1, "") and "0-3 4-7" in err
    answer_due(store)
    code, out, _ = run(store, "view", "--budget", 4)
    assert code == 0 and [line.split()[1] for line in out.split("\n")[1:-1]] == ["#0-3", "#4-7", "#8", "#9"]


def test_a_view_line_carries_its_first_entrys_minute(store: Path) -> None:
    assert run(store, "import", stdin="".join(f"2026-01-01T00:0{i} entry {i}\n" for i in range(6)))[0] == 0
    answer_due(store)
    lines = run(store, "view", "--budget", 3)[1].split("\n")[1:-1]
    assert lines == ["2026-01-01T00:00 #0-3 summary of 0-3", "2026-01-01T00:04 #4 entry 4", "2026-01-01T00:05 #5 entry 5"]
    assert run(store, "zoom", "0-3")[1] == "2026-01-01T00:00 #0-1 summary of 0-1\n2026-01-01T00:02 #2-3 summary of 2-3\n"


def test_zoom_names_a_half_not_compressed_and_leaves_out_one_not_logged(store: Path) -> None:
    assert run(store, "import", stdin="2026-01-01T00:00 a\n2026-01-01T00:01 b\n2026-01-01T00:02 c\n")[0] == 0
    assert run(store, "zoom", "0-3")[1] == "2026-01-01T00:00 #0-1 (not compressed yet)\n2026-01-01T00:02 #2-3 (not compressed yet)\n"
    assert run(store, "compress", "0-1", stdin="a and b")[0] == 0
    assert run(store, "zoom", "0-3")[1].split("\n")[0] == "2026-01-01T00:00 #0-1 a and b"
    assert run(store, "zoom", "0-7")[1] == "2026-01-01T00:00 #0-3 (not compressed yet)\n"
    code, out, err = run(store, "zoom", "8-15")
    assert (code, out) == (1, "") and "holds 3 entries" in err


def test_body_of_a_small_block_is_its_entries_and_of_a_big_one_its_halves(store: Path) -> None:
    assert run(store, "import", stdin="".join(f"2026-01-01T00:{i:02} entry {i}\n" for i in range(32)))[0] == 0
    assert run(store, "body", "2-3")[1] == "2026-01-01T00:02 #2 entry 2\n2026-01-01T00:03 #3 entry 3\n"
    assert run(store, "body", "16-31")[1].split("\n")[:-1] == [f"2026-01-01T00:{i:02} #{i} entry {i}" for i in range(16, 32)]
    code, out, err = run(store, "body", "0-31")
    assert (code, out) == (1, "") and "0-15 and 16-31" in err
    answer_due(store)
    assert run(store, "body", "0-31")[1] == "2026-01-01T00:00 #0-15 summary of 0-15\n2026-01-01T00:16 #16-31 summary of 16-31\n"
    code, out, err = run(store, "body", "32-33")
    assert (code, out) == (1, "") and "not all logged" in err


@pytest.mark.parametrize("budget", [0, 1, 2])
def test_a_budget_the_log_cannot_be_tiled_in_is_refused(store: Path, budget: int) -> None:
    for i in range(7):  # 4 + 2 + 1: no fewer than three lines
        run(store, "append", stdin=f"entry {i}")
    answer_due(store)
    assert run(store, "view", "--budget", budget)[:2] == (1, "")
    assert len(run(store, "view", "--budget", 3)[1].split("\n")) == 1 + 3 + 1


@pytest.mark.parametrize("summary", ["y" * 512, "ü" * 256])
def test_a_compression_of_512_bytes_is_written_whole(store: Path, summary: str) -> None:
    run(store, "append", stdin="a")
    run(store, "append", stdin="b")
    assert run(store, "compress", "0-1", stdin=summary)[0] == 0
    assert run(store, "view", "--budget", 1)[1].split("\n")[1].endswith(f" #0-1 {summary}")


@pytest.mark.parametrize(
    ("block", "summary", "why"),
    [
        ("0-3", "fine", "already written"),
        ("4-7", "fine", "not all logged"),
        ("2-5", "fine", "not a block"),
        ("4-5", "two\nlines", "one line"),
        ("4-5", "   ", "one line"),
        ("4-5", "x" * 513, "too long"),
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
    """The pi extension (hypervisor/extension) runs it as a process of its own."""
    done = subprocess.run(
        [sys.executable, HERE.parent / "hv_store.py", "--dir", store, "append"],
        input=b"from a process\r\nwith a CR\n",
        capture_output=True,
        env=dict(os.environ, PYTHONIOENCODING="latin-1"),
    )
    assert done.returncode == 0, done.stderr
    raw = subprocess.run([sys.executable, HERE.parent / "hv_store.py", "--dir", store, "raw", "0"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="latin-1"))
    assert raw.stdout == "from a process\r\nwith a CR\n".encode()
