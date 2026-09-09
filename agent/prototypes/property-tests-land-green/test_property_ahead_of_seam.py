import pytest
from hypothesis import given, strategies as st
from pkg.seam import rank


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="seam stub; lifted by 02-rank")
@given(st.lists(st.text(min_size=1), min_size=1, unique=True))
def test_exact_match_ranks_first(items):
    q = items[0]
    assert rank(items, q)[0] == q
