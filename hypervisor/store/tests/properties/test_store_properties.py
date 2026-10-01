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
from unittest import mock

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import hv_store  # noqa: E402

SLOW = settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
DEFAULT_BUDGET = 256  # the parent's view budget
STAMPED = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(\s|$)")
COVERS = re.compile(r"\S+ #(\d+)(?:-(\d+))?(\s|$)")

# Any text a turn can produce, multi-byte characters included; argv cannot carry NUL.
text = st.text(st.characters(codec="utf-8", exclude_characters="\x00"), min_size=1, max_size=40)
# Over the 512 bytes an entry holds, so the store has to put it in its sidecar.
long_text = st.builds(lambda head, tail: head + "é" * 300 + tail, text, text)
# Two lines in one text, which a single line of the view cannot hold as it is.
multiline = st.builds(lambda head, tail: f"{head}\n{tail}", text, text)
entry = st.one_of(text, text, multiline, long_text)
summary = st.one_of(text, multiline, long_text)


def run(store: str, *args: object, stdin: str = "") -> tuple[int, str]:
    """One command line, as its caller sees it: the exit status and what it printed. An exception
    that escapes `main` is a process dying with status 1, except the stub's, which the expected
    failures wait for."""
    out = io.StringIO()
    # Text over bytes, as a process's stdin is, so a store may read either.
    given = io.TextIOWrapper(io.BytesIO(stdin.encode()), encoding="utf-8", newline="\n")
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()), mock.patch("sys.stdin", given):
        try:
            code = hv_store.main(["--dir", store, *map(str, args)])
        except SystemExit as exit:
            code = exit.code if isinstance(exit.code, int) else (exit.code is not None)
        except NotImplementedError:
            raise
        except Exception:
            code = 1
    return code or 0, out.getvalue()


def append_all(store: str, texts: list[str]) -> None:
    for t in texts:
        assert run(store, "append", stdin=t)[0] == 0, f"append refused {t!r}"


def answer_due(store: str, summaries: list[str], most: int | None = None) -> None:
    """Write the compressions the store lists as due, until none is or `most` are written. A
    generated summary the store refuses (a newline, too many bytes) is replaced by a plain line,
    which it has to take."""
    written: set[str] = set()
    while blocks := run(store, "due")[1].split():
        for block in blocks:
            if len(written) == most:
                return
            assert block not in written, f"due lists {block} again after it was written"
            if run(store, "compress", block, stdin=summaries[len(written) % len(summaries)])[0] != 0:
                assert run(store, "compress", block, stdin=f"summary of {block}")[0] == 0, f"due listed {block}, compress refused it"
            written.add(block)


def view(store: str, budget: int | None) -> tuple[int, str, list[str]]:
    """The view's status, its header and its lines. A line ends at "\\n" only: `splitlines` would also
    break at characters a summary may hold."""
    code, out = run(store, "view", *(["--budget", budget] if budget else []))
    header, *lines = out.removesuffix("\n").split("\n")
    return code, header, lines


def lengths(budget: int) -> st.SearchStrategy[int]:
    """Log lengths that reach past the budget, weighted to where a tiling breaks: the budget's edge,
    powers of two and their neighbours."""
    edges = {budget - 1, budget, budget + 1, 2 * budget} | {2**k + d for k in range(1, 10) for d in (-1, 0, 1)}
    return st.one_of(st.integers(0, 3 * budget), st.sampled_from(sorted(e for e in edges if 0 <= e <= 3 * budget)))


@settings(SLOW, max_examples=40)
@given(st.data())
def test_the_view_never_exceeds_its_budget(data: st.DataObject) -> None:
    """lifelong-hypervisor#P2, at budgets from 8 lines up and at the default, with compressions
    outstanding and with all of them written. A budget under the bit length of the log's length is left
    out: the merge tree cannot tile such a log in fewer lines than its set bits, and the parent's budget
    of 256 lines puts that past any log that will ever exist."""
    budget = data.draw(st.one_of(st.none(), st.integers(8, 48)), label="budget")
    limit = budget or DEFAULT_BUDGET
    n = data.draw(lengths(limit), label="log length")
    # The texts repeat across the log, numbered so no two entries read alike.
    texts = data.draw(st.lists(entry, min_size=1, max_size=8), label="entry texts")
    summaries = data.draw(st.lists(summary, min_size=1, max_size=4), label="summaries")
    answered = data.draw(st.integers(0, n), label="compressions written before the first view")
    with tempfile.TemporaryDirectory() as store:
        assert run(store, "init")[0] == 0
        append_all(store, [f"{texts[i % len(texts)]} #{i}" for i in range(n)])
        answer_due(store, summaries, most=answered)
        # The view may refuse while a compression it needs is outstanding; one it renders keeps the budget.
        code, _, lines = view(store, budget)
        if code == 0:
            assert len(lines) <= limit, "a view with compressions outstanding"
        answer_due(store, summaries)
        code, header, lines = view(store, budget)
        assert code == 0, header
        assert not STAMPED.match(header), "the view starts with its header, not a view line"
        assert all(STAMPED.match(line) for line in lines), "every view line starts with its start time"
        assert len(lines) <= limit
        # A view that drops lines keeps the bound. The parent's view is constant-size, and its lines
        # are contiguous: together they cover the log from its first entry to its last, in order.
        assert len(lines) == min(n, limit)
        covered = [(int(m[1]), int(m[2] or m[1])) for m in map(COVERS.match, lines) if m]
        assert len(covered) == len(lines), "every view line names the entry or block it covers"
        ends = [-1] + [hi for _, hi in covered]
        assert all(lo == end + 1 for (lo, _), end in zip(covered, ends)), "the lines leave a gap or overlap"
        assert ends[-1] == n - 1, "the view stops short of the newest entry"


# A block id as a caller might type it: a real block, a misaligned one, or not a block at all.
block_id = st.one_of(
    st.integers(0, 6).flatmap(lambda k: st.integers(0, 8).map(lambda i: f"{i * 2**k}-{(i + 1) * 2**k - 1}")),
    st.tuples(st.integers(-1, 40), st.integers(-1, 40)).map(lambda p: f"{p[0]}-{p[1]}"),
    text,
)
# A command line and the text on its stdin.
command = st.one_of(
    st.tuples(st.just(("append",)), entry),
    st.tuples(st.just(("init",)), st.just("")),
    st.tuples(st.lists(text, max_size=2).map(lambda rest: ("init", *rest)), st.just("")),
    st.tuples(st.just(("view",)), st.just("")),
    st.tuples(st.integers(1, 12).map(lambda b: ("view", "--budget", b)), st.just("")),
    st.tuples(block_id.map(lambda b: ("zoom", b)), st.just("")),
    st.tuples(st.one_of(st.sampled_from([".", ".*", "#1", "(", "é"]), text).map(lambda r: ("recall", r)), st.just("")),
    st.tuples(st.one_of(st.integers(-2, 40), text).map(lambda i: ("raw", i)), st.just("")),
    st.tuples(st.just(("due",)), st.just("")),
    st.tuples(st.just(("compress", "<due>")), summary),
    st.tuples(block_id.map(lambda b: ("compress", b)), summary),
    st.tuples(st.lists(text, max_size=3).map(tuple), text),  # whatever else a command line can be handed
)


def entries(store: str, logged: int) -> dict[str, str]:
    """Every logged entry as the command line reads it back: each one whole through `raw`, and each
    pair, stamps included, through `zoom`. A pair whose second entry is not logged yet shows its first."""
    seen = {f"raw {i}": run(store, "raw", i) for i in range(logged)}
    seen |= {f"zoom {k}-{k + 1}": run(store, "zoom", f"{k}-{k + 1}") for k in range(0, logged, 2)}
    unread = [key for key, (code, _) in seen.items() if code != 0]
    assert not unread, f"logged entries the command line cannot read: {unread}"
    return {key: out for key, (_, out) in seen.items()}


@settings(SLOW, max_examples=30)
@given(st.lists(entry, min_size=1, max_size=12), st.lists(command, max_size=25))
def test_no_command_changes_an_earlier_entry(first: list[str], commands: list[tuple[tuple, str]]) -> None:
    """lifelong-hypervisor#P3: whatever commands follow, every entry already logged reads back as it
    did. A pair that gains its second entry keeps its first as it read alone."""
    with tempfile.TemporaryDirectory() as store:
        assert run(store, "init")[0] == 0
        append_all(store, first)
        logged = len(first)
        before = entries(store, logged)
        for args, stdin in commands:
            if args == ("compress", "<due>"):
                due = run(store, "due")[1].split()
                args = ("compress", due[0]) if due else ("due",)
            code, _ = run(store, *args, stdin=stdin)
            if args == ("append",):
                assert code == 0, f"append refused {stdin!r}"
                logged += 1
            after = entries(store, logged)
            changed = [key for key in before if not kept(key, before[key], after[key])]
            assert not changed, f"`{' '.join(map(str, args))}` changed {changed}"
            before = after


def kept(key: str, before: str, after: str) -> bool:
    """An entry read whole reads the same; a pair may only gain its second entry."""
    return after == before if key.startswith("raw") else after.startswith(before)
