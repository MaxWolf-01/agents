# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown"]
# ///
"""Checks for the board's reading of a tracker. Run: uv run test_board.py

Two seams: the tracker loader (a fixture tracker on disk in, ticket and queue state out) and
the rendered page's status classes (what the loader read, drawn). The oracle is the tracker's
MARKDOWN.md: a proposed ticket sits in every view in its own colour, keeping its status whatever
blocks it; a reference whose file no longer exists counts as done; the needs-human.md beside a
set of tickets is their queue rather than one of them; a needs-human bullet's detail continues on
indented lines.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from board import (
    STATUS_SYMBOL,
    Diffviews,
    board_dag,
    feature_dag,
    load_features,
    load_needs_human,
    load_standalone,
    render,
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
    ticket(feature / "03-faster-suite.md", "proposed", blocked_by=["02"])
    ticket(feature / "04-uses-fast-suite.md", "open", blocked_by=["03"])
    ticket(feature / "05-after-first.md", "open", blocked_by=["01"])
    ticket(root / "loose-idea.md", "proposed", blocked_by=["feat/02"])
    ticket(root / "small-chore.md", "open")
    (root / "quoted.md").write_text('---\nstatus: open\n---\n\n# Say "no limit" plainly\n')
    (root / "needs-human.md").write_text(
        "---\nworker-host: agent@pc\n---\n"
        "- rule on loose-idea :: built while proposed; its page is agent/diffviews/loose-idea.html\n"
    )
    return root


def load(root: Path):
    dv = Diffviews(root.parent / "diffviews", None)
    features = load_features(root, {}, dv)
    standalone = load_standalone(root, {}, dv)
    return features, standalone


def by_num(feature):
    return {t.num: t for t in feature.tickets}


def test_a_proposed_ticket_keeps_its_status_whatever_blocks_it(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    assert by_num(feature)["03"].status == "proposed"
    assert {k.slug: k.status for k in standalone} == {"loose-idea": "proposed", "quoted": "open", "small-chore": "open"}
    assert sorted(t.num for t in feature.tickets if t.status == "open") == ["02", "05"]


def test_a_ticket_waiting_on_a_proposal_is_blocked_until_the_ruling_lands_as_done(tracker: Path) -> None:
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / "feat" / "03-faster-suite.md", "open", blocked_by=["02"])
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / "feat" / "03-faster-suite.md", "done")
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "open"


def test_a_rejected_proposal_unblocks_what_waited_on_it(tracker: Path) -> None:
    (tracker / "feat" / "03-faster-suite.md").unlink()
    (feature,), standalone = load(tracker)
    assert by_num(feature)["04"].status == "open"
    assert by_num(feature)["04"].blocked_by == []
    for full in (False, True):
        assert '04 uses fast suite"]:::open' in feature_dag(feature, full)
        assert '04 uses fast suite"]:::open' in board_dag([feature], standalone, full)
    assert 'card open"><a class="cardlink" href="#t-feat-04"' in wave_lanes(feature)


def test_proposed_tickets_are_drawn_in_every_view_in_their_own_class(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    for full in (False, True):
        assert '03 faster suite"]:::proposed' in feature_dag(feature, full)
        assert 'loose idea"]:::proposed' in board_dag([feature], standalone, full)
    lanes = wave_lanes(feature)
    assert lanes.index("proposed — awaiting ruling") > lanes.rindex("wave +")  # 04 waits on 03, which waits on 02
    assert 'card proposed"><a class="cardlink" href="#t-feat-03"' in lanes.split("proposed — awaiting ruling")[1]
    page = render_page("demo", [feature], standalone, ([], None), log="", stamp="s", stamp_src="s.js")
    assert "1/4 done" in page  # the top bar: the proposal is not part of the feature's count
    assert 'feat <span class="dim">1/4</span>' in page  # the feature chip agrees
    assert '<span class="badges"><span class="badge proposed">' in page
    assert 'click T_f0_feat_03 "#t-feat-03"' in feature_dag(feature, False)
    # a raw double quote in a label ends mermaid's string and breaks the whole flowchart
    assert 'K_b0_quoted["○ Say ”no limit” plainly"]' in board_dag([feature], standalone, False)
    assert "2 standalone open" in page
    assert "2 proposed" in page
    assert "1 blocked · 1 proposed" in page  # the feature's own counts
    assert 'class="ticket row-proposed" id="t-feat-03"' in page
    class_defs = re.search(r'const classDefs = \[([^\]]*)\]', page).group(1)
    for status in STATUS_SYMBOL:
        assert f'"{status}"' in class_defs


def test_the_standalone_queue_is_the_tracker_roots_own_and_not_a_ticket(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    assert "needs-human" not in {k.slug for k in standalone}
    page = render_page(
        "demo", [feature], standalone, load_needs_human(tracker / "needs-human.md"),
        log="", stamp="s", stamp_src="s.js",
    )
    assert '<a class="chip open" href="#standalone">standalone</a> rule on loose-idea' in page
    assert 'id="standalone"' in page
    assert "workers on agent@pc" in page


def test_a_queue_entry_outliving_its_ticket_still_has_a_section_to_link_to(tracker: Path) -> None:
    # the ruling on the last standalone ticket was `reject`, which deletes the file
    (feature,), _ = load(tracker)
    page = render_page(
        "demo", [feature], [], load_needs_human(tracker / "needs-human.md"),
        log="", stamp="s", stamp_src="s.js",
    )
    assert 'id="standalone"' in page
    assert "workers on agent@pc" in page


def test_render_reads_the_queue_beside_the_tickets(tracker: Path, tmp_path: Path) -> None:
    repo = tracker.parent.parent
    git = ["git", "-c", "user.email=t@e", "-c", "user.name=t", "-C", str(repo)]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "the tracker"], check=True)
    out = tmp_path / "out" / "board.html"
    render(tracker, {}, repo, out)
    assert "rule on loose-idea" in out.read_text()


def test_a_queue_entry_keeps_its_indented_detail(tmp_path: Path) -> None:
    queue = tmp_path / "needs-human.md"
    queue.write_text(
        "---\nworker-host: agent@pc\n---\n\n"
        "- debrief :: **fixed** a1b2c3 pins the averaging rule.\n"
        "  **proposed** 03, 04.\n\n"
        "  **left** two case-flip survivors, the value is case-insensitive.\n"
        "- Which colour :: the prototype at agent/prototypes/colour\n"
    )
    entries, host = load_needs_human(queue)
    assert host == "agent@pc"
    assert entries == [
        "debrief :: **fixed** a1b2c3 pins the averaging rule.\n**proposed** 03, 04.\n\n**left** two case-flip survivors, the value is case-insensitive.",
        "Which colour :: the prototype at agent/prototypes/colour",
    ]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
