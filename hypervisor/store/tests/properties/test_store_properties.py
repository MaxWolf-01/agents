"""lifelong-hypervisor#P2 and #P3 at the store's command line, over generated logs.

The command line is entered through `hv_store.main`, in-process: a log of a few hundred entries
takes as many appends and about as many compressions, which a process per call would make minutes.
"""

import contextlib
import io
import re
import sys
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import hv_store  # noqa: E402

LIFTED_BY_STORE = pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="lifted by hypervisor-store")
SLOW = settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
DEFAULT_BUDGET = 256  # the parent's view budget
STAMPED = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(\s|$)")

# Any text a turn can produce, newlines and multi-byte characters included; argv cannot carry NUL.
text = st.text(st.characters(codec="utf-8", exclude_characters="\x00"), min_size=1, max_size=40)
# Over the 512 bytes an entry holds, so the store has to put it in its sidecar.
long_text = st.builds(lambda head, tail: head + "é" * 300 + tail, text, text)
# Two lines in one text, which a single line of the view cannot hold as it is.
multiline = st.builds(lambda head, tail: f"{head}\n{tail}", text, text)
entry = st.one_of(text, text, multiline, long_text)
summary = st.one_of(text, multiline, long_text)


def run(store: str, *args: object) -> tuple[int, str]:
    """One command line, as its caller sees it: the exit status and what it printed. An exception
    that escapes `main` is a process dying with status 1, except the stub's, which the expected
    failures wait for."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = hv_store.main(["--dir", store, *map(str, args)])
        except SystemExit as exit:
            code = exit.code if isinstance(exit.code, int) else (exit.code is not None)
        except NotImplementedError:
            raise
        except Exception:
            code = 1
    return code or 0, out.getvalue()


def append_all(store: str, texts: list[str]) -> int:
    """Append every text and return how many the store took; one it refuses is not in the log."""
    return sum(run(store, "append", t)[0] == 0 for t in texts)


def answer_due(store: str, summaries: list[str]) -> None:
    """Write every compression the store lists as due, until none is. A generated summary the store
    refuses (a newline, too many bytes) is replaced by a plain line, which it has to take."""
    written: set[str] = set()
    while blocks := run(store, "due")[1].split():
        for block in blocks:
            assert block not in written, f"due lists {block} again after it was written"
            line = summaries[len(written) % len(summaries)]
            if run(store, "compress", block, line)[0] != 0:
                assert run(store, "compress", block, f"summary of {block}")[0] == 0, f"due listed {block}, compress refused it"
            written.add(block)


def lengths(budget: int) -> st.SearchStrategy[int]:
    """Log lengths that reach past the budget, weighted to where a tiling breaks: the budget's edge,
    powers of two and their neighbours."""
    edges = {budget - 1, budget, budget + 1, 2 * budget} | {2**k + d for k in range(1, 10) for d in (-1, 0, 1)}
    return st.one_of(st.integers(0, 3 * budget), st.sampled_from(sorted(e for e in edges if 0 <= e <= 3 * budget)))


@LIFTED_BY_STORE
@settings(SLOW, max_examples=40)
@given(st.data())
def test_the_view_never_exceeds_its_budget(data: st.DataObject) -> None:
    """P2, at budgets from 8 lines up and at the default. A budget under the bit length of the log's
    length is left out: the merge tree cannot tile such a log in fewer lines than its set bits, and the
    parent's budget of 256 lines puts that past any log that will ever exist."""
    budget = data.draw(st.one_of(st.none(), st.integers(8, 48)), label="budget")
    limit = budget or DEFAULT_BUDGET
    n = data.draw(lengths(limit), label="log length")
    # The texts repeat across the log, numbered so no two entries read alike.
    texts = data.draw(st.lists(entry, min_size=1, max_size=8), label="entry texts")
    summaries = data.draw(st.lists(summary, min_size=1, max_size=4), label="summaries")
    with tempfile.TemporaryDirectory() as store:
        assert run(store, "init")[0] == 0
        logged = append_all(store, [f"{texts[i % len(texts)]} #{i}" for i in range(n)])
        answer_due(store, summaries)
        code, out = run(store, "view", *(["--budget", budget] if budget else []))
        assert code == 0, out
        # A line ends at "\n" only: `splitlines` would also break at characters a summary may hold.
        lines = out.removesuffix("\n").split("\n")[1:]  # the first line is the header
        assert all(STAMPED.match(line) for line in lines), "every view line starts with its start time"
        assert len(lines) <= limit
        # A view that drops lines would satisfy the bound; the brief's view is constant-size.
        assert len(lines) == min(logged, limit)


# A block id as a caller might type it: a real block, a misaligned one, or not a block at all.
block_id = st.one_of(
    st.integers(0, 6).flatmap(lambda k: st.integers(0, 8).map(lambda i: f"{i * 2**k}-{(i + 1) * 2**k - 1}")),
    st.tuples(st.integers(-1, 40), st.integers(-1, 40)).map(lambda p: f"{p[0]}-{p[1]}"),
    text,
)
command = st.one_of(
    st.tuples(st.just("append"), entry),
    st.tuples(st.just("view")),
    st.tuples(st.just("view"), st.just("--budget"), st.integers(1, 12)),
    st.tuples(st.just("zoom"), block_id),
    st.tuples(st.just("recall"), st.one_of(st.sampled_from([".", ".*", "#1", "(", "é"]), text)),
    st.tuples(st.just("raw"), st.one_of(st.integers(-2, 40), text)),
    st.tuples(st.just("due")),
    st.tuples(st.just("compress"), st.just("<due>"), summary),
    st.tuples(st.just("compress"), block_id, summary),
    st.lists(text, max_size=3).map(tuple),  # whatever else a command line can be handed
)


def entries(store: str, logged: int) -> dict[str, str]:
    """Every logged entry as the command line reads it back: each one whole through `raw`, and each
    complete pair, stamps included, through `zoom`."""
    seen = {f"raw {i}": run(store, "raw", i) for i in range(logged)}
    seen |= {f"zoom {k}-{k + 1}": run(store, "zoom", f"{k}-{k + 1}") for k in range(0, logged - 1, 2)}
    unread = [key for key, (code, _) in seen.items() if code != 0]
    assert not unread, f"logged entries the command line cannot read: {unread}"
    return {key: out for key, (_, out) in seen.items()}


@LIFTED_BY_STORE
@settings(SLOW, max_examples=30)
@given(st.lists(entry, min_size=1, max_size=12), st.lists(command, max_size=25))
def test_no_command_changes_an_earlier_entry(first: list[str], commands: list[tuple]) -> None:
    """P3: whatever commands follow, every entry already logged reads back exactly as it did."""
    with tempfile.TemporaryDirectory() as store:
        assert run(store, "init")[0] == 0
        logged = append_all(store, first)
        before = entries(store, logged)
        for args in commands:
            if args[:2] == ("compress", "<due>"):
                due = run(store, "due")[1].split()
                args = ("compress", due[0], args[2]) if due else ("due",)
            code, _ = run(store, *args)
            logged += args[:1] == ("append",) and code == 0
            after = entries(store, logged)
            changed = [key for key in before if after[key] != before[key]]
            assert not changed, f"`{' '.join(map(str, args))}` changed {changed}"
            before = after
