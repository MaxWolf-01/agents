# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown"]
# ///
"""Checks for the board's reading of a tracker. Run: uv run test_board.py

Four seams: the tracker loader (a fixture tracker on disk in, ticket state out), the
checkout discovery (a git repo with worktrees in, which copy of what is read out), the graph
sources (which tickets become nodes, in which class, joined by which edges), and the rendered
page (groups, rows, the attributes the page's script matches against the graph sources). The
oracle is the tracker's MARKDOWN.md and the board's --help: the frontier is open, unblocked,
unclaimed; a proposed ticket is not open whatever blocks it; a build in review waits for the
user's ruling in its own group and unblocks nothing until the accept writes done; a gh reference
is a link to GitHub; a row copies the absolute path of the file it was read from; a review page
is linked on the address diffview serves it on, and as a file where nothing serves it; a reference whose file no longer exists counts as done; a graph draws only
tickets with an edge; a standalone ticket a branch added is shown, one it merely inherited is
not; markdown at the tracker root that declares no status is not a ticket.

Under "properties" at the end sit the executable Properties of
agent/tickets/board-orients/spec.md that belong to these seams; that spec is their oracle.
"""

import html
import itertools
import json
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

import board
import tracker as tracker_module
from board import (
    ALONE,
    STATUS_SYMBOL,
    Seen,
    TICKET_STATUSES,
    Diffviews,
    Roots,
    board_graph,
    changed_note,
    content_stamp,
    load_tickets,
    look,
    needs_me,
    render,
    render_page,
    run_out,
    serve_diffviews,
    ticket_sessions,
    tracker_roots,
    tracker_snapshot,
    tree_graph,
)
import briefing
import github
from briefing import CADENCE, QUIET, Briefing, cache_path
from demo_tracker import S1, S2, S3, S4, Demo, build as build_demo
from demo_tracker import commit as demo_commit, git as demo_git, transcript as write_transcript

TREE = "feat-a"  # a hyphen, so a slugged id and the raw slug can be told apart
STUB_ADDRESS = "http://127.0.0.1:54321"


def ticket(
    path: Path, status: str, blocked_by: list[str] | None = None, parent: str | None = None,
    needs_user: bool = False, gh: list[str] | None = None, priority: int | None = 2,
    size: str | None = "S", brief: str | None = None, name: str | None = None,
) -> None:
    """One ticket file the tracker's rules accept, at `path`; its slug is the file's stem."""
    lines = ["---", f"status: {status}"]
    if parent:
        lines.append(f"parent: {parent}")
    if blocked_by:
        lines.append(f"blocked-by: [{', '.join(blocked_by)}]")
    if needs_user:
        lines.append("needs-user: true")
    if gh:
        lines.append(f"gh: [{', '.join(gh)}]")
    if priority:
        lines.append(f"priority: {priority}")
    if size:
        lines.append(f"size: {size}")
    lines += ["---", "", f"# {name or path.stem.replace('-', ' ')}", "", "## Brief", ""]
    if brief:
        lines += [brief, ""]
    lines += ["## What to build", "", "Cut from the worker's closing comment on first: the `suite` is slow.", ""]
    path.write_text("\n".join(lines))


@pytest.fixture
def tracker(tmp_path: Path) -> Path:
    """A flat tracker: one tree of seven tickets under `feat-a`, and three tickets in no tree."""
    root = tmp_path / "repo" / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / f"{TREE}.md", "open", priority=1, size="L", name="Feat")
    ticket(root / "first.md", "done", parent=TREE)
    ticket(root / "second.md", "open", parent=TREE)
    ticket(root / "faster-suite.md", "proposed", parent=TREE, blocked_by=["second"])
    ticket(root / "uses-fast-suite.md", "open", parent=TREE, blocked_by=["faster-suite"])
    ticket(root / "after-first.md", "open", parent=TREE, blocked_by=["first"])
    ticket(root / "needs-chore.md", "open", parent=TREE, blocked_by=["small-chore"])
    ticket(root / "built.md", "review", parent=TREE, blocked_by=["first"], gh=["acme/backend#317", "acme/helix#412"])
    ticket(root / "loose-idea.md", "proposed", blocked_by=["second"])
    ticket(root / "small-chore.md", "open")
    ticket(root / "quoted.md", "open", blocked_by=["first"], name='Say "no limit" plainly')
    return root


@pytest.fixture
def stub_diffview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A diffview that records its arguments and answers as the real one does on --serve."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "diffview"
    stub.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" > "$0.args"\n'
        f'echo "diffview: serving $2 at {STUB_ADDRESS}/  (exits 30 minutes after the last page closes)"\n'
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    return stub


def load(root: Path) -> dict[str, board.Ticket]:
    """The tracker as the board reads it, by slug."""
    dv = Diffviews(root.parent / "diffviews", None)
    return {t.slug: t for t in load_tickets(Roots(root, []), dv)}


def page_of(root: Path) -> str:
    return render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")


# ---- loader ---------------------------------------------------------------


def test_a_proposed_ticket_is_off_the_frontier_whatever_blocks_it(tracker: Path) -> None:
    read = load(tracker)
    assert read["faster-suite"].status == "proposed"
    assert read["loose-idea"].status == "proposed"
    assert sorted(slug for slug, t in read.items() if t.status == "open") == [
        "after-first", TREE, "quoted", "second", "small-chore"
    ]


def test_a_ticket_waiting_on_a_proposal_is_blocked_until_the_ruling_lands_as_done(tracker: Path) -> None:
    assert load(tracker)["uses-fast-suite"].status == "blocked"
    ticket(tracker / "faster-suite.md", "open", parent=TREE, blocked_by=["second"])
    assert load(tracker)["uses-fast-suite"].status == "blocked"
    ticket(tracker / "faster-suite.md", "review", parent=TREE)  # built, waiting for the ruling: still not done
    assert load(tracker)["uses-fast-suite"].status == "blocked"
    ticket(tracker / "faster-suite.md", "done", parent=TREE)
    assert load(tracker)["uses-fast-suite"].status == "open"


def test_a_ticket_of_one_tree_waits_on_a_ticket_of_no_tree(tracker: Path) -> None:
    assert load(tracker)["needs-chore"].status == "blocked"
    ticket(tracker / "small-chore.md", "done")
    assert load(tracker)["needs-chore"].status == "open"


def test_a_status_the_tracker_does_not_know_is_refused_with_the_file_and_the_line(tracker: Path) -> None:
    ticket(tracker / "second.md", "opne", parent=TREE)
    with pytest.raises(tracker_module.Refused, match=r"second\.md:2: `status: opne` is no ticket status"):
        load(tracker)


def test_a_gh_reference_that_is_not_owner_repo_number_is_refused_with_the_file_and_the_line(tracker: Path) -> None:
    ticket(tracker / "built.md", "review", parent=TREE, gh=["https-github-com/acme#317x"])
    with pytest.raises(tracker_module.Refused, match=r"built\.md:\d+: `gh: .*` is no reference"):
        load(tracker)


def test_a_ticket_with_no_parent_and_no_child_is_in_no_tree(tracker: Path) -> None:
    read = load(tracker)
    assert read[TREE].tree == TREE and read["second"].tree == TREE
    assert read["small-chore"].tree == "" and read["loose-idea"].tree == ""


def test_a_tree_runs_to_the_top_level_ticket_however_deep_the_ancestry_is(tmp_path: Path) -> None:
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "top.md", "open")
    ticket(root / "middle.md", "open", parent="top")
    ticket(root / "leaf.md", "open", parent="middle")
    assert {slug: t.tree for slug, t in load(root).items()} == {"top": "top", "middle": "top", "leaf": "top"}


# ---- graphs ---------------------------------------------------------------


def test_a_rejected_proposal_unblocks_what_waited_on_it_and_leaves_the_graph(tracker: Path) -> None:
    (tracker / "faster-suite.md").unlink()
    ticket(tracker / "uses-fast-suite.md", "open", parent=TREE)  # the edge onto it goes with it
    read = load(tracker)
    assert read["uses-fast-suite"].status == "open"
    assert read["uses-fast-suite"].blocked_by == []
    graph = tree_graph(list(read.values()), TREE)
    # uses-fast-suite waits on nothing now and nothing waits on it: a row, not a node
    assert "uses fast suite" not in graph
    # after-first still waits on the done first, which is drawn as its dashed context
    assert 'first"]:::ghost' in graph
    assert "T_f_first --> T_f_after_first" in graph
    assert "uses fast suite" not in str(board_graph(list(read.values())))


def test_a_tree_whose_tickets_wait_on_nothing_has_no_graph(tmp_path: Path) -> None:
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "solo.md", "open")
    ticket(root / "only.md", "open", parent="solo")
    read = list(load(root).values())
    assert tree_graph(read, "solo") is None
    assert board_graph(read) is None
    page = render_page("demo", read, log="", stamp="s", stamp_src="s.js")
    assert "nothing in solo waits on anything" in page
    assert "nothing waits on anything" in page


def test_a_proposed_ticket_is_a_node_in_its_own_class_once_something_waits_on_it(tracker: Path) -> None:
    graph = tree_graph(list(load(tracker).values()), TREE)
    assert 'faster suite"]:::proposed' in graph
    assert "T_f_second --> T_f_faster_suite" in graph and "T_f_faster_suite --> T_f_uses_fast_suite" in graph
    assert 'click T_f_faster_suite "#t-faster-suite"' in graph


def test_the_whole_tracker_graph_is_parts_per_tree_with_edges_naming_both_ends(tracker: Path) -> None:
    read = list(load(tracker).values())
    parts = board_graph(read)
    assert [f["name"] for f in parts["trees"]] == [ALONE, TREE]
    ids = {f["name"]: [n["id"] for n in f["nodes"]] for f in parts["trees"]}
    assert ids[TREE] == ["T_b_after_first", "T_b_built", "T_b_faster_suite", "T_b_first",
                         "T_b_needs_chore", "T_b_second", "T_b_uses_fast_suite"]
    assert ids[ALONE] == ["T_b_loose_idea", "T_b_quoted", "T_b_small_chore"]
    edges = {(e["a"], e["from"], e["b"], e["to"]) for e in parts["edges"]}
    assert (TREE, "T_b_second", ALONE, "T_b_loose_idea") in edges
    assert (ALONE, "T_b_small_chore", TREE, "T_b_needs_chore") in edges
    assert (TREE, "T_b_first", ALONE, "T_b_quoted") in edges
    lines = "\n".join(line for f in parts["trees"] for n in f["nodes"] for line in n["lines"])
    assert 'loose idea"]:::proposed' in lines
    assert 'first"]:::ghost' in lines
    # a raw double quote in a label ends mermaid's string and breaks the whole flowchart
    assert 'T_b_quoted["○ Say ”no limit” plainly"]' in lines
    assert (TREE, "T_b_first", TREE, "T_b_after_first") in edges


def test_a_done_ticket_another_tree_waits_on_is_drawn_as_its_context(tmp_path: Path) -> None:
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "base.md", "open")
    ticket(root / "storage.md", "done", parent="base")
    ticket(root / "cleanup.md", "proposed", parent="base")
    ticket(root / "top.md", "open")
    ticket(root / "uses-storage.md", "open", parent="top", blocked_by=["storage"])
    read = list(load(root).values())
    assert tree_graph(read, "base") is None  # nothing within base waits on anything
    parts = board_graph(read)
    lines = "\n".join(line for f in parts["trees"] for n in f["nodes"] for line in n["lines"])
    assert 'storage"]:::ghost' in lines
    assert "cleanup" not in lines
    assert [(e["a"], e["b"], e["line"]) for e in parts["edges"]] == [("base", "top", "  T_b_storage --> T_b_uses_storage")]


# ---- page -----------------------------------------------------------------


def test_the_page_groups_rows_by_state_needs_me_first_and_done_folded(tracker: Path) -> None:
    page = page_of(tracker)
    assert re.findall(r'id="grp-(\w+)"', page) == ["needs", "open", "blocked", "proposed", "done", "log"]
    assert '<h2>proposed <span class="n">2</span></h2>' in page  # faster-suite and the loose idea
    assert '<details class="grp" id="grp-done" data-state="done"><summary>' in page
    assert '<details class="grp" id="grp-open" data-state="open" open>' in page
    # a build waiting for the ruling is the user's to act on: it sits in needs me
    assert '<details class="grp" id="grp-needs" data-state="needs" open><summary><h2>needs me <span class="n">1</span>' in page
    assert rows_in(page, "needs") == {"t-built"}
    assert 'class="ticket row-review" id="t-built"' in page
    assert f'class="ticket row-proposed" id="t-faster-suite" data-tree="{TREE}" data-slug="faster-suite"' in page
    assert 'id="t-faster-suite"' in page and 'class="badge proposed"' not in page  # the group says the status; a row does not repeat it


def test_a_tree_chip_carries_the_counts_as_its_tooltip(tracker: Path) -> None:
    page = page_of(tracker)
    assert (
        f'<button class="treechip" data-tree="{TREE}" title="1/8 done · 3 open · 1 review · 2 blocked · 1 proposed">'
        f'<i class="dot"></i>{TREE} <span class="dim">1/8</span></button>' in page
    )
    assert f'{ALONE} <span class="dim">0/3</span>' in page


def test_a_tree_chip_dots_when_any_of_its_tickets_waits_on_the_user(tmp_path: Path) -> None:
    """The dot reads the needs-me group, so a ticket stopped on a question lights it as much as a
    build in review does; the counts beside it already say how many tickets the tree has."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    only = root / "only.md"
    ticket(root / "solo.md", "done")
    ticket(only, "review", parent="solo")
    page = render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")
    assert '<button class="treechip" data-tree="solo" title="1/2 done · 1 review"><i class="dot"></i>solo' in page

    ticket(only, "claimed", parent="solo")  # the case a status alone cannot tell: in hand, and waiting on an answer
    only.write_text(only.read_text() + "\n## Questions\n\n- [D1] **Per bank or per file?** Neither is free.\n")
    page = render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")
    assert '<button class="treechip" data-tree="solo" title="1/2 done · 1 claimed"><i class="dot"></i>solo' in page

    ticket(only, "claimed", parent="solo")  # the same ticket with nothing asked of the user
    page = render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")
    assert '<button class="treechip" data-tree="solo" title="1/2 done · 1 claimed">solo' in page


def test_a_gh_reference_is_a_link_on_the_row_and_in_its_search_text(tracker: Path) -> None:
    ticket(tracker / "quoted.md", "open", blocked_by=["first"], gh=["acme/coding#137"], name='Say "no limit" plainly')
    page = page_of(tracker)
    assert (
        '<a class="gh unknown" href="https://github.com/acme/backend/issues/317" target="_blank" '
        'onclick="event.stopPropagation()" data-tip="A pull request or issue this ticket names, on GitHub.">acme/backend#317</a>'
        '<a class="gh unknown" href="https://github.com/acme/helix/issues/412"' in page
    )
    assert 'href="https://github.com/acme/coding/issues/137"' in page
    searches = dict(re.findall(r'id="([\w-]+)" data-tree="[\w-]*" data-slug="[^"]+" data-search="([^"]*)"', page))
    assert "acme/backend#317 acme/helix#412" in searches["t-built"]
    assert "acme/coding#137" in searches["t-quoted"]


def test_a_row_carries_what_the_page_script_matches_against_the_graphs(tracker: Path) -> None:
    """The script hides rows by the chip's raw tree name, filters on data-search with
    String.includes, and marks the node T_f_<slug> in the graph container of the row's tree."""
    read = list(load(tracker).values())
    page = render_page("demo", read, log="", stamp="s", stamp_src="s.js")
    in_tree = [t for t in read if t.tree == TREE]
    assert page.count(f'data-tree="{TREE}"') == 1 + len(in_tree) + 1  # chip, rows, graph container
    rows = re.findall(r'<details class="ticket row-\w+" id="([\w-]+)" data-tree="([\w-]*)" data-slug="([^"]+)" data-search="([^"]*)"', page)
    assert len(rows) == len(read)
    searches = {row_id: html.unescape(search) for row_id, _, _, search in rows}  # the script reads the attribute unescaped
    assert searches["t-faster-suite"] == "faster-suite faster suite what to build cut from the worker's closing comment on first: the suite is slow."
    assert all(s == s.lower() and "<" not in s for s in searches.values())
    graph = re.search(rf'<div class="g" data-tree="{TREE}" hidden><pre class="mermaid" data-key="g:{TREE}">(.*?)</pre>', page, re.S).group(1)
    for row_id, tree, slug, _ in rows:
        if tree == TREE and slug in ("second", "faster-suite", "uses-fast-suite", "after-first", "first", "built"):
            assert f"T_f_{slug.replace('-', '_')}[" in graph, row_id
    assert '<div class="g" data-tree="*" hidden><pre class="mermaid" data-key="g:*"></pre>' in page
    assert '"id": "T_b_quoted"' in page


def test_the_side_columns_graph_is_a_preview_of_one_that_opens_at_full_size(tracker: Path) -> None:
    """The ids the page's script and the browser checks address the full size views by, and the one
    markup both of those views wear (board.GRAPH_VIEW), so the overlay over the board and the window
    of its own cannot drift apart. What either draws, and what a click on it does, is the browser's
    to say (test_board_layout.py)."""
    page = page_of(tracker)
    for opener in ("gopen", "gwinopen", "gwinfull", "gclose"):  # from the preview, and to the window
        assert f'id="{opener}"' in page, opener
    for view in (board.OVERLAY, board.GRAPH_WINDOW):
        assert re.findall(r'data-gmode="(\w+)"', view) == ["tree", "all"]
        assert view.count('<div class="gsvg">') == 1
    assert board.OVERLAY in page, "the overlay wears markup of its own"
    assert json.dumps(board.GRAPH_WINDOW).replace("</", "<\\/") in page, "the window is built from markup of its own"


def test_a_row_links_its_review_page(tracker: Path) -> None:
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "second.html").write_text("<html>")
    (dv / "quoted.html").write_text("<html>")
    page = page_of(tracker)
    assert f'href="file://{dv / "second.html"}"' in page
    assert f'href="file://{dv / "quoted.html"}"' in page
    assert page.count('class="rp"') == 2  # once per row (the spec's Decisions), on the name's line


def test_a_row_links_its_review_page_on_the_address_diffview_serves(tracker: Path, stub_diffview: Path) -> None:
    """A page opened as a file is read-only, so a review that starts from the board has to land on
    the served one, at the address diffview names for that directory of pages."""
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "second.html").write_text("<html>")
    (dv / "quoted.html").write_text("<html>")
    diffviews = serve_diffviews(dv)
    assert Path(f"{stub_diffview}.args").read_text().split() == ["--serve", str(dv)]
    page = render_page("demo", load_tickets(Roots(tracker, []), diffviews), log="", stamp="s", stamp_src="s.js")
    assert f'href="{STUB_ADDRESS}/second.html"' in page
    assert f'href="{STUB_ADDRESS}/quoted.html"' in page


def test_a_review_page_nothing_serves_is_linked_as_the_file_it_is(tracker: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine without diffview has the pages but no server for them."""
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "second.html").write_text("<html>")
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools"))
    assert serve_diffviews(dv).link(dv, "second.html") == f"file://{dv / 'second.html'}"


def test_the_graph_draws_every_status_in_the_house_ink(tracker: Path) -> None:
    """The graph's colours are baked into the SVG by mermaid, so the page hands it one classDef per
    status, each mixed from the house tokens in the scheme on show."""
    page = page_of(tracker)
    classes = re.search(r"const cls = \{(.*?)\s*\};", page, re.S).group(1)
    read = set(re.findall(r'c(?:\.|\[")([\w-]+)', classes))
    for status in [*STATUS_SYMBOL, "ghost"]:
        assert re.search(rf"\b{status}: \[", classes), f"the graph draws no {status} node"
    assert read, "the classDefs name no token"
    for token in read:
        assert f"--{token}: light-dark(" in page, f"the graph reads --{token}, which the page does not declare"
    assert not re.search(r":\s*\[\s*[\"']?#", classes), "a status is drawn in a literal colour, not the house ink"


# ---- checkouts ------------------------------------------------------------


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(cwd), *args],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.fixture
def repo(tracker: Path) -> Path:
    """The tracker committed on main, and a worktree on the tree's parent ticket's branch beside the repo."""
    repo = tracker.parent.parent
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tracker")
    git(repo, "worktree", "add", "-q", str(repo.parent / "wt"), "-b", TREE)
    return repo


def test_a_ticket_a_branch_added_is_shown_and_one_it_inherited_is_not(repo: Path, tracker: Path) -> None:
    wt = repo.parent / "wt"
    # main retires a chore after the branch was cut; the branch's inherited copy must not bring it back
    git(repo, "rm", "-q", "agent/tickets/small-chore.md")
    git(repo, "rm", "-q", "agent/tickets/needs-chore.md")  # its edge would dangle
    git(repo, "commit", "-q", "-m", "small-chore: done")
    branch_root = wt / "agent" / "tickets"
    ticket(branch_root / "filed-on-branch.md", "open")  # untracked on the branch
    ticket(branch_root / "loose-idea.md", "open", blocked_by=["second"])  # changed on the branch; main's copy wins
    ticket(branch_root / "second.md", "claimed", parent=TREE)  # in the tree the branch is named after: its copy wins
    roots = tracker_roots(tracker)
    assert roots.main == tracker
    assert roots.repo == repo
    assert roots.branches == [(TREE, branch_root)]
    read = {t.slug: t for t in load_tickets(roots, Diffviews(tracker.parent / "diffviews", None))}
    assert {slug: t.source for slug, t in read.items() if t.source or slug in ("loose-idea", "quoted")} == {
        "loose-idea": None, "quoted": None, "filed-on-branch": TREE,
    }
    assert read["loose-idea"].status == "proposed"  # main's copy, which the branch does not outvote
    assert read["second"].status == "claimed"  # the tree is read from the worktree the branch is named after
    page = render_page("demo", list(read.values()), log="", stamp="s", stamp_src="s.js")
    assert f'data-tip="Filed on branch {TREE}, not on the main branch.">on {TREE}</span>' in page


def test_a_row_copies_the_path_of_the_file_the_board_read(repo: Path, tracker: Path) -> None:
    """A tree in flight is read from its worktree and a ticket filed on a branch exists only there,
    so the main checkout's copy is the wrong path to hand to a session."""
    branch_root = repo.parent / "wt" / "agent" / "tickets"
    ticket(branch_root / "filed-on-branch.md", "open")
    roots = tracker_roots(tracker)
    read = load_tickets(roots, Diffviews(tracker.parent / "diffviews", None))
    page = render_page("demo", read, log="", stamp="s", stamp_src="s.js")
    paths = dict(re.findall(r'<details class="ticket row-\w+" id="([\w-]+)" [^>]*data-path="([^"]*)"', page))
    assert paths["t-second"] == str(branch_root / "second.md")
    assert paths["t-filed-on-branch"] == str(branch_root / "filed-on-branch.md")
    assert paths["t-quoted"] == str(tracker / "quoted.md")


def test_a_worktree_whose_tracker_no_reader_can_read_leaves_the_render_the_main_checkouts(
    repo: Path, tracker: Path, capsys: pytest.CaptureFixture,
) -> None:
    """The main checkout is the tracker; a branch is a source the render can do without, and the
    refusal is printed whole so the file and the line are there to act on."""
    branch_root = repo.parent / "wt" / "agent" / "tickets"
    (branch_root / "second.md").write_text("---\nstatus: claimed\ntype: grilling\npriority: 2\nsize: S\n---\n\n# Second\n\n## Brief\n")
    read = {t.slug: t for t in load_tickets(tracker_roots(tracker), Diffviews(tracker.parent / "diffviews", None))}
    assert read["second"].status == "open", "the main checkout's copy"
    said = capsys.readouterr().err
    assert f"{TREE} holds a tracker no reader can read" in said
    assert "second.md:3: `type` is dropped" in said


def test_the_watcher_notices_a_page_server_leaving_its_pages_unserved(repo: Path, tracker: Path) -> None:
    """A page server exits a while after the last page closes, rewriting the marker it left beside
    the pages; noticing that is what gets the next render, which is what serves them again."""
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "quoted.html").write_text("<html>")
    marker = dv / ".serve.json"
    marker.write_text('{"port": 54321, "pid": 1234}')  # what a live server leaves beside the pages
    roots = tracker_roots(tracker)
    before = tracker_snapshot(roots, repo)
    marker.write_text('{"port": 54321}')  # the pid dropped, as a server does on its way out
    assert tracker_snapshot(roots, repo) != before


def test_a_worktree_on_a_landed_branch_is_ignored(repo: Path, tracker: Path) -> None:
    wt = repo.parent / "wt"
    ticket(wt / "agent" / "tickets" / "second.md", "done", parent=TREE)
    git(wt, "commit", "-q", "-am", "second landed")
    assert tracker_roots(tracker).branches == [(TREE, wt / "agent" / "tickets")]
    git(repo, "merge", "-q", "--no-ff", "-m", "feat-a: landed", TREE)
    assert tracker_roots(tracker).branches == []


def test_a_tracker_the_main_checkout_does_not_have_yet_renders_from_the_worktree(repo: Path, tracker: Path) -> None:
    git(repo, "rm", "-q", "-r", "agent/tickets")
    git(repo, "commit", "-q", "-m", "tracker moved out")
    roots = tracker_roots(repo.parent / "wt" / "agent" / "tickets")  # run from the worktree, the only tracker there is
    assert not roots.main.is_dir() and roots.branches
    read = load_tickets(roots, Diffviews(roots.main.parent / "diffviews", None))
    # the tree the branch is named after is read from the worktree; the tickets outside it the
    # branch merely inherited are main's to show, and main has retired them
    assert {t.slug for t in read} == {TREE, "first", "second", "faster-suite", "uses-fast-suite",
                                      "after-first", "needs-chore", "built"}
    assert all(t.source is None for t in read), "an override is the tracker's own copy, not a branch's addition"


def test_the_stamp_changes_with_a_tickets_source(tracker: Path) -> None:
    read = list(load(tracker).values())
    before = content_stamp("demo", read, "")
    read[0].source = "some-branch"
    assert content_stamp("demo", read, "") != before


# ---- what the root holds --------------------------------------------------


def test_markdown_at_the_tracker_root_that_no_reader_can_read_is_refused_by_the_render(
    repo: Path, tracker: Path, tmp_path: Path,
) -> None:
    """The tracker root holds tickets and nothing else: a note left beside them is refused where it
    sits, rather than rendered as half a row."""
    (tracker / "needs-human.md").write_text("# Needs human\n\n- rule on loose-idea :: built while proposed\n")
    with pytest.raises(tracker_module.Refused, match=r"needs-human\.md:1: no frontmatter"):
        render(tracker_roots(tracker), repo, tmp_path / "out" / "board.html")


def test_an_unblocked_proposal_is_claimable_and_still_waits_for_its_ruling(tracker: Path) -> None:
    """The live case: a proposal an agent filed with nothing blocking it (`/mx:tracker`)."""
    ticket(tracker / "render-check.md", "proposed", parent=TREE)
    read = load(tracker)
    assert read["render-check"].status == "proposed"
    assert read["render-check"].blocked_by == []
    page = render_page("demo", list(read.values()), log="", stamp="s", stamp_src="s.js")
    proposed = page.split('id="grp-proposed"')[1].split('class="grp" id="grp-')[0]
    assert 'id="t-render-check"' in proposed


# ---- rows ------------------------------------------------------------------
# The marks' words come from the spec, not from board.py: these literals are the spec's own
# ("The ticket file": XS under 15 min ... XL several sessions; priority 1 to 5 named now, next,
# soon, later, someday; "The board": what the row asks is one of four words).
SIZE_WORDS = {"XS": ("15 min", "under 15 min"), "S": ("20 min", "about 20 min"), "M": ("1 h", "about an hour"),
              "L": ("half a day", "half a day"), "XL": ("several sessions", "several sessions")}
PRIORITY_WORDS = {1: "now", 2: "next", 3: "soon", 4: "later", 5: "someday"}
ASK_WORDS = {"review": "to rule on", "answer": "your answer", "session": "with you", "build": "build"}
MARKS = {"ftag", "num", "asks", "time", "pri", "chip", "rp", "gh", "src", "qtag", "qhead", "copier"}
# What a row holds that is not a mark: the boxes the marks sit in, and the prose a reader reads
# rather than decodes, the ticket's own name among it (its hover words are the name in full, for a
# row too narrow to show it). Everything else on a row explains itself, which is what makes the
# check below catch a mark a later slice adds rather than skip it.
NOT_MARKS = {"main", "titleline", "title", "meta", "chips", "brief", "qs", "q", "clip"}


def rows_of(page: str) -> dict[str, str]:
    """Each ticket row's markup, by row id, in the order the page lists them: to the `</details>`
    that closes the row, counting in the one it holds itself (the comments, folded)."""
    found = {}
    for row in re.finditer(r'<details class="ticket [^"]*" id="([\w-]+)"', page):
        depth = 0
        for tag in re.finditer(r"<details\b|</details>", page[row.start():]):
            depth += 1 if tag.group().startswith("<details") else -1
            if depth == 0:
                found[row.group(1)] = page[row.end(): row.start() + tag.start()]
                break
    return found


def summary_of(row: str) -> str:
    """What a row shows without being opened: its name, its marks and its open questions."""
    return row.split("</summary>", 1)[0]


def body_of(row: str) -> str:
    """What it shows opened: the blocks the ticket reads as."""
    return row.split("</summary>", 1)[1]


class Marks(HTMLParser):
    """Every element of a row that carries a class, with the words it shows and the words it says
    on hover. A mark that clips its text holds it in an inner element, so the text of a mark is
    everything under it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.open: list[tuple[str, list]] = []
        self.found: list[list] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        got = dict(attrs)
        entry = [(got.get("class") or "").split()[0] if got.get("class") else "", [], got]
        self.open.append((tag, entry))
        self.found.append(entry)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i][0] == tag:
                del self.open[i:]
                return

    def handle_data(self, data: str) -> None:
        for _, entry in self.open:
            entry[1].append(data)


def marks_on(row: str) -> list[tuple[str, str, str | None]]:
    """(mark, the words it shows, the words it says on hover) for every mark on a row."""
    return [(mark, "".join(text).strip(), got.get("data-tip")) for mark, text, got in elements_of(row)]


def elements_of(markup: str) -> list[list]:
    """[first class, the text under it, its attributes] for every element, in document order."""
    reader = Marks()
    reader.feed(markup)
    return reader.found


def tips_on(row: str) -> dict[str, str]:
    """The hover words of each mark on a row, by mark."""
    return {mark: tip for mark, _, tip in marks_on(row) if mark in MARKS and tip}


def test_a_rows_marks_are_read_from_the_ticket_file(tmp_path: Path) -> None:
    """The spec's Decisions on the ticket file: priority and size in frontmatter, the H1 as the
    short name, the brief from `## Brief`. A brief with nothing under it leaves the row without
    that mark rather than inventing one; the priority and the size every ticket declares, so no row
    is ever without those."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "map-columns.md", "open", priority=1, size="M",
           name="Map columns once per bank", brief="You tell the importer once which column holds the `date`.")
    ticket(root / "silent.md", "open")
    read = load(root)
    mapped, silent = read["map-columns"], read["silent"]
    assert (mapped.priority, mapped.size) == (1, "M")
    assert mapped.title == "Map columns once per bank", "the H1 is the short name"
    assert mapped.brief == "You tell the importer once which column holds the <code>date</code>."
    assert silent.brief == ""
    page = render_page("demo", list(read.values()), log="", stamp="s", stamp_src="s.js")
    rows = rows_of(page)
    shown = {mark: text for mark, text, _ in marks_on(rows["t-map-columns"]) if mark in MARKS}
    assert shown["time"] == "1 h" and shown["pri"] == "p1 now"
    assert "Map columns once per bank" in rows["t-map-columns"]
    assert "which column holds the <code>date</code>" in rows["t-map-columns"]
    assert {mark for mark, _, _ in marks_on(rows["t-silent"])}.isdisjoint({"brief"})
    assert "## Brief" not in page and "brief" not in labels_of(rows["t-map-columns"]), "the brief has one home, and it is the row"
    # the brief is searchable, since the filter is how a reader narrows to a word they remember
    assert "which column holds the date" in html.unescape(
        re.search(r'id="t-map-columns" [^>]*data-search="([^"]*)"', page).group(1)
    )


def test_a_priority_or_size_the_tracker_does_not_know_is_refused_with_the_file_and_the_line(tracker: Path) -> None:
    ticket(tracker / "second.md", "open", parent=TREE, priority=9)
    with pytest.raises(tracker_module.Refused, match=r"second\.md:\d+: `priority: 9` is none of"):
        load(tracker)
    ticket(tracker / "second.md", "open", parent=TREE, size="HUGE")
    with pytest.raises(tracker_module.Refused, match=r"second\.md:\d+: `size: HUGE` is none of"):
        load(tracker)


def test_every_size_and_priority_shows_the_word_the_spec_gives_it(tmp_path: Path) -> None:
    """Five sizes and five priorities, each on a row of its own: the words the user reads are the
    spec's, and the tip's own definition of a mark stays in step with the word beside it."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    for i, size in enumerate(SIZE_WORDS, start=1):
        ticket(root / f"sized-{i}.md", "open", size=size, priority=i)
    page = render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")
    rows = rows_of(page)
    for i, (size, (word, means)) in enumerate(SIZE_WORDS.items(), start=1):
        row = rows[f"t-sized-{i}"]
        shown = {mark: text for mark, text, _ in marks_on(row) if mark in MARKS}
        assert shown["time"] == word, f"{size} reads {shown['time']!r}"
        assert shown["pri"] == f"p{i} {PRIORITY_WORDS[i]}"
        tips = tips_on(row)
        assert f"{size} {means}" in tips["time"], f"the time's words leave {size} out"
        assert f"p{i} {PRIORITY_WORDS[i]}:" in tips["pri"], f"the priority's words leave p{i} out"


def columns_for(page: str, selector: str) -> dict[str, str]:
    """The width in characters the page gives each of a row's fixed columns, for the whole board
    (`:root`) or for one group; empty when that selector narrows none of them."""
    block = re.search(rf"{re.escape(selector)} \{{\n((?:    --col-.*\n)+)  \}}", page)
    return dict(re.findall(r"--col-(\w+): calc\((\d+) \*", block.group(1))) if block else {}


def test_a_rows_fixed_columns_are_as_wide_as_the_marks_that_land_in_them(tmp_path: Path) -> None:
    """The name and the brief take what the row has spare, so a column is measured from the marks:
    the closed vocabularies for what a row asks, the time and the priority, the tracker's own names
    and references for the feature tag and the blockers, and each group's own three, since a group
    of quick unblocked tickets has no use for the width an XL one needs."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "ledger.md", "open", priority=1, size="S")
    ticket(root / "quick.md", "review", parent="ledger", priority=2, size="S")
    ticket(root / "long-haul.md", "open", parent="ledger", priority=5, size="XL", blocked_by=["quick"])
    ticket(root / "waits-on-the-haul.md", "open", priority=3, size="M", blocked_by=["long-haul"])
    page = render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")
    assert columns_for(page, ":root") == {
        "ftag": str(len("ledger")),  # the one tree's slug
        "num": str(len("waits-on-the-h")),  # the longest slug, capped at the column's width
        "asks": str(len("your answer")),  # the widest of the spec's four words
        "time": str(len("several sessions")),
        "pri": str(len("p5 someday")),
        "chips": str(len("long-haul")),
    }
    # the group whose only ticket is an S at p2 with nothing waiting on it leaves the rest of that
    # width to the name and the brief
    assert columns_for(page, "#grp-needs") == {"time": str(len("20 min")), "pri": str(len("p2 next")), "chips": "0"}
    # the group that holds the XL ticket keeps the board's width for every one of the three
    # the group holding the XL ticket and the widest reference narrows none of the three
    narrowed = columns_for(page, "#grp-blocked")
    assert narrowed == {}, f"the blocked group narrows {sorted(narrowed)}, though its rows are the widest of each"


def test_rows_sort_by_priority_then_by_the_users_time_within_a_group(tmp_path: Path) -> None:
    """The spec's Decision: the user reads a group top down, the soonest and shortest first."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "slow-p1.md", "open", priority=1, size="L")
    ticket(root / "quick-p2.md", "open", priority=2, size="XS")
    ticket(root / "quick-p1.md", "open", priority=1, size="XS")
    ticket(root / "slowest-p5.md", "open", priority=5, size="XL")
    ticket(root / "middling-p1.md", "open", priority=1, size="M")
    ticket(root / "a-chore.md", "open", priority=3, size="S", name="A chore")
    page = render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")
    assert list(rows_of(page)) == [
        "t-quick-p1", "t-middling-p1", "t-slow-p1", "t-quick-p2", "t-a-chore", "t-slowest-p5",
    ]


def test_the_stamp_the_open_tab_polls_moves_when_a_link_changes_state(tracker: Path) -> None:
    """A merge on GitHub moves nothing under the tracker, and the open tab has to hear about it."""
    read = list(load(tracker).values())
    stamps = [
        content_stamp("demo", read, "", gh)
        for gh in (github.NOTHING,
                   github.Answer({"acme/backend#317": "pr-open"}),
                   github.Answer({"acme/backend#317": "pr-merged"}),
                   github.Answer({}, "GitHub did not answer"))
    ]
    assert len(set(stamps)) == len(stamps)


def test_the_stamp_the_open_tab_polls_moves_when_a_ticket_is_reprioritised(tracker: Path) -> None:
    """An edit the page shows but the ticket's status does not: the open tab reloads on it or it
    never arrives."""
    before = content_stamp("demo", list(load(tracker).values()), "")
    ticket(tracker / "second.md", "open", parent=TREE, priority=1, size="XS", brief="Why it matters, cold.")
    assert content_stamp("demo", list(load(tracker).values()), "") != before


def test_the_stamp_the_open_tab_polls_moves_when_the_session_rewrites_the_briefing(tracker: Path) -> None:
    """The briefing is the other thing on the page that moves with no file under the tracker moving,
    and the open tab polls the stamp: an unmoved stamp is a briefing nobody ever reads."""
    read = list(load(tracker).values())
    when = datetime.fromisoformat("2026-09-21T09:30:00+02:00")
    stamps = [
        content_stamp("demo", read, "", github.NOTHING, said)
        for said in (None,
                     Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 0),
                     Briefing("One build waits on your ruling.", when, "abc-123", when, when, 1),
                     Briefing("Two builds wait on your ruling.", when + timedelta(hours=1), "abc-123", when, when, 1))
    ]
    assert len(set(stamps)) == len(stamps)


def test_what_each_row_asks_of_the_user_comes_from_its_ticket_file(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The spec's four words, each against the fixture ticket that earns it: a build in review asks
    for a ruling; a ticket the user is in the loop for asks for the session the user sits in,
    whether or not its question is written down; a ticket a worker takes is stopped by an open
    question of its own and asks for the answer; one with no question asks nothing of the user."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    rows = rows_of(out.read_text())
    expected = {
        "t-map-columns": "review",  # status: review, a build waiting on a ruling
        "t-speed-up-tests": "review",
        "t-retire-legacy-exporter": "session",  # needs-user, and its open question is that session
        "t-view-list-shape": "session",
        "t-staging-credentials": "session",  # needs-user, and its one question is ruled
        "t-read-the-bank-formats": "build",  # nothing open on it, and no worker is kept from it
        "t-flaky-upload-test": "answer",  # a build stopped on a question of its own
        "t-pick-a-date-library": "answer",  # a worker's ticket, stopped on a question
        "t-view-storage": "answer",
        "t-parse-rows": "build",  # no question, not in review, and the user is not in the loop
    }
    for row_id, kind in expected.items():
        shown = {mark: text for mark, text, _ in marks_on(rows[row_id]) if mark in MARKS}
        assert shown["asks"] == ASK_WORDS[kind], f"{row_id} asks {shown['asks']!r}, not {ASK_WORDS[kind]!r}"
        assert f'class="asks a-{kind}"' in rows[row_id]


def test_every_mark_on_a_row_says_in_words_what_it_means(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The spec's reviewed Property "Every mark explains itself", at the seam its Testing Decisions
    names for rows and marks: the demo tracker in, the page's rows out. Every mark that carries
    text says what it means, and says it about itself; that the words then paint on hover is the
    layout check's (test_board_layout.py)."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    page = out.read_text()
    seen = set()
    for row_id, row in rows_of(page).items():
        for mark, text, tip in marks_on(summary_of(row)):
            if mark in NOT_MARKS or not mark or not text:
                continue  # the summary itself, and the code spans markdown leaves inside prose
            assert mark in MARKS, f"{row_id}: {mark!r} is a mark this check has never seen, or a box to exempt"
            seen.add(mark)
            assert tip and len(tip.split()) >= 4, f"{row_id}: the {mark} mark {text!r} says {tip!r}"
    assert seen == MARKS - {"src"}, "no ticket in the fixture was filed on a branch"
    # each mark's words are about that mark: the time's say whose time it is, the priority's who set it
    row = rows_of(page)["t-map-columns"]
    tips = tips_on(row)
    assert "never the agent's" in tips["time"] and "priority" not in tips["time"]
    assert "an agent's reading" in tips["pri"] and "Your time" not in tips["pri"]
    assert "review page" in tips["rp"] and "GitHub" in tips["gh"]
    assert str(demo.root / "map-columns.md") in tips["num"], "a copy button shows what it copies"
    assert "parent ticket" in tips["ftag"]
    # a blocker says which ticket it waits on and whether that one is done (spec, The board)
    assert 'data-tip="Waits on parse-rows, done.">parse-rows</a>' in page
    assert 'data-tip="Waits on map-columns, not done yet.">map-columns</a>' in page
    assert 'data-tip="Waits on commit-import, not done yet.">commit-import</a>' in page


# ---- questions and the needs-me group -------------------------------------
# The spec's Decisions on `## Questions` and on the board: every question lives on its ticket,
# shows under its row in the one needs-me group while that row is folded, and is copyable one at a
# time, per ticket, or all at once, each button saying what it will copy.

def copiers(markup: str) -> list[tuple[str, str, str, str]]:
    """(which button, what it copies, what the page says once it has, the words it shows) for every
    copy button in `markup`: the page hands the click what the element carries."""
    return [
        (got["class"].split()[-1], got["data-copy"], got["data-copied"], got["data-tip"])
        for _, _, got in elements_of(markup) if "data-copy" in got
    ]


def questions_on(row: str) -> list[tuple[str, str]]:
    """(tag, headline) of every question a row lists, in the order it lists them."""
    marks = marks_on(row)
    tags = [text for mark, text, _ in marks if mark == "qtag"]
    return list(zip(tags, [text for mark, text, _ in marks if mark == "qhead"], strict=True))


def test_a_needs_me_row_lists_the_questions_its_ticket_file_asks_and_no_ruled_one(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The fixture's build stopped on two questions, of which a `Ruled` line answered one."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    row = rows_of(out.read_text())["t-flaky-upload-test"]
    assert questions_on(row) == [("D1", "Retry the upload, or fake the clock?")], "D2 is ruled, and a ruled question is answered"
    written = f"{demo.root / 'flaky-upload-test.md'}\n- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing."
    assert [(which, text) for which, text, _, _ in copiers(summary_of(row))] == [("qcopy", written)], "one question needs no copy-all beside it"
    # the ticket with three of them has one, and it copies all three under the one path
    three = copiers(summary_of(rows_of(out.read_text())["t-map-columns"]))
    assert [which for which, _, _, _ in three] == ["qcopy", "qcopy", "qcopy", "qall"]
    assert three[-1][1].splitlines() == [str(demo.root / "map-columns.md")] + [
        line for which, text, _, _ in three[:-1] for line in text.splitlines()[1:]
    ]


def test_a_build_in_review_shows_the_questions_and_the_closing_comment_on_its_ticket_branch(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """Both live on the branch until the merge, and the checkout's copy of the ticket has neither."""
    checkout = (demo.root / "map-columns.md").read_text()
    assert "## Questions" not in checkout and "## Comments" not in checkout
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    row = rows_of(out.read_text())["t-map-columns"]
    assert [tag for tag, _ in questions_on(row)] == ["D1", "D2", "D3"]
    assert "Remember the mapping per bank or per file name?" in row
    assert "<code>~/.config/ledger/mappings.toml</code>" in row, "a headline's own code and emphasis render on the row"
    assert "The mapping step is built and remembers a bank" in row, "the closing comment, folded under the row"
    # the row cuts a headline to its column, so the question's own words are what the hover carries
    tips = [tip for mark, _, tip in marks_on(row) if mark == "qhead"]
    assert tips[0].startswith("Remember the mapping per bank or per file name?")
    assert "Per bank asks one more question on the first import" in tips[0], "the detail the row has no room for"
    assert "[D4]" not in "".join(text for _, text, _, _ in copiers(row)), "the tags a closing comment carries are not questions"


BRANCH = "ticket/map-columns"
BUILT = """
## Questions

- [D1] **Per bank or per file name?** A bank renames its export.

## Comments

Built on its branch, not merged.
"""


@pytest.fixture
def built(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A one-ticket tracker in a git repo whose build was committed on the ticket's own branch: the
    tracker root, the repo, and the ticket file as the checkout still has it, questionless and
    `claimed`, which is where dispatch leaves it until the orchestrator flips it."""
    root = tmp_path / "repo" / "agent" / "tickets"
    root.mkdir(parents=True)
    repo = root.parent.parent
    path = root / "map-columns.md"
    ticket(path, "claimed", priority=1, size="S")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tracker")
    git(repo, "checkout", "-q", "-b", BRANCH)
    path.write_text(path.read_text() + BUILT)
    git(repo, "commit", "-q", "-am", "the build")
    git(repo, "checkout", "-q", "main")
    return root, repo, path


def rendered(root: Path, repo: Path, out: Path) -> str:
    render(tracker_roots(root), repo, out)
    return out.read_text()


def test_a_build_in_review_keeps_the_status_its_checkout_gives_it(built: tuple[Path, Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The branch says what the worker wrote, the checkout where the ticket stands: the review flip
    is the orchestrator's and lands on the tracker's copy, not on the worker's branch. Until that
    flip the branch is a build in progress and the board reads none of it."""
    root, repo, path = built
    out = tmp_path / "board.html"
    page = rendered(root, repo, out)
    assert questions_on(rows_of(page)["t-map-columns"]) == [], "a claimed ticket's branch is a build in progress"
    assert 'id="grp-needs"' not in page, "nothing waits on the user, so the group is not on the page"
    ticket(path, "review", priority=1, size="S")  # the flip the orchestrator makes on the tracker's copy
    page = rendered(root, repo, out)
    assert rows_in(page, "needs") == {"t-map-columns"}
    assert questions_on(rows_of(page)["t-map-columns"]) == [("D1", "Per bank or per file name?")]
    assert 'class="ticket row-review" id="t-map-columns"' in page, "the branch's own claimed does not outrank the tracker"
    assert "brief" not in labels_of(rows_of(page)["t-map-columns"]), "the brief has one home, and the branch's copy does not open a second"


def test_a_ruling_in_the_tracker_answers_a_question_its_branch_asks(built: tuple[Path, Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The board hands out the tracker's path on the clipboard, so that is where the session taking
    the user's answer writes the `Ruled` line; the branch's copy is the worker's and does not move
    again until the merge."""
    root, repo, path = built
    ticket(path, "review", priority=1, size="S")
    path.write_text(path.read_text() + "\n## Questions\n\n- [D1] **Per bank or per file name?** A bank renames its export.\n  - Ruled 2026-09-23: per bank.\n")
    page = rendered(root, repo, tmp_path / "board.html")
    assert questions_on(summary_of(rows_of(page)["t-map-columns"])) == [], "the ruling is in the file the board named"
    assert rows_in(page, "needs") == {"t-map-columns"}, "the build still waits for its ruling"
    assert asked_in(rows_of(page)["t-map-columns"]) == [{
        "tag": "D1", "head": "Per bank or per file name?", "detail": "A bank renames its export.",
        "ruling": "Ruled 2026-09-23: per bank.",
    }], "the opened ticket reads the branch's question with the ruling the tracker's copy carries"


def test_a_ticket_with_no_branch_of_its_own_left_reads_none(built: tuple[Path, Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The slug is the ticket's id across the tracker, so the branch ending in it is its own; once
    that branch has merged and been deleted, the merge has brought the questions in and there is
    nothing else for the row to read."""
    root, repo, path = built
    ticket(path, "review", priority=1, size="S")
    out = tmp_path / "board.html"
    assert questions_on(rows_of(rendered(root, repo, out))["t-map-columns"]) == [("D1", "Per bank or per file name?")]
    git(repo, "branch", "-D", BRANCH)
    assert questions_on(rows_of(rendered(root, repo, out))["t-map-columns"]) == []


def test_the_board_reads_the_ticket_branches_again_on_every_render(built: tuple[Path, Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """A worker cutting its branch and committing on it moves no file under the tracker, so the
    watcher's snapshot has to carry the branches, and a board that has been open for a day has to
    ask again rather than answer from the list it read first."""
    root, repo, path = built
    sha = git(repo, "rev-parse", BRANCH)
    git(repo, "branch", "-D", BRANCH)
    ticket(path, "review", priority=1, size="S")
    out = tmp_path / "board.html"
    assert questions_on(rows_of(rendered(root, repo, out))["t-map-columns"]) == [], "no branch yet, nothing to read"
    before = tracker_snapshot(tracker_roots(root), repo)
    git(repo, "branch", BRANCH, sha)
    assert tracker_snapshot(tracker_roots(root), repo) != before, "a watching board would never render the build's questions"
    assert questions_on(rows_of(rendered(root, repo, out))["t-map-columns"]) == [("D1", "Per bank or per file name?")]
    after = tracker_snapshot(tracker_roots(root), repo)
    git(repo, "branch", "-f", BRANCH, "main")  # as a commit on the branch moves its tip
    assert tracker_snapshot(tracker_roots(root), repo) != after


def test_a_question_is_read_in_the_shapes_a_ticket_file_is_written_in() -> None:
    """What the spec's prose allows and the generated check above does not draw: an item with no
    bold headline, a detail running over lines, a rationale that opens with the word Ruled and
    names no date, and a second `## Questions` section, which is how a worker's questions reach a
    ticket that already had some."""
    read = {q.tag: q for q in board.questions_of("""## Questions

- [D1] **Bulleted ruling?** One line.
  - Ruled 2026-09-21: per bank.
- [D2] **A ruling is a bullet of its own?** A line merely indented under the question continues it.
  Ruled 2026-09-22 is part of this detail.
- [D3] No bold headline, just the question?
- [D4] **A detail over two lines?** It starts here
  and carries on there.
- [D5] **Ruled out is not a ruling.** Two ways out.
  - Ruled out: a third, since the suite is already slow.

## Comments

The build, on its branch.

## Questions

- [D6] **Appended by the worker?** Under a second heading of its own.
""", [])}
    assert list(read) == ["D1", "D2", "D3", "D4", "D5", "D6"]
    assert read["D1"].ruled == "2026-09-21"
    assert read["D2"].ruled is None and "Ruled 2026-09-22 is part of this detail" in read["D2"].detail
    assert read["D3"].headline == "No bold headline, just the question?" and read["D3"].detail == ""
    assert read["D4"].detail == "It starts here and carries on there."
    assert read["D5"].ruled is None, "a line that opens with the word Ruled and names no date rules nothing"
    assert read["D6"].headline == "Appended by the worker?"


def test_a_near_design_session_is_in_needs_me_with_no_question_written_down(tmp_path: Path) -> None:
    """The needs-me clauses the demo tracker has no row for: a ticket the user is in the loop for
    and would sit for soon is there before anyone has written its question, one nobody can sit for
    yet is not, and a done ticket is never there whatever it still carries (the spec's Property, as
    amended 2026-09-23)."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "soon.md", "open", needs_user=True, priority=2, size="S")
    ticket(root / "taken.md", "claimed", needs_user=True, priority=1, size="S")
    ticket(root / "someday.md", "open", needs_user=True, priority=3, size="S")
    ticket(root / "shipped.md", "done", priority=1, size="S")
    (root / "shipped.md").write_text(
        (root / "shipped.md").read_text() + "\n## Questions\n\n- [D1] **Left open when it landed?** Nobody ruled.\n"
    )
    page = render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")
    assert rows_in(page, "needs") == {"t-soon"}
    assert questions_on(rows_of(page)["t-shipped"]) == [], "a question left on a done ticket is a leftover, not a call"
    assert copiers(page) == [], "the done group grew a copy-all for a question no row on the board shows"


def test_every_copy_button_on_the_board_shows_what_it_copies(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The spec's reviewed Property, at the loader-and-page seam its Testing Decisions names: the
    words a button shows on hover are what its click puts on the clipboard, cut off only where they
    run long.

    The tracker is the one with its transcripts where this machine keeps its own, since the button
    that copies a resume command is only drawn for a session the board can name, and a check that
    rendered without them would hold the Property for four kinds of button out of five."""
    out = tmp_path / "board.html"
    render(tracker_roots(transcribed.root), transcribed.repo, out)
    page = out.read_text()
    found = copiers(page)
    assert {which for which, _, _, _ in found} == {"qcopy", "qall", "qgroup", "democopy", "resume"}
    for which, text, said, tip in found:
        what, _, shown = tip.partition("\n\n")
        assert len(what.split()) >= 4 and "copy" in what, f"the {which} button says {what!r} of the click"
        assert shown, f"the {which} button shows nothing of what it copies"
        if shown.endswith("…"):  # a button whose text runs long shows the start of it and says so
            assert text.startswith(shown[:-1]) and len(shown) > 120, f"the {which} button shows {shown!r}"
            assert len(shown) <= 260, f"the {which} button spills {len(shown)} characters into the row"
        else:
            assert shown == text, f"the {which} button shows {shown!r} and copies {text!r}"
        # the note the page shows once a click has landed names what it landed, in the terms that
        # button's own text is in: the file for the three that copy a path, a count for the board's
        # worth of questions, the session for the one that copies a command
        if which == "qgroup":
            assert said == f"{sum(line.startswith('- [D') for line in text.splitlines())} questions"
        elif which == "resume":
            assert said.removeprefix("the command resuming ") not in ("", said)
        else:
            assert text.splitlines()[0].rsplit("/", 1)[-1] in said, f"the {which} button's note says {said!r}"
    # the copy button the row already had says the same of itself (02-rows)
    assert str(transcribed.root / "flaky-upload-test.md") in tips_on(rows_of(page)["t-flaky-upload-test"])["num"]


def test_the_needs_me_groups_copy_button_holds_every_open_question_under_its_tickets_path(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """What the user pastes into an editor to answer a board's worth of questions at once."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    page = out.read_text()
    (text,) = [text for kind, text, _, _ in copiers(page) if kind == "qgroup"]
    blocks = [block.splitlines() for block in text.split("\n\n")]
    assert {lines[0] for lines in blocks} == {
        str(demo.root / name) for name in [
            "map-columns.md", "view-storage.md", "view-list-shape.md", "flaky-upload-test.md",
            "pick-a-date-library.md", "retire-legacy-exporter.md", "speed-up-tests.md",
        ]
    }
    asked = [line for lines in blocks for line in lines[1:]]
    assert len(asked) == 11 and all(line.startswith("- [D") for line in asked)
    assert any("Remember the mapping per bank" in line for line in asked), "the questions on a ticket branch are in it too"
    # the file's own markdown, so a question pastes back into the ticket as it was written
    assert "- [D3] **The mappings live in `~/.config/ledger/mappings.toml`.** Fine there, or beside the ledger file so they travel with it?" in asked
    assert not any("Whose card does the sandbox go on" in line for line in asked), "a ruled question is answered"


# ---- an opened ticket ------------------------------------------------------
# The spec's Decisions on an opened ticket: blocks, not a wall of text, in one order, reading the
# artefacts from the ticket's show directory and folding the comments away as history.

QUESTION_PARTS = ("tag", "head", "detail", "ruling")


def put(path: Path, text: str) -> None:
    """A file under a directory that may not exist yet: an artefact beside a ticket."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def artefacts_markup(row: str) -> str:
    """The artefacts list an opened ticket holds, as the page wrote it."""
    listed = re.search(r'<ul class="artefacts">.*?</ul>', body_of(row), re.S)
    return listed.group() if listed else ""


def artefacts_in(row: str) -> list[tuple[str, str]]:
    """What an opened ticket lists as its artefacts, in order: ("demo", the path its button copies)
    for the demo, and (the words of the link, where it points) for a figure."""
    found = []
    for item in re.findall(r"<li>(.*?)</li>", artefacts_markup(row), re.S):
        link = re.search(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', item)
        found.append((link.group(2), link.group(1)) if link else ("demo", re.search(r'data-copy="([^"]+)"', item).group(1)))
    return found


def labels_of(row: str) -> list[str]:
    """The word over each block of an opened ticket, in the order the reader meets them."""
    return [text for mark, text, _ in marks_on(body_of(row)) if mark == "label"]


def asked_in(row: str) -> list[dict[str, str]]:
    """Every question an opened ticket holds, as the parts it shows of each: its tag, its headline,
    its detail, and the ruling that answered it where one has, each shown once and in that order."""
    found: list[dict[str, str]] = []
    for mark, text, _ in marks_on(body_of(row)):
        if mark == "question":
            found.append({})
        elif mark in QUESTION_PARTS and found:
            assert mark not in found[-1], f"a question shows its {mark} twice"
            found[-1][mark] = text
    assert all(list(q) == [part for part in QUESTION_PARTS if part in q] for q in found), f"out of order: {found}"
    return found


def test_an_opened_ticket_reads_as_blocks_in_one_order(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The build in review, which has one of every block: its questions, the sessions that worked
    on it, its artefacts, then its own sections as the file writes them, the comments last and
    folded."""
    out = tmp_path / "board.html"
    render(tracker_roots(transcribed.root), transcribed.repo, out)
    row = rows_of(out.read_text())["t-map-columns"]
    assert labels_of(row) == [
        "questions", "sessions on this machine", "artefacts", "what to build", "acceptance criteria", "comments",
    ]
    # the brief is the row's own: read before anything is opened, and written once
    assert "You tell the importer once" in summary_of(row)
    assert "You tell the importer once" not in body_of(row)
    assert summary_of(row).count('<span class="brief">') == 1


def test_an_opened_ticket_carries_every_question_with_its_detail_and_the_ruling_on_it(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The row shows the open headlines; the ticket shows all of them, the detail it had no room
    for, and what the user ruled on the ones that are answered."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    row = rows_of(out.read_text())["t-flaky-upload-test"]
    assert asked_in(row) == [
        {"tag": "D1", "head": "Retry the upload, or fake the clock?",
         "detail": "A retry hides a real slowdown; a fake clock makes the test say nothing about timing."},
        {"tag": "D2", "head": "Keep the test in the fast suite?",
         "detail": "It takes four seconds with either fix.",
         "ruling": "Ruled 2026-09-21: keep it in the fast suite."},
    ]
    assert [tag for tag, _ in questions_on(summary_of(row))] == ["D1"], "the row lists the open one and no more"
    assert '<li class="question ruled">' in body_of(row), "an answered question is marked answered"


def test_an_opened_ticket_copies_each_open_question_where_the_folded_row_does(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """An opened row lists its questions once: the list under the name goes (the page's style) and
    the block carries the same buttons beside the detail, copying the same line under the same
    path. The row's copy-all goes with the list it copies."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    page = out.read_text()
    rows = rows_of(page)
    row = rows["t-flaky-upload-test"]
    written = (f"{demo.root / 'flaky-upload-test.md'}\n- [D1] **Retry the upload, or fake the clock?**"
               " A retry hides a real slowdown; a fake clock makes the test say nothing about timing.")
    assert [text for _, text, _, _ in copiers(body_of(row))] == [written], "the question as the file writes it, under its path"
    assert copiers(body_of(row)) == copiers(summary_of(row)), "the same button, and none on the question a ruling answered"
    # the list going is the page's style, which only a browser sees run (test_board_layout.py);
    # this is the tripwire for a run with no browser, not the check
    assert ".ticket[open] .qs { display: none; }" in page, "nothing in the page hides an opened row's question list"
    three = rows["t-map-columns"]
    assert [which for which, _, _, _ in copiers(body_of(three))] == ["qcopy", "qcopy", "qcopy", "democopy"]
    assert [which for which, _, _, _ in copiers(summary_of(three))] == ["qcopy", "qcopy", "qcopy", "qall"]
    assert [text for _, text, _, _ in copiers(body_of(three))[:3]] == [
        text for _, text, _, _ in copiers(summary_of(three))[:3]
    ], "a question is copied the same way wherever the button for it sits"


def test_a_blocked_rows_questions_carry_the_same_buttons_in_both_places(tmp_path: Path) -> None:
    """A ticket's body is rendered from the status its file declares, and the board derives
    `blocked` from its blockers afterwards; the row and the block read the two. They have to agree
    on which questions carry a copy button, which they do while only a done ticket loses them."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "store.md", "open", priority=1, size="S")
    ticket(root / "waiting.md", "open", blocked_by=["store"], priority=1, size="S")
    waiting = root / "waiting.md"
    waiting.write_text(waiting.read_text() + "\n## Questions\n\n- [D1] **Which store?** The one that travels.\n")
    page = render_page("demo", list(load(root).values()), log="", stamp="s", stamp_src="s.js")
    assert '<details class="ticket row-blocked" id="t-waiting"' in page, "the fixture no longer exercises a derived status"
    row = rows_of(page)["t-waiting"]
    written = f"{waiting}\n- [D1] **Which store?** The one that travels."
    assert [text for _, text, _, _ in copiers(body_of(row))] == [written]
    assert copiers(body_of(row)) == copiers(summary_of(row)), "the two readings of the status disagree"


def test_a_tickets_artefacts_are_read_from_its_show_directory(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The demo on a button that copies its path, since a demo is a command to run, and the figures
    beside it as links. Nothing in the ticket declares either: the directory is read."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    rows = rows_of(out.read_text())
    show = demo.repo / "agent" / "show" / "map-columns"
    assert artefacts_in(rows["t-map-columns"]) == [
        ("demo", str(show / "demo")), ("mapping.svg", f"file://{show / 'mapping.svg'}"),
    ]
    assert [which for which, _, _, _ in copiers(artefacts_markup(rows["t-map-columns"]))] == ["democopy"], (
        "the demo is the one artefact on a button"
    )
    # every show directory is its ticket's slug's own, beside the tracker the ticket was read from
    alone = demo.repo / "agent" / "show" / "speed-up-tests"
    assert artefacts_in(rows["t-speed-up-tests"]) == [("demo", str(alone / "demo"))]
    assert "artefacts" not in labels_of(rows["t-flaky-upload-test"]), "nothing has been built on it yet"


def test_what_a_show_directory_offers_an_opened_ticket(tmp_path: Path) -> None:
    """A figure under it keeps the path that names it, what the demo regenerates under out/ is not
    an artefact, and a ticket with figures and no demo has the block all the same."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "map-columns.md", "review")
    ticket(root / "view-list.md", "open")
    show = tmp_path / "agent" / "show"
    put(show / "map-columns" / "demo", "#!/bin/sh\necho two imports\n")
    put(show / "map-columns" / "shots" / "mapping.svg", "<svg/>")
    put(show / "map-columns" / "out" / "frame-01.png", "generated")
    put(show / "view-list" / "layouts.svg", "<svg/>")
    rows = rows_of(page_of(root))
    assert artefacts_in(rows["t-map-columns"]) == [
        ("demo", str(show / "map-columns" / "demo")),
        ("shots/mapping.svg", f"file://{show / 'map-columns' / 'shots' / 'mapping.svg'}"),
    ]
    assert artefacts_in(rows["t-view-list"]) == [("layouts.svg", f"file://{show / 'view-list' / 'layouts.svg'}")]


def test_the_comments_fold_under_an_opened_ticket_as_history(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """A build's closing comment is what happened, not what the ticket is, so it opens only when
    the reader asks for it."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    row = rows_of(out.read_text())["t-map-columns"]
    folded = re.search(r'<details class="history"(\s+open)?>(.*)</details>', body_of(row), re.S)
    assert folded and not folded.group(1), "the comments are open before anyone asked for them"
    assert "The mapping step is built and remembers a bank" in folded.group(2), "the closing comment, on its branch"
    assert labels_of(row)[-1] == "comments"


def test_the_acceptance_criteria_read_as_a_checklist(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The build in review met one criterion on its branch and left the other, which is what the
    checklist says; neither reads as a line opening with a bracket."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    body = body_of(rows_of(out.read_text())["t-map-columns"])
    assert [(mark, text) for mark, text, _ in marks_on(body) if mark == "tick"] == [
        ("tick", "The second import from a bank asks nothing and maps the columns the first one did."),
        ("tick", "csv-import#P1, reviewed: a mapping that fails halfway writes nothing."),
    ]
    assert body.count('<li class="tick met"') == 1 and body.count('<li class="tick"') == 1
    assert "[x]" not in body and "[ ]" not in body


def test_an_opened_ticket_leaves_none_of_the_file_behind(tmp_path: Path) -> None:
    """A ticket writes the sections it needs: one opens with its provenance under no heading of its
    own, answers under a heading the board has no word for, and says more in its `## Questions`
    section than its items. Each keeps the place the file gives it, and a `##` line inside a fence
    is code the ticket quotes, not a heading that splits it."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    (root / "pick-a-format.md").write_text(
        "---\nstatus: review\npriority: 2\nsize: S\n---\n\n# A wire format\n\n"
        "Proposed by the orchestrator from duplicate-rule's closing comment.\n\n"
        "## Brief\n\nWhich format the two services speak.\n\n"
        "## Questions\n\nThe two are coupled: the second only arises if you say Protobuf.\n\n"
        "- [D1] **Protobuf or JSON?** One is smaller, the other is read by hand.\n\n"
        "## Answer\n\nJSON, until a profile says otherwise.\n\n"
        "## Comments\n\nThe worker's closing comment quoted the shape of a ticket:\n\n"
        "```markdown\n## Questions\n\n- [D1] **A question?** Its detail.\n```\n"
    )
    row = rows_of(page_of(root))["t-pick-a-format"]
    assert labels_of(row) == ["questions", "answer", "comments"]
    written = body_of(row)
    assert "The two are coupled" in written, "what the questions section says besides its items"
    assert written.index("The two are coupled") < written.index("Protobuf or JSON?"), "above the questions it introduces"
    assert "Proposed by the orchestrator" in written, "the provenance line, under no heading of its own"
    assert written.index("Proposed by the orchestrator") < written.index("JSON, until a profile says otherwise.")
    assert asked_in(row) == [{"tag": "D1", "head": "Protobuf or JSON?", "detail": "One is smaller, the other is read by hand."}]
    quoted = re.search(r'<details class="history".*</details>', written, re.S)
    assert quoted and "## Questions" in quoted.group(), "the fenced sample is quoted, not read as a section of its own"


def test_a_ticket_that_says_less_gets_fewer_blocks(tmp_path: Path) -> None:
    """The board invents no block: a ticket with no artefacts and no comments opens as what it does
    say, a question with no detail shows none, and a checkbox outside the acceptance criteria is
    the ticket's own writing rather than a criterion."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    (root / "skip-imported-rows.md").write_text(
        "---\nstatus: open\npriority: 2\nsize: S\n---\n\n# Skip rows already imported\n\n"
        "## Brief\n\nImporting the same export twice adds nothing the second time.\n\n"
        "## What to build\n\nA row matches on date, amount and payee. The report then reads:\n\n"
        "- [ ] 12 rows added\n- [x] 3 rows skipped\n\n"
        "## Questions\n\n- [D1] **Match on the payee too, or only date and amount?**\n"
    )
    row = rows_of(page_of(root))["t-skip-imported-rows"]
    assert labels_of(row) == ["questions", "what to build"], "no artefacts, and nothing folded away"
    assert "<details" not in body_of(row), "a ticket with no comments has no history to fold"
    assert asked_in(row) == [{"tag": "D1", "head": "Match on the payee too, or only date and amount?"}]
    assert 'class="tick' not in body_of(row), "the checkbox is in what to build, and only the criteria are a checklist"
    assert "[x] 3 rows skipped" in body_of(row), "the ticket's own words, as it wrote them"


def test_the_watcher_notices_a_demo_landing_in_a_show_directory(repo: Path, tracker: Path) -> None:
    """A session writing a demo moves no file under the tracker, and the artefacts are what an
    opened ticket would otherwise never show."""
    before = tracker_snapshot(tracker_roots(tracker), repo)
    demo = tracker.parent / "show" / "built" / "demo"
    demo.parent.mkdir(parents=True)
    demo.write_text("#!/bin/sh\necho the import, twice\n")
    assert tracker_snapshot(tracker_roots(tracker), repo) != before


# ---- the sessions behind a ticket ------------------------------------------
# The spec's Decision: the sessions a ticket lists come from the `Session:` trailer on every commit
# that changed its file, on every branch, and take their title and working directory from their
# transcript on this machine. A session with no transcript here the user cannot resume, so it is
# not listed.

HERE = "f1e2d3c4-1111-4111-8111-111111111111"  # committed on the main branch and on the ticket's own
AWAY = "f1e2d3c4-2222-4222-8222-222222222222"  # a worker on another host: no transcript on this machine
NAMED = "f1e2d3c4-3333-4333-8333-333333333333"  # committed on the ticket branch only, renamed by hand, its worktree gone
NEW = "f1e2d3c4-4444-4444-8444-444444444444"  # committed before Claude Code had titled it
LOOKALIKE = "agent/show/demo/tickets/map-columns.md"  # same name, same directory name, another file


@pytest.fixture
def worked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """(the tracker, its repo) of a ticket four sessions committed on: one on the main branch, one
    only on the ticket's own branch, one a worker on another host, one too new to have a title.
    Beside it, a ticket committed before any session put its id on a commit, and a file elsewhere in
    the repo with the ticket's own name under a directory of the ticket's own name.

    The repo's path carries a space, which a resume command has to survive. It uses the demo
    tracker's git helpers rather than this file's, since only those pin a commit's date.
    """
    repo = tmp_path / "the ledger"
    root = repo / "agent" / "tickets"
    root.mkdir(parents=True)
    demo_git(repo, "init", "-q", "-b", "master")
    ticket(root / "map-columns.md", "open")
    demo_commit(repo, HERE, "2026-09-14T10:00:00+02:00", "map-columns: filed", "agent/tickets")
    append(root / "map-columns.md", "\nOne mapping per bank.\n")
    demo_commit(repo, HERE, "2026-09-16T09:00:00+02:00", "map-columns: one mapping per bank", "agent/tickets")

    demo_git(repo, "checkout", "-q", "-b", "ticket/map-columns")
    append(root / "map-columns.md", "\nRead from the header row.\n")
    demo_commit(repo, AWAY, "2026-09-17T11:00:00+02:00", "map-columns: the mapping step", "agent/tickets")
    append(root / "map-columns.md", "\nAsked once per bank.\n")
    demo_commit(repo, NAMED, "2026-09-18T12:00:00+02:00", "map-columns: for review", "agent/tickets")
    append(root / "map-columns.md", "\nThe header row names the bank.\n")
    demo_commit(repo, NEW, "2026-09-19T08:00:00+02:00", "map-columns: the header row names the bank", "agent/tickets")
    demo_git(repo, "checkout", "-q", "master")

    ticket(root / "view-list.md", "open")
    demo_git(repo, "add", "--", "agent/tickets")
    demo_git(repo, "commit", "-q", "-m", "view-list: filed before the hook")
    put(repo / LOOKALIKE, "---\nstatus: open\n---\n\n# A fixture tracker's own ticket\n")
    demo_commit(repo, HERE, "2026-09-20T10:00:00+02:00", "a demo tracker for the docs", "agent/show")

    written = tmp_path / "claude" / "projects"
    write_transcript(written, HERE, str(repo), "Ledger imports")
    write_transcript(written, NAMED, str(tmp_path / "gone"), "Wave 1 of csv-import", "Mapping the Sparkasse export")
    write_transcript(written, NEW, str(repo), "")
    monkeypatch.setattr(board, "TRANSCRIPTS", written)
    return root, repo


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text() + text)


def sessions_in(row: str) -> list[tuple[str, str, str]]:
    """(its title, the days it worked, the command its button copies) for every session an opened
    ticket lists, in the order it lists them."""
    listed = re.search(r'<ul class="sessions">(.*?)</ul>', body_of(row), re.S)
    found = []
    for item in re.findall(r"<li>(.*?)</li>", listed.group(1) if listed else "", re.S):
        marks = {mark: text for mark, text, _ in marks_on(item)}
        (resume,) = [text for which, text, _, _ in copiers(item) if which == "resume"]
        found.append((marks["stitle"], marks["when"], resume))
    return found


def test_a_tickets_sessions_come_from_the_trailers_on_every_branch(worked: tuple[Path, Path]) -> None:
    """The one that worked on the ticket branch is listed beside the one that worked on master: a
    build's commits are on its own branch until the merge. The worker on another host is not, a
    ticket no trailer names has no sessions, and a file the ticket merely shares a name with is
    another file."""
    root, repo = worked
    listed = ticket_sessions(root / "map-columns.md", repo)
    assert [s.id for s in listed] == [HERE, NAMED, NEW], "oldest first, and AWAY has no transcript on this machine"
    assert [(s.first, s.last) for s in listed] == [
        ("2026-09-14", "2026-09-16"), ("2026-09-18", "2026-09-18"), ("2026-09-19", "2026-09-19"),
    ], f"HERE's later commit was on {LOOKALIKE}, which is not this ticket"
    assert ticket_sessions(root / "view-list.md", repo) == [], "no trailer says which session committed it"


def test_a_session_shows_the_name_it_was_given_over_the_one_it_was_written(worked: tuple[Path, Path]) -> None:
    """The title is the session's `/rename` name where it has one, else Claude Code's own, else the
    id, which is all a session has before its first title is written."""
    root, repo = worked
    titles = {s.id: s.title for s in ticket_sessions(root / "map-columns.md", repo)}
    assert titles == {HERE: "Ledger imports", NAMED: "Mapping the Sparkasse export", NEW: NEW}


def test_an_opened_ticket_lists_its_sessions_with_the_command_that_resumes_each(worked: tuple[Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """What the user reads to recognise the session they want, and clicks to close their tmux panes:
    the title, the days it committed on the ticket, and the command that picks it up again. The one
    whose working directory dispatch has since removed is resumed where the reader stands."""
    root, repo = worked
    out = tmp_path / "board.html"
    render(tracker_roots(root), repo, out)
    rows = rows_of(out.read_text())
    assert sessions_in(rows["t-map-columns"]) == [
        ("Ledger imports", "2026-09-14 → 2026-09-16", f"cd '{repo}' && claude --resume {HERE}"),
        ("Mapping the Sparkasse export", "2026-09-18", f"claude --resume {NAMED}"),
        (NEW, "2026-09-19", f"cd '{repo}' && claude --resume {NEW}"),
    ]
    assert "sessions on this machine" in labels_of(rows["t-map-columns"])
    assert "sessions on this machine" not in labels_of(rows["t-view-list"]), "no trailer names a session"
    assert AWAY not in out.read_text(), "the worker on another host is left out, not shown unresumable"
    assert absences(out.read_text(), "transcripts") == 0, "this machine has its transcripts"


def test_a_session_that_commits_between_two_renders_is_on_the_second(worked: tuple[Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The board reads the log again on every render, as it does the ticket branches: a session
    working while the board watches is on the ticket by the next one."""
    root, repo = worked
    out = tmp_path / "board.html"
    render(tracker_roots(root), repo, out)
    assert [title for title, _, _ in sessions_in(rows_of(out.read_text())["t-view-list"])] == []
    append(root / "view-list.md", "\nThe list is a sidebar.\n")
    demo_commit(repo, HERE, "2026-09-21T10:00:00+02:00", "view-list: the list is a sidebar", "agent/tickets")
    render(tracker_roots(root), repo, out)
    assert [title for title, _, _ in sessions_in(rows_of(out.read_text())["t-view-list"])] == ["Ledger imports"]


def test_the_button_that_resumes_a_session_shows_the_command_it_copies(worked: tuple[Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The spec's reviewed Property, at the button this slice adds: what it says on hover is what
    the click puts on the clipboard, and its note names the session the way the reader knows it."""
    root, repo = worked
    out = tmp_path / "board.html"
    render(tracker_roots(root), repo, out)
    listed = sessions_in(rows_of(out.read_text())["t-map-columns"])
    found = [c for c in copiers(rows_of(out.read_text())["t-map-columns"]) if c[0] == "resume"]
    assert len(found) == len(listed)
    for (_, text, said, tip), (title, _, command) in zip(found, listed):
        what, _, shown = tip.partition("\n\n")
        assert len(what.split()) >= 4 and "copy" in what, f"the button says {what!r} of the click"
        assert shown == text == command, f"the button shows {shown!r} and copies {text!r}"
        assert title in said, f"the note says {said!r} of a session the reader knows as {title!r}"


def test_a_resume_command_longer_than_a_button_shows_is_cut_where_every_other_one_is(worked: tuple[Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """A working directory nested deep enough to run past what a button shows: the words are cut
    with an ellipsis, as a question's are, rather than spilling into the row."""
    root, repo = worked
    deep = repo / ("one-mapping-per-bank-" * 6)
    deep.mkdir()
    write_transcript(board.TRANSCRIPTS, HERE, str(deep), "Ledger imports")
    out = tmp_path / "board.html"
    render(tracker_roots(root), repo, out)
    (resume, *_) = [c for c in copiers(rows_of(out.read_text())["t-map-columns"]) if c[0] == "resume"]
    _, text, _, tip = resume
    shown = tip.partition("\n\n")[2]
    assert str(deep) in text and len(text) > board.COPY_CAP, "the command has to run long for the cut to show"
    assert shown.endswith("\u2026") and text.startswith(shown[:-1])


def test_the_demo_trackers_ticket_lists_the_sessions_this_machine_can_resume(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The fixture's build in review: four sessions on its commits, the two with a transcript here
    listed with their titles, the worker on another host left out. The second ran in a worktree
    dispatch has since removed, so its command resumes it where the reader stands."""
    out = tmp_path / "board.html"
    render(tracker_roots(transcribed.root), transcribed.repo, out)
    row = rows_of(out.read_text())["t-map-columns"]
    assert sessions_in(row) == [
        ("Grilling the CSV import", "2026-09-14", f"cd {transcribed.repo} && claude --resume {S1}"),
        ("Dispatching csv-import, wave 1", "2026-09-17 → 2026-09-18", f"claude --resume {S2}"),
    ]
    assert S4 not in out.read_text(), "the worker built it on another host, where the user cannot resume it"


FILED = "b4c5d6e7-1111-4111-8111-111111111111"  # filed both tickets, before either moved
GRILLED = "b4c5d6e7-2222-4222-8222-222222222222"  # grilled them into the feature, which moved them
LATER = "b4c5d6e7-3333-4333-8333-333333333333"  # worked on one after it left the feature again


@pytest.fixture
def moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """(the tracker, its repo) of two tickets that moved: one standalone ticket grilled into a
    feature, and one grilled in that later left it again under a name of its own.

    Beside the three sessions named above, AWAY edits one under its first path, so a carried session
    the board cannot resume has somewhere to show; and the move out of the feature is the user's own
    `git mv`, under no session at all.
    """
    repo = tmp_path / "the ledger"
    root = repo / "agent" / "tickets"
    (root / "csv-import").mkdir(parents=True)
    demo_git(repo, "init", "-q", "-b", "master")
    ticket(root / "split-rows.md", "open")
    ticket(root / "name-columns.md", "open")
    demo_commit(repo, FILED, "2026-09-14T10:00:00+02:00", "two csv tickets filed", "agent/tickets")
    append(root / "split-rows.md", "\nOne row per transaction.\n")
    demo_commit(repo, AWAY, "2026-09-15T11:00:00+02:00", "split-rows: one row per transaction", "agent/tickets")

    demo_git(repo, "mv", "agent/tickets/split-rows.md", "agent/tickets/csv-import/02-split-rows.md")
    demo_git(repo, "mv", "agent/tickets/name-columns.md", "agent/tickets/csv-import/01-name-columns.md")
    demo_commit(repo, GRILLED, "2026-09-16T09:00:00+02:00", "csv-import: grilled, two slices", "agent/tickets")
    append(root / "csv-import" / "01-name-columns.md", "\nThe header row names the bank.\n")
    # written during the grilling and cherry-picked over after the move, so the walk reaches it
    # after the commit whose date it has to widen the span back from
    demo_commit(repo, GRILLED, "2026-09-15T16:00:00+02:00", "csv-import: 01, the header row", "agent/tickets")

    demo_git(repo, "mv", "agent/tickets/csv-import/01-name-columns.md", "agent/tickets/header-row.md")
    demo_git(repo, "commit", "-q", "-m", "header-row: out of csv-import")  # moved by hand, no session
    append(root / "header-row.md", "\nAsked once per bank.\n")
    demo_commit(repo, LATER, "2026-09-19T08:00:00+02:00", "header-row: asked once per bank", "agent/tickets")

    written = tmp_path / "claude" / "projects"
    for sid, title in ((FILED, "Filing the csv tickets"), (GRILLED, "Grilling csv-import"), (LATER, "The header row")):
        write_transcript(written, sid, str(repo), title)
    monkeypatch.setattr(board, "TRANSCRIPTS", written)
    return root, repo


def test_a_ticket_that_moved_lists_the_sessions_from_under_its_old_path(moved: tuple[Path, Path]) -> None:
    """A moved ticket is one ticket: git records the move, so the session that filed it is listed on
    it wherever it now sits, and a chain of two moves carries both earlier paths."""
    root, repo = moved
    once = ticket_sessions(root / "csv-import" / "02-split-rows.md", repo)
    assert [(s.id, s.first, s.last) for s in once] == [
        (FILED, "2026-09-14", "2026-09-14"), (GRILLED, "2026-09-16", "2026-09-16"),
    ], "the session that filed it as agent/tickets/split-rows.md worked on this ticket"
    twice = ticket_sessions(root / "header-row.md", repo)
    assert [(s.id, s.first, s.last) for s in twice] == [
        (FILED, "2026-09-14", "2026-09-14"),
        (GRILLED, "2026-09-15", "2026-09-16"),
        (LATER, "2026-09-19", "2026-09-19"),
    ], "standalone, then the feature's 01, then standalone again, the move itself under no session"


def test_a_session_the_board_cannot_resume_is_left_off_a_moved_ticket_too(moved: tuple[Path, Path]) -> None:
    """The Property that a listed session has a transcript on this machine, over a carried session:
    AWAY worked on the ticket under its first path and has no transcript here."""
    root, repo = moved
    under = board.session_log(repo)["agent/tickets/csv-import/02-split-rows.md"]
    assert AWAY in under, "it committed on the ticket while it was agent/tickets/split-rows.md"
    assert AWAY not in {s.id for s in ticket_sessions(root / "csv-import" / "02-split-rows.md", repo)}


def test_a_move_on_one_branch_leaves_the_sessions_on_the_path_another_branch_still_has(
    moved: tuple[Path, Path],
) -> None:
    """A move is a fact of the branch that made it, and the walk is over every branch at once. The
    ticket a worker moves on its own branch keeps its sessions where the main checkout still has
    it, until the merge."""
    root, repo = moved
    demo_git(repo, "checkout", "-q", "-b", "ticket/master/split-rows")
    demo_git(repo, "mv", "agent/tickets/csv-import/02-split-rows.md", "agent/tickets/split-rows.md")
    demo_commit(repo, LATER, "2026-09-21T10:00:00+02:00", "split-rows: out of csv-import", "agent/tickets")
    demo_git(repo, "checkout", "-q", "master")
    assert [s.id for s in ticket_sessions(root / "csv-import" / "02-split-rows.md", repo)] == [FILED, GRILLED], (
        "the path master still holds the ticket at, whose board the move has not reached"
    )
    assert [s.id for s in ticket_sessions(root / "split-rows.md", repo)] == [FILED, GRILLED, LATER]


def test_a_ticket_born_at_a_path_another_left_lists_only_its_own_sessions(moved: tuple[Path, Path]) -> None:
    """A ticket filed at a path a move freed is another ticket, and inherits nothing from the one
    that moved away."""
    root, repo = moved
    ticket(root / "split-rows.md", "open")  # a second ticket, named for the gap the first one left
    demo_commit(repo, LATER, "2026-09-20T10:00:00+02:00", "split-rows: filed again", "agent/tickets")
    assert [s.id for s in ticket_sessions(root / "split-rows.md", repo)] == [LATER]


def test_a_ticket_moved_onto_a_path_another_left_carries_its_own_sessions_alone(moved: tuple[Path, Path]) -> None:
    """A path one ticket left is not the ticket that moves into it: the arriving ticket brings the
    sessions from where it came and none of what the path held before."""
    root, repo = moved
    ticket(root / "duplicate-rule.md", "open")  # a ticket of its own, filed where nothing had been
    demo_commit(repo, LATER, "2026-09-20T09:00:00+02:00", "duplicate-rule: filed", "agent/tickets")
    demo_git(repo, "mv", "agent/tickets/duplicate-rule.md", "agent/tickets/name-columns.md")
    demo_git(repo, "commit", "-q", "-m", "duplicate-rule: renamed for the column it rules on")
    assert [s.id for s in ticket_sessions(root / "name-columns.md", repo)] == [LATER], (
        "the sessions that worked on the ticket that was at this path until the grilling moved it"
    )


def test_a_commit_message_line_that_names_no_file_does_not_stop_the_walk(moved: tuple[Path, Path]) -> None:
    """What the log prints under a commit is its files, except where a trailer's value runs on to a
    line of its own, which git folds into the value and the format string prints as written."""
    root, repo = moved
    append(root / "header-row.md", "\nThe bank is asked for once.\n")
    demo_git(repo, "add", "--", "agent/tickets")
    demo_git(repo, "commit", "-q", "-m", "header-row: the bank is asked for once", "-m", f"Session: {LATER}\n  resumed")
    assert [s.id for s in ticket_sessions(root / "header-row.md", repo)] == [FILED, GRILLED, LATER]


def test_the_sessions_of_every_ticket_come_from_one_pass_over_the_repo(
    moved: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Following a move costs no git call per ticket: however many tickets the board lists, and
    however far each has moved, the log is read once."""
    root, repo = moved
    ran: list[str] = []
    real = board.git

    def counted(cwd: Path, *args: str) -> str:
        ran.append(args[0])
        return real(cwd, *args)

    monkeypatch.setattr(board, "git", counted)
    tickets = sorted(root.rglob("*.md"))
    assert len(tickets) == 2, "two tickets, so one call for both is a reading and not a coincidence"
    for path in tickets:
        ticket_sessions(path, repo)
    assert ran.count("log") == 1, ran


# ---- the state of a GitHub reference ---------------------------------------
# The spec's Decision: the board resolves every `gh` reference in one query per render, cached
# beside the board, and a link wears the state that comes back. The oracle is GitHub's GraphQL
# schema (a repository's issueOrPullRequest by number, a pull request's state, isDraft and
# reviewDecision) and the ticket's own sentence: a pull request is open, a draft, merged or
# waiting on changes, an issue open or closed.


def pull(number: int, state: str, draft: bool = False, review: str | None = None) -> dict:
    """A pull request as GitHub answers for one: the two states carry names of their own, since one
    response name cannot hold both enums (github.query)."""
    return {"__typename": "PullRequest", "number": number, "prState": state, "isDraft": draft, "reviewDecision": review}


def issue(number: int, state: str) -> dict:
    return {"__typename": "Issue", "number": number, "issueState": state}


# One answer holding a reference in every state the board tells apart, across two repositories.
ANSWERED = {
    "data": {
        "r0": {
            "nameWithOwner": "acme/backend",
            "n0": pull(1, "OPEN"),
            "n1": pull(2, "OPEN", draft=True),
            "n2": pull(3, "OPEN", review="CHANGES_REQUESTED"),
            "n3": pull(4, "MERGED", review="APPROVED"),
            "n4": pull(5, "CLOSED"),
            "n5": pull(8, "OPEN", draft=True, review="CHANGES_REQUESTED"),
            "n6": pull(317, "OPEN"),  # the build ticket the tracker fixture already carries
        },
        "r1": {
            "nameWithOwner": "acme/helix",
            "n0": issue(6, "OPEN"),
            "n1": issue(7, "CLOSED"),
            "n2": issue(412, "OPEN"),
        },
    }
}
# What the board should make of it, every reference the tracker names once `referenced` has run.
STATED = {
    "acme/backend#1": "pr-open",
    "acme/backend#2": "pr-draft",
    "acme/backend#3": "pr-changes",
    "acme/backend#4": "pr-merged",
    "acme/backend#5": "pr-closed",
    "acme/backend#8": "pr-draft",  # nothing has been asked of a pull request nobody was asked to review
    "acme/helix#6": "issue-open",
    "acme/helix#7": "issue-closed",
    "acme/backend#317": "pr-open",
    "acme/helix#412": "issue-open",
}


@pytest.fixture
def referenced(tracker: Path) -> Path:
    """The tracker with a ticket naming a reference in every state the board tells apart, beside
    the two its build ticket already names. It is a standalone ticket, which the main checkout is
    read for: a feature with a worktree is read from there (tracker_roots), and the repo fixture
    commits the tracker before this rewrites it."""
    ticket(tracker / "small-chore.md", "open", gh=[ref for ref in STATED if not ref.endswith(("#317", "#412"))])
    return tracker


def gh_answering(path_with: Callable[..., Path], answer: dict, said: str = "") -> Path:
    """A `gh` that answers every query with `answer`. Given `said`, it reports that on stderr and
    exits non-zero, as gh does with a request it considers failed."""
    # printf, a shell builtin, since this PATH holds only the tools the board reaches for itself
    spoken = f'printf "%s\\n" {shlex.quote(said)} >&2\nexit 1' if said else ""
    return path_with("gh", f"printf '%s' {shlex.quote(json.dumps(answer))}\n{spoken}")


def gh_marks(page: str) -> dict[str, tuple[str, str]]:
    """(the state it wears, the words it says on hover) of every GitHub link on the page, by
    reference."""
    return {
        "".join(text).strip(): (got["class"].split()[1], got["data-tip"])
        for mark, text, got in elements_of(page) if mark == "gh"
    }


def queries(record: Path) -> list[str]:
    """The GraphQL queries the render sent; an auth probe is not one."""
    return [r for r in runs(record) if "graphql" in r]


def stamp_of(page: str) -> str:
    """The stamp the open tab polls against, which moves when anything the page shows moves."""
    return re.search(r'<body data-stamp="([^"]*)"', page).group(1)


def test_a_reference_wears_the_state_github_gives_it_and_says_it_in_words(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """Every state the board tells apart, from one answer, and the words each says on hover: which
    of the two it is, and which state it is in."""
    gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(tracker_roots(referenced), repo, out)
    marks = gh_marks(out.read_text())
    assert {ref: state for ref, (state, _) in marks.items()} == STATED
    assert "merged" in marks["acme/backend#4"][1], "a merged pull request reads as merged without opening it"
    for ref, (state, tip) in marks.items():
        kind = "pull request" if state.startswith("pr-") else "issue"
        word = {"changes": "asked for changes"}.get(state.split("-", 1)[1], state.split("-", 1)[1])
        assert kind in tip and word in tip, f"{ref} is {state} and says {tip!r}"
    assert absences(out.read_text(), "github") == 0, "GitHub answered, so there is no absence to report"


def test_the_query_asks_for_the_two_states_under_names_of_their_own() -> None:
    """A pull request's state and an issue's are two different enums, and GraphQL refuses a node
    that selects both under the one response name, whatever the parent types.

    Validated against GitHub's published schema on 2026-09-23, which is how to redo it:

        curl -sfL -o /tmp/gh.graphql https://docs.github.com/public/fpt/schema.docs.graphql
        uv run --with graphql-core python -c "import github; from graphql import *; \
          print(validate(build_schema(open('/tmp/gh.graphql').read()), parse(github.query(['a/b#1']))))"
    """
    asked = github.query(["acme/backend#1"])
    assert not re.findall(r"(?<!: )\bstate\b", asked), f"{asked}: a state asked for under its own name merges the two enums"


def test_a_reference_written_in_another_case_wears_its_state_all_the_same(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """GitHub answers under the repository's canonical name; the row looks its reference up by the
    string its own file holds, and a repository name is the same name in any case."""
    ticket(referenced / "loose-idea.md", "proposed", gh=["ACME/Backend#4"])
    gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(tracker_roots(referenced), repo, out)
    assert gh_marks(out.read_text())["ACME/Backend#4"][0] == "pr-merged"


def test_one_query_per_render_resolves_every_reference_in_every_repository(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    record = gh_answering(path_with, ANSWERED)
    render(tracker_roots(referenced), repo, tmp_path / "board.html")
    (asked,) = queries(record)
    assert runs(record) == [asked], "one gh for the render, which is the query"
    assert 'repository(owner: "acme", name: "backend")' in asked
    assert 'repository(owner: "acme", name: "helix")' in asked
    assert asked.count("issueOrPullRequest") == len(STATED), "one field per reference, whichever of the two it is"


def test_an_answer_carrying_data_is_read_though_gh_calls_the_request_failed(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """A repository the account cannot see answers as null and makes gh exit non-zero, while the
    rest of the answer stands: those links stay bare, and the board asked and was answered, so the
    page has no absence to report."""
    partial = {"data": {"r0": ANSWERED["data"]["r0"], "r1": None}}
    gh_answering(path_with, partial, said="gh: Could not resolve to a Repository with the name 'acme/helix'.")
    out = tmp_path / "board.html"
    render(tracker_roots(referenced), repo, out)
    marks = gh_marks(out.read_text())
    assert marks["acme/backend#4"][0] == "pr-merged"
    assert [marks[ref][0] for ref in ("acme/helix#6", "acme/helix#7")] == ["unknown", "unknown"]
    assert marks["acme/helix#6"][1] == board.UNKNOWN_REF
    assert absences(out.read_text(), "github") == 0


def test_the_page_says_why_github_did_not_answer_in_ghs_own_words(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """An answer with no data in it is no answer: a token GitHub refuses, a network that is not
    there. What gh said is what the user has to fix, so the note carries it."""
    gh_answering(path_with, {"message": "Bad credentials", "status": "401"}, said="gh: Bad credentials (HTTP 401)")
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    page = out.read_text()
    assert absences(page, "github") == 1
    assert "Bad credentials" in page
    assert gh_marks(page)["acme/backend#317"] == ("unknown", board.UNKNOWN_REF)


def test_a_reference_filed_after_the_last_query_is_asked_about_at_once(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The cached answer serves the references it was asked about; a ticket filed with one it was
    not is worth the query it costs, rather than a window bare."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(tracker_roots(referenced), repo, out)
    ticket(referenced / "loose-idea.md", "proposed", gh=["acme/coding#9"])
    render(tracker_roots(referenced), repo, out)
    assert len(queries(record)) == 2
    assert queries(record)[1].count("issueOrPullRequest") == len(STATED) + 1


def test_an_answer_older_than_its_lifetime_is_asked_again(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The clock is what ages an answer, so the check moves the lifetime rather than the file: what
    the cache holds is the module's own business."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(tracker_roots(referenced), repo, out)
    monkeypatch.setattr(github, "LIFETIME", timedelta(0))
    render(tracker_roots(referenced), repo, out)
    assert len(queries(record)) == 2


def test_a_cached_answer_dresses_the_links_the_render_it_served_did_not_ask_about(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """What the cache is for: the second render shows every state the first one was told, and says
    nothing about an absence, having wanted nothing."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(tracker_roots(referenced), repo, out)
    first = out.read_text()
    render(tracker_roots(referenced), repo, out)
    assert len(queries(record)) == 1
    served = out.read_text()
    assert {ref: state for ref, (state, _) in gh_marks(served).items()} == STATED
    assert absences(served, "github") == 0
    assert stamp_of(served) == stamp_of(first), "the tab has nothing to reload for"


def test_a_tracker_that_changed_without_its_references_changing_asks_nothing(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The watcher's everyday render: a claim, a ruling, a brief rewritten, and the same references
    on the rows."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(tracker_roots(referenced), repo, out)
    ticket(referenced / "small-chore.md", "claimed", gh=[ref for ref in STATED if not ref.endswith(("#317", "#412"))])
    render(tracker_roots(referenced), repo, out)
    assert len(queries(record)) == 1
    assert 'class="ticket row-claimed" id="t-small-chore"' in out.read_text(), "the render did happen"


def test_a_tracker_naming_no_pull_request_or_issue_asks_nothing_and_says_nothing(
    tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """A board with no GitHub reference on it has no source to miss, as a tracker with no review
    page rendered has no server to miss. Its own tracker, since the fixture's build ticket names
    two references from the worktree its feature is read from."""
    record = gh_answering(path_with, ANSWERED)
    root = tmp_path / "repo" / "agent" / "tickets"
    (root / "solo").mkdir(parents=True)
    ticket(root / "solo" / "01-only.md", "open")
    repo = root.parent.parent
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tracker")
    render(tracker_roots(root), repo, tmp_path / "board.html")
    page = (tmp_path / "board.html").read_text()
    assert queries(record) == []
    assert absences(page, "github") == 0
    assert gh_marks(page) == {}


def test_a_cache_this_version_cannot_read_is_asked_past(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """A cache half-written by a killed render, or written by a board that held other fields: the
    render asks again rather than failing on it."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    github.cache_path(out).parent.mkdir(parents=True, exist_ok=True)
    github.cache_path(out).write_text('{"asked": "2026-09-23T')
    render(tracker_roots(referenced), repo, out)
    assert len(queries(record)) == 1
    assert gh_marks(out.read_text())["acme/backend#4"][0] == "pr-merged"


def test_a_gh_that_never_answers_leaves_the_render_to_go_on_without_it(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A render waits TIMEOUT for GitHub and no longer: a board that hung on a hung request would
    take its watcher with it."""
    monkeypatch.setattr(github, "TIMEOUT", 0.5)
    path_with("gh", "while :; do :; done")
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    page = out.read_text()
    assert absences(page, "github") == 1
    assert gh_marks(page)["acme/backend#317"][0] == "unknown"


def test_every_state_a_link_can_wear_has_a_look_of_its_own_on_the_page(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The ticket's "a link shows its state in its own look", at the page seam: the layout checks
    render without gh, so the styles the states wear are only visible here."""
    gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(tracker_roots(referenced), repo, out)
    style = out.read_text().split("<style>", 1)[1].split("</style>", 1)[0]
    looks = {state: re.findall(rf"\.gh\.{state}\b[^{{]*{{([^}}]*)}}", style) for state in github.SAYS}
    assert all(looks[state] for state in github.SAYS), f"states with no look of their own: {[s for s in looks if not looks[s]]}"
    assert len({tuple(rules) for rules in looks.values()}) >= 4, "the states would not be told apart on the page"


# ---- the board briefing ---------------------------------------------------
# The side column's head: what the session that writes it is given, what a change tells it, and
# what the board says before any session has written one. The oracle is the spec's Decisions under
# "The board briefing"; the Property on pings and retirement is test_briefing.py's.


@pytest.fixture
def ranked(tmp_path: Path) -> Path:
    """A tracker whose frontier separates the three things the fallback orders by: two tickets at
    one priority differing in what they unblock, two differing in the user's time, and one at a
    lower priority that unblocks more than any of them."""
    root = tmp_path / "repo" / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "hub.md", "open", priority=1, size="M", name="The hub")
    ticket(root / "quick.md", "open", priority=1, size="XS", name="The quick one")
    ticket(root / "slow.md", "open", priority=1, size="L", name="The slow one")
    ticket(root / "later.md", "open", priority=2, size="XS", name="The later one")
    ticket(root / "waits.md", "open", blocked_by=["hub", "later"], priority=1, size="XS", name="Waits on the hub")
    ticket(root / "waits-too.md", "open", blocked_by=["hub", "later"], priority=1, size="XS", name="Waits as well")
    ticket(root / "third.md", "open", blocked_by=["later"], priority=1, size="XS", name="Waits on the later one")
    ticket(root / "built.md", "review", priority=2, size="S", name="A build to rule on")
    ticket(root / "shape.md", "open", needs_user=True, priority=1, size="S", name="A shape to pick")
    ticket(root / "grill.md", "open", needs_user=True, priority=2, size="S", name="A shape to talk through")
    (root / "asked.md").write_text(
        "---\nstatus: open\npriority: 3\nsize: S\n---\n\n# Stopped on a word\n\n## Brief\n\nWhat it is, cold.\n\n"
        "## Questions\n\n- [D1] **Retry, or fake the clock?** Either way it is four seconds.\n"
    )
    return root


def briefing_of(page: str) -> str:
    """The briefing as the page carries it, markup and all."""
    return page.split('<div class="briefing"', 1)[1].split('<div class="ghead"', 1)[0]


def test_the_board_says_what_waits_on_the_user_until_a_session_writes_a_briefing(ranked: Path) -> None:
    """The spec's fallback: the counts the prototype's sentence gives, and no model behind them."""
    said = board.fallback(list(load(ranked).values()))
    assert said.startswith(
        "One build to rule on, one question wanting a word and two tickets wanting a session wait on you."
    ), f"both near tickets the user is in the loop for are counted: {said}"


def test_the_fallback_orders_the_next_picks_by_priority_then_what_they_unlock_then_your_time(ranked: Path) -> None:
    """Three picks, in the order the spec names: priority, then what accepting one unblocks, then
    the user's own time on it."""
    said = board.fallback(list(load(ranked).values()))
    picks = re.findall(r"^- \*\*(.+?)\*\*: (.+)$", said, re.MULTILINE)
    assert [name for name, _ in picks] == ["The hub", "The quick one", "A shape to pick"]
    assert picks[0][1] == "now · accepting it unblocks two · 1 h of yours"


def test_the_briefing_the_cache_holds_is_what_the_board_shows_with_the_time_it_was_written(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    out = tmp_path / "board.html"
    when = datetime.fromisoformat("2026-09-21T09:30:00+02:00")
    Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 2).write(cache_path(out))
    render(tracker_roots(tracker), repo, out)
    page = out.read_text()
    said = briefing_of(page)
    assert "Two builds wait on your ruling." in said
    assert "21 Sep 09:30" in said, "the board shows when the briefing was written"
    assert "waits on you." not in said, "the board's own count stands in only until a session writes one"
    assert absences(page, "model") == 0, "a briefing already written is no absence whatever the machine has now"
    # the mark's own words, which are what the user is told the cadence is (the every-mark-explains
    # -itself Property, disposed reviewed): the numbers are the schedule's own, the sentence is not
    tip = re.search(r'class="bwhen" title="([^"]*)"', page)
    assert tip and "status" in tip.group(1), "the hover words do not say that a status is what reaches the session"
    assert f"{QUIET.seconds // 60} minutes" in tip.group(1) and f"{CADENCE.seconds // 60} minutes" in tip.group(1), \
        "the hover words do not carry both windows"


def test_a_watched_board_re_renders_on_a_briefing_the_session_rewrote(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """A pass of the watcher that finds nothing under the tracker moved still has two things to look
    at, and this is one of them: the briefing lands minutes after the change that asked for it, on a
    tracker that has gone quiet since."""
    out = tmp_path / "board.html"
    watching, session = Seen(), board.Briefer(repo, out)
    watching = look(watching, session, tracker, repo, out)  # the first pass reads; main() rendered
    rendered = out.stat().st_mtime_ns if out.exists() else 0
    watching = look(watching, session, tracker, repo, out)
    assert (out.stat().st_mtime_ns if out.exists() else 0) == rendered, "nothing moved, nothing re-rendered"

    when = datetime.now().astimezone()
    Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 0).write(cache_path(out))
    look(watching, session, tracker, repo, out)
    assert out.stat().st_mtime_ns != rendered, "the briefing the session wrote never reached the page"
    assert "Two builds wait on your ruling." in briefing_of(out.read_text())


def test_a_watched_board_re_renders_on_a_change_under_the_tracker_and_tells_the_session_of_a_status(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The watcher's own reason to exist, which the pass above leaves out: a ticket file moves and
    the page follows it. Only a status moving is the session's business, though (the spec's
    Decisions under "The board briefing"): a ticket filed or retired is a status appearing or going,
    prose rewritten is a render and no more, and a status that goes back to what the session was
    last told leaves nothing to tell.

    Both halves of the tracker are moved, since `statuses` reads the features and the standalone
    tickets in two comprehensions and a board is mostly features."""
    out = tmp_path / "board.html"
    when = datetime.now().astimezone()  # a briefing already written, so the opening pass arms nothing
    Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 0).write(cache_path(out))
    render(tracker_roots(tracker), repo, out)  # as main() does before it starts watching
    watching, session = [Seen()], board.Briefer(repo, out)
    watching[0] = look(watching[0], session, tracker, repo, out)
    assert session.changed_at is None, "the opening pass has nothing to tell the session about"
    assert watching[0].statuses == render(tracker_roots(tracker), repo, out), \
        "the baseline the first pass read is not the tracker the board draws"

    chore = tracker / "new-chore.md"
    # the tree is read from the worktree on its parent ticket's branch, where a worker flips a status
    second = repo.parent / "wt" / "agent" / "tickets" / "second.md"
    assert status_moved(watching, session, tracker, repo, out, lambda: ticket(chore, "open")), \
        "the briefing session was never told a ticket was filed"
    assert "t-new-chore" in rows_of(out.read_text()), "the new row is not on the page it re-rendered"
    assert not status_moved(watching, session, tracker, repo, out,
                     lambda: ticket(chore, "open", brief="The `suite` is slow, and flaky with it.")), \
        "prose rewritten was sent to the session as a change"
    assert status_moved(watching, session, tracker, repo, out, lambda: ticket(second, "claimed", parent=TREE)), \
        "a ticket of the tree claimed was never sent to the session"
    assert status_moved(watching, session, tracker, repo, out, chore.unlink), \
        "a ticket retired was never sent to the session"


def test_a_status_that_goes_back_to_what_the_session_was_told_leaves_nothing_to_tell() -> None:
    """A ticket claimed and unclaimed inside one window: the board re-renders twice and the session
    is owed nothing, since what it holds is what the tracker says again. The other half of the same
    rule is that a pass where no status moved leaves the quiet window where it was, so prose
    rewritten every minute cannot hold a pending change open for ever."""
    at = datetime.now().astimezone()
    told = (("feat-a/02", "open"), ("small-chore", "open"))
    session = board.Briefer(Path("."), Path("board.html"), told=(), told_statuses=told)

    session.saw(claimed := (("feat-a/02", "claimed"), ("small-chore", "open")), told, at)
    assert session.changed_at == at, "a status that moved never started the quiet window"
    session.saw(claimed, claimed, at + timedelta(minutes=3))
    assert session.changed_at == at, "a pass that moved no status started the quiet window again"
    session.saw(told, claimed, at + timedelta(minutes=4))
    assert session.changed_at is None, "the tracker is back where the session left it, and it was told anyway"


def status_moved(
    watching: list[Seen], session: "board.Briefer", tracker: Path, repo: Path, out: Path, change: Callable[[], None]
) -> bool:
    """Make one change under the tracker, run a pass of the watcher over it, and answer whether the
    briefing session was told a status moved. The page is re-rendered either way, which is asserted
    here so that every caller reads as the one thing it is about."""
    rendered, told = out.stat().st_mtime_ns, session.changed_at
    change()
    watching[0] = look(watching[0], session, tracker, repo, out)
    assert out.stat().st_mtime_ns != rendered, "a change under the tracker never reached the page"
    return session.changed_at != told


def test_a_briefing_the_session_wrote_does_not_disarm_githubs_clock(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """Two slices share one `elif`: the briefing's re-render and GitHub's answer running out. Only
    the second is a render that asks GitHub again, so only it is done with the answer it asked
    about. A briefing landing inside the answer's lifetime that armed the clock would leave it
    armed against an answer no later render replaces, and a merged pull request would read as open
    on a quiet tracker for as long as the board watched it."""
    path_with("gh", 'echo "{}"')
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    watching, session = Seen(), board.Briefer(repo, out)
    watching = look(watching, session, tracker, repo, out)
    assert watching.asked, "the render before the watch asked GitHub about the references on the board"

    when = datetime.now().astimezone()
    Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 0).write(cache_path(out))
    watching = look(watching, session, tracker, repo, out)
    assert watching.armed is None, "the briefing's re-render took GitHub's answer as one it had asked about"
    assert run_out(watching.asked - github.LIFETIME, watching.armed), "so nothing would ever ask again"


def test_a_run_of_the_model_that_answers_nothing_reaches_the_open_tab(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The note says the briefing is the board's own count, and a tab reloads on the stamp alone.
    A run that answers nothing writes no cache file, so neither the stamp nor the watcher has
    anything to move with, and the note reaches the file and never the reader."""
    claude = path_with("claude", "echo '{}'")  # on the machine, and answering nothing
    out = tmp_path / "board.html"
    stamp = lambda: Path(str(out) + ".stamp.js").read_text()  # noqa: E731
    render(tracker_roots(tracker), repo, out)
    before = stamp()
    assert absences(out.read_text(), "model") == 0, "the model is here and nothing has failed yet"

    watching, session = Seen(), board.Briefer(repo, out)
    watching = look(watching, session, tracker, repo, out)  # the first pass starts the run
    assert session.running
    session.running.join(30)
    assert len(runs(claude)) == 1 and briefing.SILENT, "the run that answered nothing said nothing of itself"

    look(watching, session, tracker, repo, out)
    assert stamp() != before, "the open tab has no reason to reload"
    assert absences(out.read_text(), "model") == 1 and "it answered nothing" in out.read_text()


def test_a_quiet_pass_of_the_watcher_makes_no_model_call(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The Property at the seam that can fail it. A render has no path to the model at all, so the
    cost the Property is about is the watcher's, and it is only a cost once a session exists: the
    change that starts one is paid for, and every pass after it over a tracker that has not moved
    is the thing the Property forbids."""
    said = {"is_error": False, "session_id": "abc-123", "result": "Two builds wait on your ruling."}
    claude = path_with("claude", f"printf '%s\\n' {shlex.quote(json.dumps(said))}")
    out = tmp_path / "board.html"
    watching, session = Seen(), board.Briefer(repo, out)
    watching = look(watching, session, tracker, repo, out)  # the start is a change: one run is owed
    assert session.running
    session.running.join(30)
    assert len(runs(claude)) == 1

    for _ in range(3):
        watching = look(watching, session, tracker, repo, out)
        if session.running:
            session.running.join(30)
    assert len(runs(claude)) == 1, "an unchanged tracker has nothing to tell the briefing session"


def test_githubs_answer_arms_the_watchers_clock_once_per_answer() -> None:
    """The other thing a quiet pass looks at. An answer that has had its render is done with:
    a render that does not ask (a tracker that has stopped naming any reference) leaves the same
    answer behind, and a clock that read the file alone would re-render on it every two seconds."""
    old = datetime.now().astimezone() - github.LIFETIME - timedelta(seconds=1)
    assert run_out(old, None), "an answer past its lifetime is one the next render asks again"
    assert not run_out(old, old), "and having had that render, the same answer asks for no other"
    assert not run_out(datetime.now().astimezone(), None), "an answer still good asks for nothing"
    assert not run_out(None, None), "and a board that has asked nothing has no clock to run out"


def test_the_watcher_runs_the_model_once_a_cadence_and_keeps_what_it_was_told_until_it_answers(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The watcher's side of the schedule, driven a tick at a time with claude stubbed: the first
    change dispatches a run and its answer lands in the cache beside the board, a second change
    inside the windows dispatches nothing, and a run that answers nothing leaves the account of what
    moved for the retry to carry (briefing.on_change holds the schedule itself)."""
    said = {"is_error": False, "session_id": "abc-123", "result": "Two builds wait on your ruling."}
    claude = path_with("claude", f"printf '%s\\n' {shlex.quote(json.dumps(said))}")
    out, roots = tmp_path / "board.html", tracker_roots(tracker)
    at = datetime.now().astimezone()
    watcher = board.Briefer(repo, out)

    statuses = board.statuses(load_tickets(roots, board.Diffviews(roots.main.parent / "diffviews", None)))
    watcher.opened(tracker_snapshot(roots, repo), statuses, at)
    watcher.tick(roots, tracker_snapshot(roots, repo), statuses, at)
    watcher.running.join(30)
    assert len(runs(claude)) == 1, "the change the watcher opened on starts one run"
    written = Briefing.read(cache_path(out))
    assert written and (written.text, written.session, written.pings) == (said["result"], "abc-123", 0)
    told = watcher.told

    watcher.saw(statuses + (("feat-a/09", "open"),), statuses, at + timedelta(minutes=1))
    watcher.tick(roots, tracker_snapshot(roots, repo), statuses, at + timedelta(minutes=1))
    assert len(runs(claude)) == 1, "a change inside the quiet window waits it out"
    watcher.tick(roots, tracker_snapshot(roots, repo), statuses, at + QUIET + timedelta(minutes=1))
    assert len(runs(claude)) == 1, "a run inside the cadence of the last one is not tried again (Briefer.tried)"

    path_with("claude", "echo '{\"is_error\": true}'")  # a login that has lapsed, a run past its limit
    ticket(tracker / "small-chore.md", "done")
    # stamped while the session was exploring: a run's clock is read before it starts, so a change
    # landing during one reads as a change it has not heard, and the cadence after is when it does
    watcher.saw(statuses + (("small-chore", "done"),), statuses, written.last_activity + timedelta(seconds=1))
    watcher.tick(roots, tracker_snapshot(roots, repo), statuses, at + CADENCE + timedelta(seconds=1))
    watcher.running.join(30)
    assert len(runs(claude)) == 2, "a change the session has not heard is pinged out the cadence after it"
    assert f"--resume {written.session}" in runs(claude)[1], "the cadence's change started a fresh exploration"
    assert Briefing.read(cache_path(out)) == written, "a run that answered nothing writes nothing"
    assert watcher.told == told, "what the session was told about waits for the run that reaches it"

    # and the run that answered nothing is tried again a cadence later, not on every pass after it
    watcher.tick(roots, tracker_snapshot(roots, repo), statuses, at + CADENCE + timedelta(seconds=30))
    assert len(runs(claude)) == 2, "a run that answered nothing was retried on the next pass"
    watcher.tick(roots, tracker_snapshot(roots, repo), statuses, at + 2 * CADENCE + timedelta(seconds=2))
    watcher.running.join(30)
    assert len(runs(claude)) == 3, "a run that answered nothing was never retried"

    cache_path(out).unlink()  # and with no briefing to fall back on, the page says why there is none
    render(tracker_roots(tracker), repo, out)
    assert absences(out.read_text(), "model") == 1


def test_a_cache_file_the_board_cannot_read_leaves_it_the_boards_own_count(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The cache is written by a thread of its own while the board renders from it, and a version
    of the board older than the file that is there is the same case: neither is a render that
    fails."""
    out = tmp_path / "board.html"
    cache_path(out).write_text('{"text": "half a fi')
    render(tracker_roots(tracker), repo, out)
    assert "One build to rule on waits on you." in briefing_of(out.read_text())


def test_the_briefing_session_is_given_every_ticket_the_board_shows_and_the_file_to_read_it_in(demo: Demo) -> None:
    """What a fresh session starts from: the tracker as the board computes it, which is every row's
    marks, its brief, its open questions and the file the rest of it is in."""
    roots = tracker_roots(demo.root)
    state = board.briefing_state(roots, demo.repo)
    shown = load_tickets(tracker_roots(demo.root), Diffviews(demo.root, None))
    for t in shown:
        assert f"{t.slug} · {t.status} · " in state, f"{t.slug} is a row on the board and not a line of the state"
        assert str(t.path) in state, f"{t.slug} is given without the file to read the rest of it in"
    asked = [q.tag for t in shown for q in t.questions if not q.ruled]
    assert asked and all(f"asks: [{tag}]" in state for tag in asked)
    assert board.git_log(demo.repo).splitlines()[0] in state, "the commits behind the tracker"
    # one line in full, since what the session is handed is every mark the row wears and not only
    # the three above
    ticket = demo.root / "map-columns.md"
    assert (
        f"map-columns \u00b7 review \u00b7 to rule on \u00b7 p1 now \u00b7 1 h \u00b7 Map columns once per bank \u00b7 {ticket}\n"
        "  brief: You tell the importer once which column holds the date, the amount and the payee;"
        " it remembers that per bank and never asks again.\n"
        "  waits on: parse-rows\n"
    ) in state
    # the tickets are written out under the tree each is part of, the ones in no tree under their own
    assert "## alone\nexport-to-xlsx \u00b7 blocked \u00b7 build \u00b7 p4 later \u00b7 20 min \u00b7 Export to Excel \u00b7 " in state


def test_a_tracker_change_reaches_the_session_as_the_files_that_moved(tmp_path: Path) -> None:
    """What a ping tells the session. Its own copy of the demo tracker: this check moves files under
    it, and the shared fixture is read by every later check in this file and the next."""
    own = build_demo(tmp_path / "demo")
    roots = tracker_roots(own.root)
    before = tracker_snapshot(roots, own.repo)
    assert changed_note(before, before, own.repo) == "something under the tracker was touched without changing"

    ticket(own.root / "new-slice.md", "open", parent="csv-import")
    (own.root / "upgrade-python.md").unlink()
    faster = own.root / "speed-up-tests.md"
    faster.write_text(faster.read_text() + "\n## Questions\n\n- [D9] **Is the template rebuilt often enough?**\n")
    demo_commit(own.repo, S3, "2026-09-23T09:00:00+02:00", "tickets: a slice filed, a chore retired", "agent/tickets")
    note = changed_note(before, tracker_snapshot(roots, own.repo), own.repo)

    assert "new: agent/tickets/new-slice.md" in note
    assert "gone: agent/tickets/upgrade-python.md" in note
    assert "changed: agent/tickets/speed-up-tests.md" in note
    assert "the repo has moved on: " in note and "a slice filed, a chore retired" in note


# ---- properties -----------------------------------------------------------
# The executable Properties of agent/tickets/board-orients/spec.md that live at these seams.


def runs(record: Path) -> list[str]:
    """What the board ran a stub tool with, one line per run (the path_with fixture)."""
    return record.read_text().splitlines() if record.exists() else []


def absences(page: str, source: str) -> int:
    """How often the page says it did without `source` (board.absence_note)."""
    return page.count(f'data-absent="{source}"')


def rows_in(page: str, group: str) -> set[str]:
    """The ticket rows one of the board's groups holds."""
    body = page.split(f'id="grp-{group}"', 1)[1].split('class="grp" id="grp-', 1)[0]
    return set(re.findall(r'<details class="ticket [^"]*" id="([\w-]+)"', body))


def test_a_ticket_is_in_needs_me_exactly_when_it_waits_on_a_ruling_an_answer_or_a_session() -> None:
    """The whole space of what a ticket file can say, since it is small enough to enumerate.

    The reading the spec's sentence leaves open: "nobody has claimed" means open or proposed, since
    a blocked or done ticket is not the user's to sit for either.
    """
    space = itertools.product(
        sorted(TICKET_STATUSES | {"blocked"}), [False, True], [1, 2, 3, 4, 5], [False, True],
    )
    for status, needs_user, priority, open_question in space:
        waits = status != "done" and (
            status == "review"
            or open_question
            or (needs_user and priority in (1, 2) and status in ("open", "proposed"))
        )
        assert needs_me(status, needs_user, priority, open_question) is waits, (status, needs_user, priority, open_question)


PHRASE = st.lists(st.sampled_from("retry the clock suite upload mapping bank payee ledger".split()), min_size=2, max_size=6).map(" ".join)
HEADLINE = st.builds(lambda words, end: words + end, PHRASE, st.sampled_from("?.:"))
DETAIL = st.builds(lambda words, path: f"{words}, in {path}." if path else f"{words}.", PHRASE, st.sampled_from(["", "`src/mapping.py`", "`~/.config/ledger/mappings.toml`"]))
QUESTION = st.tuples(HEADLINE, DETAIL, st.one_of(st.none(), st.sampled_from(["2026-09-21", "2026-09-22"])))
# the first tag, since a ticket's Dn sequence runs on across its comment too and its questions need not open it
QUESTIONS = st.tuples(st.integers(min_value=1, max_value=4), st.lists(QUESTION, min_size=1, max_size=6))


def ticket_asking(first: int, items: list[tuple[str, str, str | None]]) -> str:
    """A ticket file whose `## Questions` holds `items`, some of them ruled, and whose closing
    comment carries tags of the same running sequence that are not questions."""
    asked = "\n".join(
        f"- [D{n}] **{headline}** {detail}" + (f"\n  - Ruled {ruled}: the answer, relayed." if ruled else "")
        for n, (headline, detail, ruled) in enumerate(items, start=first)
    )
    after = first + len(items)
    return (
        "---\nstatus: review\npriority: 1\nsize: S\n---\n\n# A ticket\n\n## Brief\n\nWhat it is, cold.\n\n"
        f"## Questions\n\n{asked}\n\n"
        "## Comments\n\nBuilt on its branch, not merged.\n\n"
        f"**Details, if you want them**\n\n- [D{after}] Assumptions\n  - A1 `src/mapping.py:1`: one mapping per bank.\n"
    )


@given(asked=QUESTIONS)
def test_a_question_a_ruled_line_answers_is_never_open(asked: tuple[int, list[tuple[str, str, str | None]]]) -> None:
    first, items = asked
    read = board.questions_of(ticket_asking(first, items), [])
    assert [q.tag for q in read] == [f"D{n}" for n in range(first, first + len(items))]
    assert [q.headline for q in read] == [headline for headline, _, _ in items]
    assert [q.ruled is None for q in read] == [ruled is None for _, _, ruled in items]
    assert all(detail in q.detail and "Ruled" not in q.detail for q, (_, detail, _) in zip(read, items))


# what the demo tracker's tickets ask of the user: the two builds in review, every ticket with a
# question no Ruled line answers, and the two near tickets the user is in the loop for, whose
# session is the work whether or not a question of theirs is open.
NEEDS_ME = {
    "t-map-columns", "t-view-storage", "t-view-list-shape", "t-flaky-upload-test",
    "t-pick-a-date-library", "t-retire-legacy-exporter", "t-speed-up-tests", "t-staging-credentials",
}


def test_the_needs_me_group_holds_exactly_the_tickets_that_wait_on_the_user(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The same two properties as the checks above, at the seam the spec's Testing seams names: a
    fixture tracker on disk in, groups out. map-columns keeps its questions on its ticket branch,
    so the board has to read them there."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    assert rows_in(out.read_text(), "needs") == NEEDS_ME
    assert "t-read-the-bank-formats" not in rows_in(out.read_text(), "needs"), "a worker's ticket with nothing open"


def test_every_session_listed_on_a_ticket_has_a_transcript_on_this_machine(demo: Demo) -> None:
    path = demo.root / "map-columns.md"
    listed = ticket_sessions(path, demo.repo, demo.transcripts)
    assert {s.id for s in listed} <= set(demo.sessions)
    assert [s.id for s in listed] == [S1, S2], "the sessions that committed on it, oldest first; the worker S4 is on another host"
    assert [s.title for s in listed] == [demo.sessions[s.id]["title"] for s in listed]
    assert [s.cwd for s in listed] == [demo.sessions[s.id]["cwd"] for s in listed]


def test_the_board_renders_with_no_transcripts_and_says_the_absence_once(demo: Demo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_with: Callable[..., Path]) -> None:
    monkeypatch.setattr(board, "TRANSCRIPTS", tmp_path / "no-transcripts")
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    page = out.read_text()
    assert absences(page, "transcripts") == 1
    assert S1 not in page and S4 not in page, "no session is resumable without a transcript"


def test_the_board_renders_without_github_and_says_the_absence_once(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    page = out.read_text()
    assert absences(page, "github") == 1
    assert "acme/backend#317" in page, "the references stay on the row, bare"


def test_the_board_renders_without_the_model_and_says_the_absence_once(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    assert absences(out.read_text(), "model") == 1


def test_the_board_renders_with_no_review_page_server_and_says_the_absence_once(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "quoted.html").write_text("<html>")
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    page = out.read_text()
    assert f'href="file://{dv / "quoted.html"}"' in page, "the pages stay linked, as the files they are"
    assert absences(page, "review-page-server") == 1


def test_a_board_whose_review_pages_are_served_says_no_absence(tracker: Path, stub_diffview: Path) -> None:
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "quoted.html").write_text("<html>")
    diffviews = serve_diffviews(dv)
    page = render_page("demo", load_tickets(Roots(tracker, []), diffviews), log="", stamp="s", stamp_src="s.js")
    assert f'href="{STUB_ADDRESS}/quoted.html"' in page
    assert absences(page, "review-page-server") == 0


def test_a_tracker_with_no_review_pages_rendered_says_nothing_about_the_server(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """Nothing has been sent for review yet, so there is no page a server could be answering for:
    the absence the Property names is the server for pages that exist."""
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    assert absences(out.read_text(), "review-page-server") == 0


def test_a_done_blocker_is_the_same_dashed_context_in_a_tree_and_out_of_one(tmp_path: Path) -> None:
    """The whole tracker's graph draws a done ticket a live one waits on as its dashed context. A
    ticket in no tree is one of those: dropping it takes the edge with it, and a reader looking at
    the graph to see what a ticket rests on gets a complete answer for one and silence for the
    other."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "ledger.md", "open")
    ticket(root / "waits-on-a-chore.md", "open", parent="ledger", blocked_by=["done-chore"])
    ticket(root / "waits-on-a-tree.md", "open", parent="ledger", blocked_by=["landed"])
    # a second waiter on the same done chore, since the list of waits holds one entry per waiter
    ticket(root / "waits-on-it-too.md", "open", parent="ledger", blocked_by=["done-chore"])
    ticket(root / "other.md", "open")
    ticket(root / "landed.md", "done", parent="other")
    ticket(root / "done-chore.md", "done")
    parts = board_graph(list(load(root).values()))
    assert parts, "nothing waits on anything"
    lines = [line for part in parts["trees"] for node in part["nodes"] for line in node["lines"]]
    ghosts = [line for line in lines if ":::ghost" in line]
    assert len(ghosts) == 2, f"a done blocker is drawn twice, or one kind of it is not drawn: {ghosts}"
    drawn = [edge["line"].strip() for edge in parts["edges"]]
    assert len(drawn) == len(set(drawn)) == 3, f"an edge into a done blocker was dropped or doubled: {drawn}"


def test_what_a_ticket_unblocks_is_counted_once_per_ticket_that_waits_on_it(tmp_path: Path) -> None:
    """The count behind the briefing's next picks and the graph's edges are the same edges, or the
    page contradicts itself."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "hub.md", "open")
    ticket(root / "the-hub.md", "open", parent="hub")
    ticket(root / "dep.md", "open")
    ticket(root / "waits-first.md", "open", parent="dep", blocked_by=["the-hub"])
    ticket(root / "waits-second.md", "open", parent="dep", blocked_by=["the-hub"])
    ticket(root / "waits-alone.md", "open", blocked_by=["the-hub"])  # a ticket in no tree waits too
    read = list(load(root).values())
    said = board.fallback(read)
    assert "accepting it unblocks three" in said, f"the waiters counted apart in the picks: {said}"
    parts = board_graph(read)
    assert parts and len(parts["edges"]) == 3, "and the graph drew edges the count does not agree with"


def test_a_render_writes_nothing_beside_the_board_that_says_anything_about_a_ticket(
    demo: Demo, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The second half of the reviewed Property "the board keeps no side file about a ticket". A
    render writes two files beside the page, a content hash and GitHub's own answer keyed by the
    reference it was asked about; the briefing's cache is the session's thread's. None of them says
    anything a ticket file says, and the next cache added beside the board is what this names."""
    out = tmp_path / "beside" / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    beside = sorted(p.name for p in out.parent.iterdir())
    assert beside == ["board.html", "board.html.github.json", "board.html.stamp.js"]
    rows = load_tickets(tracker_roots(demo.root), Diffviews(demo.root, None))
    about = [str(t.path) for t in rows] + [t.title for t in rows] + [t.brief for t in rows if t.brief]
    about += [q.tag for t in rows for q in t.questions]
    for sidecar in beside[1:]:
        held = (out.parent / sidecar).read_text()
        assert not any(said in held for said in about), f"{sidecar} says something about a ticket"


def test_a_render_that_finds_nothing_changed_makes_no_github_request(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    gh = path_with("gh", 'echo "{}"')
    out = tmp_path / "board.html"
    queries = lambda: [r for r in runs(gh) if "graphql" in r]  # noqa: E731  an auth probe is not a request for a reference
    render(tracker_roots(tracker), repo, out)
    assert len(queries()) == 1, "one query per render resolves both references"
    render(tracker_roots(tracker), repo, out)
    assert len(queries()) == 1, "the answer cached beside the board serves the unchanged render"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
