# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown"]
# ///
"""Checks for the board's reading of a tracker. Run: uv run test_board.py

Three seams: the tracker loader (a fixture tracker on disk in, ticket and queue state out),
the graph sources (which tickets become nodes, in which class), and the rendered page's
groups and status classes. The oracle is the tracker's MARKDOWN.md and the board's --help:
the frontier is open, unblocked, unclaimed; a proposed ticket is not open whatever blocks it;
a reference whose file no longer exists counts as done; a graph draws only tickets with an
edge; a standalone ticket a branch added is shown, one it merely inherited is not; a
needs-human bullet's detail continues on indented lines.
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
    Roots,
    board_graph,
    feature_graph,
    load_features,
    load_needs_human,
    load_standalone,
    render_page,
    tracker_roots,
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
    (feature / "needs-human.md").write_text("- debrief :: the suite is slow, see 03\n")
    ticket(feature / "01-first.md", "done")
    ticket(feature / "02-second.md", "open")
    ticket(feature / "03-faster-suite.md", "proposed", blocked_by=["02"])
    ticket(feature / "04-uses-fast-suite.md", "open", blocked_by=["03"])
    ticket(feature / "05-after-first.md", "open", blocked_by=["01"])
    ticket(root / "loose-idea.md", "proposed", blocked_by=["feat/02"])
    ticket(root / "small-chore.md", "open")
    (root / "quoted.md").write_text('---\nstatus: open\nblocked-by: [feat/01]\n---\n\n# Say "no limit" plainly\n')
    return root


def load(root: Path):
    dv = Diffviews(root.parent / "diffviews", None)
    features = load_features(root, {}, dv)
    standalone = load_standalone(Roots(root, {}, []), dv)
    return features, standalone


def by_num(feature):
    return {t.num: t for t in feature.tickets}


def test_a_proposed_ticket_is_off_the_frontier_whatever_blocks_it(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    assert by_num(feature)["03"].status == "proposed"
    assert {k.slug: k.status for k in standalone} == {"loose-idea": "proposed", "quoted": "open", "small-chore": "open"}
    frontier = sorted(t.num for t in feature.tickets if t.status == "open")
    assert frontier == ["02", "05"]


def test_a_ticket_waiting_on_a_proposal_is_blocked_until_the_ruling_lands_as_done(tracker: Path) -> None:
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / "feat" / "03-faster-suite.md", "open", blocked_by=["02"])
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / "feat" / "03-faster-suite.md", "done")
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "open"


def test_a_rejected_proposal_unblocks_what_waited_on_it_and_leaves_the_graph(tracker: Path) -> None:
    (tracker / "feat" / "03-faster-suite.md").unlink()
    (feature,), standalone = load(tracker)
    assert by_num(feature)["04"].status == "open"
    assert by_num(feature)["04"].blocked_by == []
    graph = feature_graph(feature)
    # 04 waits on nothing now and nothing waits on it: a row, not a node
    assert "uses fast suite" not in graph
    # 05 still waits on the done 01, which is drawn as its dashed context
    assert '01 first"]:::ghost' in graph
    assert "T_f_feat_01 --> T_f_feat_05" in graph
    assert "uses fast suite" not in board_graph([feature], standalone)


def test_a_feature_whose_tickets_wait_on_nothing_has_no_graph(tmp_path: Path) -> None:
    root = tmp_path / "agent" / "tickets"
    (root / "solo").mkdir(parents=True)
    ticket(root / "solo" / "01-only.md", "open")
    (feature,), standalone = load(root)
    assert feature_graph(feature) is None
    assert board_graph([feature], standalone) is None
    page = render_page("demo", [feature], standalone, log="", stamp="s", stamp_src="s.js")
    assert "nothing in solo waits on anything" in page


def test_proposed_tickets_are_drawn_in_their_own_class_and_grouped_on_the_page(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    graph = feature_graph(feature)
    assert '03 faster suite"]:::proposed' in graph
    assert "T_f_feat_02 --> T_f_feat_03" in graph and "T_f_feat_03 --> T_f_feat_04" in graph
    assert 'click T_f_feat_03 "#t-feat-03"' in graph
    board = board_graph([feature], standalone)
    assert 'loose idea"]:::proposed' in board
    assert "T_b_feat_02 --> K_b_loose_idea" in board
    # a raw double quote in a label ends mermaid's string and breaks the whole flowchart
    assert 'K_b_quoted["○ Say ”no limit” plainly"]' in board
    page = render_page("demo", [feature], standalone, log="", stamp="s", stamp_src="s.js")
    assert 'feat <span class="dim">1/4</span>' in page  # the feature chip: the proposal is not part of the count
    assert 'standalone <span class="dim">3</span>' in page
    groups = re.findall(r'id="grp-(\w+)"', page)
    assert groups == ["needs", "open", "claimed", "blocked", "proposed", "done", "log"][:1] + [g for g in ["open", "blocked", "proposed", "done"]] + ["log"]
    assert '<h2>proposed <span class="n">2</span></h2>' in page  # 03 and the loose idea
    assert 'class="ticket row-proposed" id="t-feat-03" data-feature="feat" data-num="03"' in page
    assert '<span class="badges"><span class="badge proposed">' in page
    assert 'id="needs-feat-0" data-feature="feat"' in page
    assert page.index('id="grp-needs"') < page.index('id="grp-open"')
    assert 'class="g" data-feature="feat"' in page and 'data-key="g:*"' in page
    class_defs = re.search(r'const classDefs = \[([^\]]*)\]', page).group(1)
    for status in STATUS_SYMBOL:
        assert f'"{status}"' in class_defs


def test_a_done_ticket_another_feature_waits_on_is_drawn_as_its_context(tmp_path: Path) -> None:
    root = tmp_path / "agent" / "tickets"
    (root / "base").mkdir(parents=True)
    (root / "top").mkdir()
    ticket(root / "base" / "01-storage.md", "done")
    ticket(root / "base" / "02-cleanup.md", "proposed")
    ticket(root / "top" / "01-uses-storage.md", "open", blocked_by=["base/01"])
    features, standalone = load(root)
    base, top = features
    assert feature_graph(base) is None  # nothing within base waits on anything
    board = board_graph(features, standalone)
    assert '01 storage"]:::ghost' in board
    assert "T_b_base_01 --> T_b_top_01" in board
    assert "cleanup" not in board


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


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(cwd), *args],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_a_standalone_ticket_a_branch_added_is_shown_and_one_it_inherited_is_not(tracker: Path) -> None:
    repo = tracker.parent.parent
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tracker")
    wt = repo.parent / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "feat")  # a worktree on the feature's branch
    # main retires a chore after the branch was cut; the branch's inherited copy must not bring it back
    git(repo, "rm", "-q", "agent/tickets/small-chore.md")
    git(repo, "commit", "-q", "-m", "small-chore: done")
    branch_root = wt / "agent" / "tickets"
    ticket(branch_root / "filed-on-branch.md", "open")  # untracked on the branch
    (branch_root / "notes.md").write_text("# not a ticket\n\njust a note beside the tickets\n")
    ticket(branch_root / "loose-idea.md", "open", blocked_by=["feat/02"])  # changed on the branch; main's copy wins
    roots = tracker_roots(tracker)
    assert roots.main == tracker
    assert roots.overrides == {"feat": branch_root / "feat"}
    assert roots.branches == [("feat", branch_root)]
    standalone = load_standalone(roots, Diffviews(tracker.parent / "diffviews", None))
    assert {k.slug: k.source for k in standalone} == {"loose-idea": None, "quoted": None, "filed-on-branch": "feat"}
    assert {k.slug: k.status for k in standalone}["loose-idea"] == "proposed"
    page = render_page("demo", load_features(tracker, roots.overrides, Diffviews(tracker.parent / "diffviews", None)), standalone, log="", stamp="s", stamp_src="s.js")
    assert 'title="filed on branch feat, not on the main branch">on feat</span>' in page


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
