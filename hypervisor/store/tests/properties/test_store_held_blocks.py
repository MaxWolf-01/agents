"""lifelong-hypervisor#P2 and #P3 over what the store took on after its first checks: compressions
written in any order, some held until the blocks before them land, and appends carrying a gist."""

import tempfile
from collections.abc import Callable

from hypothesis import given, settings
from hypothesis import strategies as st
from test_store_properties import COVERS, DEFAULT_BUDGET, SLOW, STAMPED, command, entries, entry, kept, lengths, run, summary, text, view


def answer_due_in(order: Callable[[list[str]], list[str]], store: str, most: int | None = None) -> None:
    """Write what `due` lists, each round in the given order, until none is due or `most` are written."""
    written = 0
    while blocks := run(store, "due")[1].split():
        for block in order(blocks):
            if written == most:
                return
            assert run(store, "compress", block, stdin=f"summary of {block}")[0] == 0, f"due listed {block}, compress refused it"
            written += 1


@settings(SLOW, max_examples=30)
@given(st.data())
def test_the_view_never_exceeds_its_budget_whatever_order_compressions_land_in(data: st.DataObject) -> None:
    budget = data.draw(st.one_of(st.none(), st.integers(8, 48)), label="budget")
    limit = budget or DEFAULT_BUDGET
    n = data.draw(lengths(limit), label="log length")
    rnd = data.draw(st.randoms(use_true_random=False), label="order")
    answered = data.draw(st.integers(0, n), label="compressions written before the first view")

    def shuffled(blocks: list[str]) -> list[str]:
        return rnd.sample(blocks, len(blocks))

    with tempfile.TemporaryDirectory() as store:
        assert run(store, "init")[0] == 0
        for i in range(n):
            assert run(store, "append", stdin=f"entry {i}")[0] == 0
        answer_due_in(shuffled, store, most=answered)
        code, _, lines = view(store, budget)
        if code == 0:
            assert len(lines) <= limit, "a view with compressions outstanding"
        answer_due_in(shuffled, store)
        code, header, lines = view(store, budget)
        assert code == 0, header
        assert all(STAMPED.match(line) for line in lines)
        assert len(lines) == min(n, limit)
        covered = [(int(m[1]), int(m[2] or m[1])) for m in map(COVERS.match, lines) if m]
        assert len(covered) == len(lines)
        ends = [-1] + [hi for _, hi in covered]
        assert all(lo == end + 1 for (lo, _), end in zip(covered, ends)), "the lines leave a gap or overlap"
        assert ends[-1] == n - 1
        # A held block reads back as written, wherever it was held.
        assert all(line.split(" ", 2)[2] == f"summary of {lo}-{hi}" for line, (lo, hi) in zip(lines, covered) if hi > lo)


# A command line and its stdin, as in the first checks, plus appends with a gist and compressions of
# any block `due` lists, not only its first.
held_command = st.one_of(
    command,
    st.tuples(text.map(lambda g: ("append", "--gist", g)), entry),
    st.tuples(st.integers(0, 40).map(lambda i: ("compress", f"<due {i}>")), summary),
)


@settings(SLOW, max_examples=30)
@given(st.lists(entry, min_size=1, max_size=12), st.lists(held_command, max_size=30))
def test_no_command_changes_an_earlier_entry_with_gists_and_held_blocks(first: list[str], commands: list[tuple[tuple, str]]) -> None:
    with tempfile.TemporaryDirectory() as store:
        assert run(store, "init")[0] == 0
        for t in first:
            assert run(store, "append", stdin=t)[0] == 0
        logged = len(first)
        before = entries(store, logged)
        for args, stdin in commands:
            if args[0] == "compress" and args[1].startswith("<due"):  # `<due>` is the first, `<due N>` the Nth
                due = run(store, "due")[1].split()
                args = ("compress", due[int(args[1][5:-1] or 0) % len(due)]) if due else ("due",)
            code, _ = run(store, *args, stdin=stdin)
            if args == ("append",):
                assert code == 0, f"append refused {stdin!r}"
            if args[0] == "append" and code == 0:
                logged += 1
            after = entries(store, logged)
            changed = [key for key in before if not kept(key, before[key], after[key])]
            assert not changed, f"`{' '.join(map(str, args))}` changed {changed}"
            before = after
