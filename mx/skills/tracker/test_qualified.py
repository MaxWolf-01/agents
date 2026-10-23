# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown", "markdown-it-py[linkify]"]  # the last four: the demo tracker and the board the shared fixtures import
# ///
"""What a qualified tag names. Run: uv run test_qualified.py

The seam is `qualified.resolver` and `QUALIFIED`, which every page the user reads links a tag by:
the session page now, the board and the review pages after it. The oracle is the ticket below,
written as the tracker skill shapes one, and fewer-workflow-concepts' Decision that a tag the user
reads is `<ticket> D6` or `<ticket> P3`, linked, with what it names as a hover preview.
"""

from pathlib import Path

import pytest

from qualified import QUALIFIED, resolver

TICKET = """---
status: review
---

# Sync

## Brief

Both checkouts stay in step.

## Properties

- P2 A ticket file is written in one checkout only.

## Acceptance criteria

- [ ] It holds.

## Questions

- [D1] **Sync on every commit?** Or on a timer.
- [D2] **Keep the old remote?** Nothing reads it.
  - Ruled 2026-10-20: drop it.

## Comments

- [D3] **Friction** the suite was slow.
- A4 `mx/sync.py:12`: one remote per checkout.
"""


@pytest.fixture
def resolve(tmp_path: Path):
    (tmp_path / "sync.md").write_text(TICKET)
    return resolver(tmp_path)


def test_each_tag_a_ticket_carries_resolves_to_what_it_names(resolve) -> None:
    """A question open and one ruled, a detail entry of the closing comment, a property and an
    assumption: each named by its kind, its words, and for a question its ruling."""
    named = {tag: resolve("sync", tag) for tag in ("D1", "D2", "D3", "P2", "A4")}
    assert {tag: (n.kind, n.open) for tag, n in named.items()} == {
        "D1": ("question", True), "D2": ("question", False), "D3": ("detail", False),
        "P2": ("property", False), "A4": ("assumption", False),
    }
    assert named["D1"].preview == "sync D1 · Sync on every commit? Or on a timer."
    assert named["D2"].preview == "sync D2 · Keep the old remote? Nothing reads it. · Ruled 2026-10-20: drop it."
    assert named["P2"].preview == "sync P2 · A ticket file is written in one checkout only."
    assert named["A4"].preview == "sync A4 · one remote per checkout."


def test_a_tag_names_nothing_where_its_ticket_or_the_tag_is_missing(resolve) -> None:
    assert [resolve(slug, tag) for slug, tag in (("sync", "D9"), ("async", "D1"), ("../sync", "D1"))] == [None, None, None]


def test_a_qualified_tag_is_found_in_text_by_its_slug_and_tag() -> None:
    """Either separator the tracker writes, and never a tag that only ends a longer word or path."""
    text = "sync D1 holds, as does two-main#P3; mx/sync D1, my_sync A4, sync D12x and syncD2 do not."
    assert [m.groups() for m in QUALIFIED.finditer(text)] == [("sync", "D1"), ("two-main", "P3")]
