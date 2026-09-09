"""Property: the ranking tiers `find` documents hold for every vault shape.

memex's README states the ranking contract as "exact title/alias > substring > fuzzy".
These properties encode the exact-match tier of that contract: whatever else is in the
vault, a note wins the top slot for its own title and for each of its own aliases.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from memex_md.find import find_notes

# Note titles and aliases as they occur in a vault: single words, hyphenated or
# underscored, no whitespace (`find_notes` splits the query on whitespace, so a
# whitespace-free key is what the exact-match tier is defined over).
KEY_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
keys = st.text(alphabet=KEY_ALPHABET, min_size=1, max_size=12)
folders = st.lists(st.sampled_from(["notes", "docs", "math", "zettel", "daily"]), max_size=2)

Note = tuple[str, str, list[str]]  # (path, title, aliases), the shape find_notes takes


@st.composite
def vaults(draw: st.DrawFn) -> list[Note]:
    """A vault whose exact-match keys (titles and aliases) are unique.

    Uniqueness is the precondition the exact-match tier needs: two notes claiming the
    same key are genuinely tied, and the contract says nothing about which wins.
    """
    pool = draw(st.lists(keys, min_size=1, max_size=10, unique_by=str.lower))
    notes: list[Note] = []
    i = 0
    while i < len(pool):
        title = pool[i]
        i += 1
        n_aliases = draw(st.integers(min_value=0, max_value=min(2, len(pool) - i)))
        aliases = pool[i : i + n_aliases]
        i += n_aliases
        path = "/".join([*draw(folders), f"{title}.md"])
        notes.append((path, title, aliases))
    return notes


@given(vaults())
@settings(max_examples=300)
def test_note_ranks_first_for_its_own_title(notes: list[Note]) -> None:
    for path, title, _ in notes:
        results = find_notes(notes, title, limit=len(notes))
        assert results, f"{title!r} found nothing in a vault that contains it"
        assert results[0].path == path


@given(vaults())
@settings(max_examples=300)
def test_note_ranks_first_for_each_of_its_aliases(notes: list[Note]) -> None:
    for path, _, aliases in notes:
        for alias in aliases:
            results = find_notes(notes, alias, limit=len(notes))
            assert results, f"alias {alias!r} found nothing in a vault that contains it"
            assert results[0].path == path


@given(vaults(), keys, st.integers(min_value=0, max_value=12))
@settings(max_examples=300)
def test_results_respect_limit_and_are_ranked_descending(notes: list[Note], query: str, limit: int) -> None:
    results = find_notes(notes, query, limit=limit)
    assert len(results) <= limit
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
