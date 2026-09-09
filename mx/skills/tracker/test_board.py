# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown"]
# ///
"""Checks for the board's reading of a tracker. Run: uv run test_board.py

The seam is the tracker loader: a fixture tracker on disk in, ticket state out. The oracle is
the tracker's MARKDOWN.md: the frontier is open, unblocked, unclaimed; a proposed ticket is not
open whatever blocks it; a reference whose file no longer exists counts as done.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from board import (
    Diffviews,
    board_dag,
    feature_dag,
    load_features,
    load_standalone,
    render_page,
    wave_lanes,
)


def ticket(path: Path, status: str, blocked_by: list[str] | None = None, kind: str | None = None) -> None:
    lines = ["---", f"status: {status}"]
    if kind:
        lines.append(f"type: {kind}")
    if blocked_by:
        lines.append(f"blocked-by: [{', '.join(blocked_by)}]")
    title = path.stem.split("-", 1)[1] if path.stem[:2].isdigit() else path.stem
    lines += ["---", "", f"# {title.replace('-', ' ')}", "", "Cut from the worker's closing comment on 01: the suite is slow.", ""]
    path.write_text("\n".join(lines))


@pytest.fixture
def tracker(tmp_path: Path) -> Path:
    root = tmp_path / "agent" / "tickets"
    feature = root / "feat"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("---\nstatus: confirmed\n---\n\n# Feat\n")
    ticket(feature / "01-first.md", "done")
    ticket(feature / "02-second.md", "open")
    ticket(feature / "03-faster-suite.md", "proposed", blocked_by=["01"])
    ticket(feature / "04-uses-fast-suite.md", "open", blocked_by=["03"])
    ticket(feature / "05-after-first.md", "open", blocked_by=["01"])
    ticket(root / "loose-idea.md", "proposed", blocked_by=["feat/02"])
    return root


def load(root: Path):
    dv = Diffviews(root.parent / "diffviews", None)
    features = load_features(root, {}, dv)
    standalone = load_standalone(root, {}, dv)
    return features, standalone


def by_num(feature):
    return {t.num: t for t in feature.tickets}


def test_a_proposed_ticket_is_off_the_frontier_whatever_blocks_it(tracker: Path) -> None:
    (feature,), (loose,) = load(tracker)
    tickets = by_num(feature)
    assert tickets["03"].status == "proposed"
    assert loose.status == "proposed"
    frontier = sorted(t.num for t in feature.tickets if t.status == "open")
    assert frontier == ["02", "05"]


def test_a_ticket_waiting_on_a_proposal_is_blocked_until_the_ruling_lands_as_done(tracker: Path) -> None:
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / "feat" / "03-faster-suite.md", "open", blocked_by=["01"])
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / "feat" / "03-faster-suite.md", "done", blocked_by=["01"])
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "open"


def test_a_rejected_proposal_unblocks_what_waited_on_it(tracker: Path) -> None:
    (tracker / "feat" / "03-faster-suite.md").unlink()
    (feature,), standalone = load(tracker)
    assert by_num(feature)["04"].status == "open"
    assert by_num(feature)["04"].blocked_by == []
    for full in (False, True):
        assert "T_f" in (feature_dag(feature, full) or "")
        board_dag([feature], standalone, full)
    assert wave_lanes(feature)


def test_proposed_tickets_are_drawn_in_every_view_in_their_own_class(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    for full in (False, True):
        assert "03 faster suite\"]:::proposed" in feature_dag(feature, full)
        assert "loose idea\"]:::proposed" in board_dag([feature], standalone, full)
    assert 'class="card proposed"' in wave_lanes(feature)
    page = render_page("demo", [feature], standalone, log="", stamp="s", stamp_src="s.js")
    assert "2 proposed" in page
    assert "standalone open" not in page
    assert "row-proposed" in page
