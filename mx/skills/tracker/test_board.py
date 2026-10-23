# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown", "markdown-it-py[linkify]"]
# ///
"""Checks for the board's reading of a tracker. Run: uv run test_board.py

Four seams: the tracker loader (a fixture tracker on disk in, ticket state out), the graph
sources (which tickets become nodes, in which class, joined by which edges), the board's values
(`board.view`: the groups, and each row with its marks, its questions, its copy buttons and the
blocks it reads as opened; `board.read`: what a render reads, GitHub and the briefing included),
and, for the few checks that say they pin it, the page's markup itself: what the page's script and
stylesheet read. The oracle is the tracker skill, the board's --help and the docstrings beside the
code that draws the page: the frontier is open, unblocked, unclaimed; a proposed ticket is not
open whatever blocks it; a build in review waits for the user's ruling in its own group and
unblocks nothing until the accept writes done, save a sibling merged into the branch of the parent
ticket the two share; a gh reference is a link to GitHub; a row copies the absolute path
of the file it was read from; a review page is linked relative to the page, as every link on it
is; a reference whose file no longer exists counts as done; a graph draws only tickets with an
edge; one tracker directory holds every ticket the board shows, a build in flight included; a
ticket the tracker's own parser refuses is refused here, with its file and its line.

The watcher is checked at its pass (`look`, `turn`), its loop (`watch`) and its restart's
hand-over, and, as a full-path check, run as a process on a copy of its code changed under it.

Under "properties" at the end sit the executable Properties of
mx/skills/tracker/corpus/board-orients.md that belong to these seams; that spec is their oracle.
"""

import functools
import html
import http.server
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import board
import tracker as tracker_module
from board import (
    ALONE,
    STATUS_SYMBOL,
    Reading,
    Seen,
    board_graph,
    changed_note,
    content_stamp,
    load_tickets,
    look,
    mark,
    render,
    render_page,
    run_out,
    ticket_sessions,
    tracker_snapshot,
    tree_graph,
)
import briefing
import github
from briefing import CADENCE, QUIET, Briefing, cache_path
from demo_tracker import S1, S2, S3, S4, Demo, build as build_demo
from demo_tracker import commit as demo_commit, git as demo_git, transcript as write_transcript

TREE = "lamp-ui"  # a hyphen, so a slugged id and the raw slug can be told apart


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
    """A flat tracker: one tree of seven tickets under `lamp-ui`, and three tickets in no tree."""
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
def listening() -> Iterator[str]:
    """An address something listens on, as a live diffview server does."""
    with socket.create_server(("127.0.0.1", 0)) as server:
        yield f"http://127.0.0.1:{server.getsockname()[1]}"


@pytest.fixture
def stub_diffview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Path]:
    """A diffview that records its arguments and answers as the real one does on --serve, naming
    the address it is given; calling it writes the stub and returns it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if git := shutil.which("git"):  # the repo the board reads what merged in, as conftest.KEPT keeps it
        (bin_dir / "git").symlink_to(git)
    monkeypatch.setenv("PATH", str(bin_dir))

    def stub(address: str) -> Path:
        script = bin_dir / "diffview"
        script.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "$0.args"\n'
            f'echo "diffview: serving $2 at {address}/"\n'
        )
        script.chmod(0o755)
        return script

    return stub


def load(root: Path, repo: Path | None = None) -> dict[str, board.Ticket]:
    """The tracker as the board reads it, by slug, its links written from the tracker's directory."""
    return {t.slug: t for t in load_tickets(root, repo, root.parent)}


def view_of(root: Path, repo: Path | None = None) -> board.View:
    """The board's values for the tracker at `root`, with no answer from GitHub."""
    return board.view(load_tickets(root, repo, root.parent))


def page_of(root: Path) -> str:
    """The page itself, for the checks that pin its markup."""
    return render_page(Reading("demo", load_tickets(root, None, root.parent), ""), stamp="s", stamp_src="s.js")


def rows_in(seen: board.View, group: str) -> set[str]:
    """The slugs of the rows one of the board's groups holds, and not of the rows folded under them."""
    return {r.ticket.slug for g in seen.groups if g.state == group for r in g.rows}


def anywhere_in(seen: board.View, group: str) -> set[str]:
    """Every row inside one of the board's groups, the rows folded under another included."""
    return {one.ticket.slug for g in seen.groups if g.state == group for r in g.rows for one in board.with_kids(r)}


def labels(row: board.Row) -> list[str | None]:
    """The word over each block of an opened ticket, in the order the reader meets them."""
    return [b.label for b in row.ticket.blocks]


def block(row: board.Row, label: str) -> board.Block | None:
    """The block of an opened ticket under `label`, None where it has none."""
    return next((b for b in row.ticket.blocks if b.label == label), None)


def asked(row: board.Row) -> list[dict[str, str]]:
    """Every question an opened ticket carries, as the parts it shows of each."""
    held = block(row, "questions")
    return [
        {part: said for part, said in (("tag", q.tag), ("head", q.headline), ("detail", q.detail), ("ruling", q.ruling)) if said}
        for q in (held.asked if held else ())
    ]


def copies(seen: board.View) -> list[board.Copy]:
    """Every copy button on the board: the groups', each row's under its name, and the ones of the
    blocks each row reads as opened."""
    found = [g.copy for g in seen.groups if g.copy]
    for r in seen.rows.values():
        found += [q.copy for q in r.questions] + ([r.copy_all] if r.copy_all else [])
        found += row_copies(r)
    return found


def row_copies(row: board.Row) -> list[board.Copy]:
    """The copy buttons of the blocks a row reads as opened, in the order it shows them."""
    return [one for b in row.ticket.blocks for one in (
        [q.copy for q in b.asked if q.copy] + [s.resume for s in b.worked] + [a.run for a in b.artefacts if a.run]
    )]


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


def test_a_blocker_the_board_cannot_see_counts_as_done(tracker: Path) -> None:
    """The tracker refuses a dangling edge where it is written, so an edge the board cannot resolve
    names a ticket in a checkout this render does not hold: the work it waits on has landed."""
    read = load(tracker)
    assert read["needs-chore"].status == "blocked"
    assert read["needs-chore"].blocked_by == [("small-chore", "open")]
    del read["small-chore"]
    assert board.ref_status("small-chore", {slug: (t, None) for slug, t in read.items()}) == "done"


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
    assert [(p.tree, p.graph) for p in board.view(read).pills] == [("solo", None)]


def test_a_proposed_ticket_is_a_node_in_its_own_class_once_something_waits_on_it(tracker: Path) -> None:
    graph = tree_graph(list(load(tracker).values()), TREE)
    assert 'faster suite"]:::proposed' in graph
    assert "T_f_second --> T_f_faster_suite" in graph and "T_f_faster_suite --> T_f_uses_fast_suite" in graph
    assert 'click T_f_faster_suite "#t-faster-suite"' in graph


def test_the_whole_tracker_graph_is_parts_per_tree_with_edges_naming_both_ends(tracker: Path) -> None:
    read = list(load(tracker).values())
    parts = board_graph(read)
    assert [f["name"] for f in parts["trees"]] == [TREE, ALONE], "the order the pills take"
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


# ---- the board's values ----------------------------------------------------


def test_the_board_groups_rows_by_state_needs_me_first_and_done_folded(tracker: Path) -> None:
    """A build waiting for the ruling is the user's to act on, so it sits in needs me; the group a
    row sits in says its status, and the done group is folded."""
    seen = view_of(tracker)
    assert [(g.state, g.label, len(g.rows), g.folded) for g in seen.groups] == [
        ("needs", "needs me", 1, False), ("open", "frontier", 5, False), ("blocked", "blocked", 2, False),
        ("proposed", "proposed", 2, False), ("done", "done", 1, True),
    ]
    assert rows_in(seen, "needs") == {"built"}
    assert rows_in(seen, "proposed") == {"faster-suite", "loose-idea"}


def test_the_page_writes_each_group_as_a_fold_of_its_own(tracker: Path) -> None:
    """Pins the format: the page's script and its group keys find a group by its id, and the page
    opens folded what the board folds."""
    page = page_of(tracker)
    assert re.findall(r'id="grp-(\w+)"', page) == ["needs", "open", "blocked", "proposed", "done", "log"]
    assert '<details class="grp" id="grp-done" data-state="done"><summary>' in page
    assert '<details class="grp" id="grp-open" data-state="open" open>' in page


def test_a_trees_pill_carries_its_counts_in_words(tracker: Path) -> None:
    pills = {p.tree: p for p in view_of(tracker).pills}
    assert (pills[TREE].says, pills[TREE].done, pills[TREE].total) == (
        "1/8 done · 3 open · 1 review · 2 blocked · 1 proposed", 1, 8,
    )
    assert (pills[ALONE].done, pills[ALONE].total) == (0, 3)


def test_the_lone_tickets_pill_comes_last_and_carries_a_graph_of_its_own(tracker: Path) -> None:
    """The pills are what the `1`…`9` keys index into, so their order is the one `trees_of` gives;
    and the tickets in no tree wait on each other like any others, so that pill has a graph."""
    pills = view_of(tracker).pills
    assert [p.tree for p in pills] == [TREE, ALONE]
    assert "T_f_quoted" in pills[-1].graph, f"the lone tickets have no graph of their own: {pills[-1].graph}"
    assert "T_f_second" not in pills[-1].graph, f"another tree's rows are drawn in it: {pills[-1].graph}"


def test_a_trees_pill_marks_when_any_of_its_tickets_waits_on_the_user(tmp_path: Path) -> None:
    """The mark reads the needs-me group, so a ticket stopped on a question lights it as much as a
    build in review does; the counts beside it already say how many tickets the tree has."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    only = root / "only.md"
    ticket(root / "solo.md", "done")
    ticket(only, "review", parent="solo")
    (solo,) = view_of(root).pills
    assert (solo.says, solo.waits) == ("1/2 done · 1 review", True)

    ticket(only, "claimed", parent="solo")  # the case a status alone cannot tell: in hand, and waiting on an answer
    only.write_text(only.read_text() + "\n## Questions\n\n- [D1] **Per bank or per file?** Neither is free.\n")
    (solo,) = view_of(root).pills
    assert (solo.says, solo.waits) == ("1/2 done · 1 claimed", True)

    ticket(only, "claimed", parent="solo")  # the same ticket with nothing asked of the user
    (solo,) = view_of(root).pills
    assert (solo.says, solo.waits) == ("1/2 done · 1 claimed", False)


def test_a_row_is_found_by_the_words_it_shows_lower_cased(tracker: Path) -> None:
    """The filter matches what the reader typed against the row's own words, its opened blocks'
    included, with the markup gone."""
    rows = view_of(tracker).rows
    assert rows["faster-suite"].search == "faster-suite faster suite what to build cut from the worker's closing comment on first: the suite is slow."
    assert rows["quoted"].search.startswith('quoted say "no limit" plainly')


def test_a_gh_reference_is_a_link_on_the_row_and_in_its_search_text(tracker: Path) -> None:
    ticket(tracker / "quoted.md", "open", blocked_by=["first"], gh=["acme/coding#137"], name='Say "no limit" plainly')
    rows = view_of(tracker).rows
    assert [(m.shows, m.href, m.look, m.says) for m in rows["built"].marks if m.kind == "gh"] == [
        ("acme/backend#317", "https://github.com/acme/backend/issues/317", "unknown", board.UNKNOWN_REF),
        ("acme/helix#412", "https://github.com/acme/helix/issues/412", "unknown", board.UNKNOWN_REF),
    ]
    assert mark(rows["quoted"], "gh").href == "https://github.com/acme/coding/issues/137"
    assert "acme/backend#317 acme/helix#412" in rows["built"].search
    assert "acme/coding#137" in rows["quoted"].search


def test_a_row_carries_what_the_page_script_matches_against_the_graphs(tracker: Path) -> None:
    """Pins the format: the script hides rows by the pill's raw tree name, filters on data-search
    with String.includes, and marks the node T_f_<slug> in the graph container of the row's tree."""
    read = list(load(tracker).values())
    page = page_of(tracker)
    in_tree = [t for t in read if t.tree == TREE]
    assert page.count(f'data-tree="{TREE}"') == 1 + len(in_tree) + 1  # chip, rows, graph container
    rows = re.findall(r'<details class="ticket row-\w+" id="([\w-]+)" data-tree="([\w-]*)" data-slug="([^"]+)" data-search="([^"]*)"', page)
    assert len(rows) == len(read)
    searches = {row_id: html.unescape(search) for row_id, _, _, search in rows}  # the script reads the attribute unescaped
    assert searches == {f"t-{slug}": row.search for slug, row in view_of(tracker).rows.items()}
    graph = re.search(rf'<div class="g" data-tree="{TREE}" hidden><pre class="mermaid" data-key="g:{TREE}">(.*?)</pre>', page, re.S).group(1)
    for row_id, tree, slug, _ in rows:
        if tree == TREE and slug in ("second", "faster-suite", "uses-fast-suite", "after-first", "first", "built"):
            assert f"T_f_{slug.replace('-', '_')}[" in graph, row_id
    assert '<div class="g" data-tree="*" hidden><pre class="mermaid" data-key="g:*"></pre>' in page
    assert '"id": "T_b_quoted"' in page


def test_a_row_links_its_review_page(tracker: Path) -> None:
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "second.html").write_text("<html>")
    (dv / "quoted.html").write_text("<html>")
    rows = view_of(tracker).rows
    assert mark(rows["second"], "rp").href == "diffviews/second.html", "from agent/board.html, the page beside it"
    assert mark(rows["quoted"], "rp").href == "diffviews/quoted.html"
    assert sum(m.kind == "rp" for r in rows.values() for m in r.marks) == 2  # once per row (the spec's Decisions)


def test_a_board_written_elsewhere_links_its_review_page_from_where_it_is(tracker: Path, tmp_path: Path) -> None:
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "second.html").write_text("<html>")
    rows = {t.slug: t for t in load_tickets(tracker, None, tmp_path / "boards")}
    assert rows["second"].diffview == "../repo/agent/diffviews/second.html"


# ---- opening it served ----------------------------------------------------


def test_board_opens_the_page_at_the_address_the_server_over_the_agent_repo_answers_on(
    tracker: Path, stub_diffview: Callable[[str], Path], listening: str,
) -> None:
    """One server over the whole agent repo, so the board and every page it links share it."""
    agent = tracker.parent
    stub = stub_diffview(listening)
    assert board.served(agent, agent / "board.html") == f"{listening}/board.html"
    assert Path(f"{stub}.args").read_text().split() == ["--serve", str(agent)]


def test_board_opens_the_file_where_no_diffview_is_installed(tracker: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools"))
    assert board.served(tracker.parent, tracker.parent / "board.html") is None


def test_board_opens_the_file_where_the_server_does_not_answer(
    tracker: Path, stub_diffview: Callable[[str], Path],
) -> None:
    """diffview printed an address, and nothing listens there."""
    stub_diffview(f"http://127.0.0.1:{free_port()}")
    assert board.served(tracker.parent, tracker.parent / "board.html") is None


def test_a_page_written_outside_the_agent_repo_opens_as_the_file_and_starts_no_server(
    tracker: Path, tmp_path: Path, stub_diffview: Callable[[str], Path], listening: str,
) -> None:
    stub = stub_diffview(listening)
    assert board.served(tracker.parent, tmp_path / "board.html") is None
    assert not Path(f"{stub}.args").exists()


def test_the_watcher_brings_back_a_server_that_exited_and_leaves_one_that_answers(
    tracker: Path, stub_diffview: Callable[[str], Path], listening: str,
) -> None:
    agent, out = tracker.parent, tracker.parent / "board.html"
    stub = stub_diffview(listening)
    assert board.kept(agent, out, f"{listening}/board.html") == f"{listening}/board.html"
    assert not Path(f"{stub}.args").exists(), "a server that answers is left alone"
    gone = f"http://127.0.0.1:{free_port()}/board.html"
    assert board.kept(agent, out, gone) == f"{listening}/board.html"
    assert Path(f"{stub}.args").read_text().split() == ["--serve", str(agent)]


def test_a_server_that_does_not_come_back_leaves_the_watcher_nothing_to_keep(
    tracker: Path, stub_diffview: Callable[[str], Path],
) -> None:
    """What the watcher backs off on: the page's address and the one diffview names are both dead."""
    stub_diffview(f"http://127.0.0.1:{free_port()}")
    gone = f"http://127.0.0.1:{free_port()}/board.html"
    assert board.kept(tracker.parent, tracker.parent / "board.html", gone) is None


def test_every_board_carries_the_note_a_served_page_shows_when_its_server_stops_answering(tracker: Path) -> None:
    """Pins the format: the page's script shows the note it finds by its source, once its polls go
    unanswered."""
    page = page_of(tracker)
    assert page.count('data-absent="board-server"') == 1
    assert '<p class="absent" data-absent="board-server" hidden>' in page


def free_port() -> int:
    """A port nothing listens on: bound, read, and let go."""
    with socket.create_server(("127.0.0.1", 0)) as server:
        return server.getsockname()[1]


def test_the_graph_draws_every_status_in_the_house_ink(tracker: Path) -> None:
    """The graph's colours are baked into the SVG by mermaid, so the page hands it one classDef per
    status, each named by house tokens the stylesheet declares as a light and a dark pair. The ink
    is read back out of the script it is handed to, where a build in review is drawn in the accent
    on its wash, and a proposal and a context node with a dashed edge, a proposal's the longer."""
    declared = {prop.removeprefix("--") for selectors, said in style_rules(board.STYLE) if ":root" in selectors
                for prop, value in said.items() if value.startswith("light-dark(")}
    assert set(board.GRAPH_INK) == {*STATUS_SYMBOL, "ghost"}, "a status the graph draws with no ink of its own"
    handed = json.loads(re.search(r"classDefs = Object\.entries\((\{.*?\})\)", page_of(tracker)).group(1))
    assert handed["review"] == ["wash", "accent", "strong", ""], "a build in review stands out from the rest of the graph"
    assert (handed["proposed"][3], handed["ghost"][3]) == ("4 3", "2 3"), "a proposal and a context node lose their dashes"
    assert {status for status, ink in handed.items() if ink[3]} == {"proposed", "ghost"}
    for status, (fill, stroke, text, _) in board.GRAPH_INK.items():
        assert {fill, stroke, text} <= declared, f"{status} is drawn in {sorted({fill, stroke, text} - declared)}, which the stylesheet does not declare"


def hrefs(seen: board.View) -> list[str]:
    """Every link the rows write: their marks', the session pages', the artefacts', and the ones a
    ticket's own prose carries, which reach the values rendered."""
    found = [m.href for r in seen.rows.values() for m in r.marks if m.href]
    for r in seen.rows.values():
        for b in r.ticket.blocks:
            found += [s.page for s in b.worked if s.page] + [a.href for a in b.artefacts]
            found += [html.unescape(ref) for ref in re.findall(r'href="([^"]*)"', b.prose)]
    return found


def to_files(links: list[str]) -> list[str]:
    """The links to a file of the tracker's: neither an anchor on the page nor another site."""
    return [ref for ref in links if not ref.startswith("#") and not urllib.parse.urlsplit(ref).scheme]


def test_a_rendered_board_links_nothing_by_a_file_or_a_loopback_address(
    transcribed: Demo, tmp_path: Path, stub_diffview: Callable[[str], Path], listening: str,
) -> None:
    """P5 of the dotfiles ticket agent-boards-on-phone: the board is read from a mirror on another
    host, where a file:// link or the laptop's 127.0.0.1 is dead. A diffview answering on this
    machine changes nothing the render writes."""
    stub_diffview(listening)
    reading = board.read(transcribed.root, transcribed.repo, tmp_path / "board.html")
    written = hrefs(board.view(reading.tickets, reading.gh))
    assert to_files(written), "the demo tracker's board links its review pages and artefacts"
    assert [ref for ref in written if ref.startswith("file:") or "127.0.0.1" in ref] == []


def test_served_from_the_agent_repo_every_link_on_the_demo_board_opens(tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """The mirror serves the agent repo as a plain directory, as `python -m http.server` does: every
    review page, artefact and session page the board links has to answer there, and as a file
    beside the page."""
    demo = build_demo(tmp_path / "demo")
    monkeypatch.setattr(board, "TRANSCRIPTS", demo.transcripts)
    agent = demo.root.parent
    reading = board.read(demo.root, demo.repo, agent / "board.html")
    linked = to_files(hrefs(board.view(reading.tickets, reading.gh)))
    assert {ref.split("/")[0] for ref in linked} >= {"diffviews", "show", "sessions"}
    assert [ref for ref in linked if not (agent / urllib.parse.unquote(ref)).is_file()] == []
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(agent))
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        page = f"http://127.0.0.1:{server.server_address[1]}/board.html"
        try:
            dead = [ref for ref in linked if urllib.request.urlopen(urllib.parse.urljoin(page, ref), timeout=5).status != 200]
        finally:
            server.shutdown()
    assert dead == []


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
    """The tracker committed on main, in the checkout it is read from."""
    repo = tracker.parent.parent
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tracker")
    return repo


def test_the_watcher_notices_the_project_moving_under_a_tracker_that_did_not(tracker: Path) -> None:
    """The page's commit list is the project's, so a merge there that touches no ticket has to
    re-render it; the tracker's own repo is the agent one, which a ticket commit moves instead."""
    code, agent = tracker.parent.parent, tracker.parent
    for at in (code, agent):
        git(at, "init", "-q", "-b", "main")
        git(at, "config", "user.email", "checks@example.com")
        git(at, "config", "user.name", "checks")
    (code / ".gitignore").write_text("/agent/\n")
    (code / "src.txt").write_text("the lamp\n")
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "the lamp")
    git(agent, "add", "-A")
    git(agent, "commit", "-q", "-m", "the tracker")

    before = tracker_snapshot(tracker, agent)
    (code / "src.txt").write_text("the lamp, rewired\n")
    git(code, "commit", "-q", "-am", "rewired")
    after = tracker_snapshot(tracker, agent)
    assert after != before, "a commit in the project the board's log comes from"
    assert "the repo has moved on: " in changed_note(before, after, code)


# ---- what the root holds --------------------------------------------------


def test_markdown_at_the_tracker_root_that_no_reader_can_read_is_refused_by_the_render(
    repo: Path, tracker: Path, tmp_path: Path,
) -> None:
    """The tracker root holds tickets and nothing else: a note left beside them is refused where it
    sits, rather than rendered as half a row."""
    (tracker / "needs-human.md").write_text("# Needs human\n\n- rule on loose-idea :: built while proposed\n")
    with pytest.raises(tracker_module.Refused, match=r"needs-human\.md:1: no frontmatter"):
        render(tracker, repo, tmp_path / "out" / "board.html")


def test_an_unblocked_proposal_is_claimable_and_still_waits_for_its_ruling(tracker: Path) -> None:
    """The live case: a proposal an agent filed with nothing blocking it (`/mx:tracker`)."""
    ticket(tracker / "render-check.md", "proposed", parent=TREE)
    read = load(tracker)
    assert read["render-check"].status == "proposed"
    assert read["render-check"].blocked_by == []
    assert "render-check" in rows_in(view_of(tracker), "proposed")


# ---- rows ------------------------------------------------------------------
# The marks' words come from the spec, not from board.py: these literals are the spec's own
# ("The ticket file": XS under 15 min ... XL several sessions; priority 1 to 5 named now, next,
# soon, later, someday; "The board": what the row asks is one of four words).
SIZE_WORDS = {"XS": ("15 min", "under 15 min"), "S": ("20 min", "about 20 min"), "M": ("1 h", "about an hour"),
              "L": ("half a day", "half a day"), "XL": ("several sessions", "several sessions")}
PRIORITY_WORDS = {1: "now", 2: "next", 3: "soon", 4: "later", 5: "someday"}
ASK_WORDS = {"review": "to rule on", "answer": "your answer", "session": "with you", "build": "build", "triage": "to triage", "whole": "with parent"}
# Every kind of mark a row wears. The demo tracker has a row wearing each, which is what makes the
# check below catch a mark a later slice adds rather than skip it.
KINDS = {"tree", "slug", "asks", "time", "pri", "chip", "rp", "gh", "kin"}


def test_a_rows_marks_are_read_from_the_ticket_file(tmp_path: Path) -> None:
    """The spec's Decisions on the ticket file: priority and size in frontmatter, the H1 as the
    short name, the brief from `## Brief`. A brief with nothing under it leaves the row without
    one rather than inventing one; the priority and the size every ticket declares, so no row is
    ever without those."""
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
    row = view_of(root).rows["map-columns"]
    assert (mark(row, "time").shows, mark(row, "pri").shows) == ("1 h", "p1 now")
    assert all("You tell the importer" not in b.prose for b in row.ticket.blocks), "the brief has one home, and it is the row"
    # the brief is searchable, since the filter is how a reader narrows to a word they remember
    assert "which column holds the date" in row.search


def test_a_priority_or_size_the_tracker_does_not_know_is_refused_with_the_file_and_the_line(tracker: Path) -> None:
    ticket(tracker / "second.md", "open", parent=TREE, priority=9)
    with pytest.raises(tracker_module.Refused, match=r"second\.md:\d+: `priority: 9` is none of"):
        load(tracker)
    ticket(tracker / "second.md", "open", parent=TREE, size="HUGE")
    with pytest.raises(tracker_module.Refused, match=r"second\.md:\d+: `size: HUGE` is none of"):
        load(tracker)


def test_every_size_and_priority_shows_the_word_the_spec_gives_it(tmp_path: Path) -> None:
    """Five sizes and five priorities, each on a row of its own: the words the user reads are the
    spec's, and the mark's own definition of itself stays in step with the word it shows."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    for i, size in enumerate(SIZE_WORDS, start=1):
        ticket(root / f"sized-{i}.md", "open", size=size, priority=i)
    rows = view_of(root).rows
    for i, (size, (word, means)) in enumerate(SIZE_WORDS.items(), start=1):
        time, priority = mark(rows[f"sized-{i}"], "time"), mark(rows[f"sized-{i}"], "pri")
        assert time.shows == word, f"{size} reads {time.shows!r}"
        assert priority.shows == f"p{i} {PRIORITY_WORDS[i]}"
        assert f"{size} {means}" in time.says, f"the time's words leave {size} out"
        assert f"p{i} {PRIORITY_WORDS[i]}:" in priority.says, f"the priority's words leave p{i} out"


def style_rules(sheet: str) -> list[tuple[list[str], dict[str, str]]]:
    """A stylesheet as rules, each its selectors and its declarations, comments dropped and an
    @media block's rules read as any other's: what the style says, not how it is laid out."""
    sheet = re.sub(r"/\*.*?\*/", "", sheet, flags=re.S)
    return [
        ([one.strip() for one in selectors.split(",")],
         {prop.strip(): value.strip() for prop, _, value in (d.partition(":") for d in body.split(";")) if value})
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", sheet)
    ]


def test_a_rows_fixed_columns_are_as_wide_as_the_marks_that_land_in_them(tmp_path: Path) -> None:
    """The name and the brief take what the row has spare, so a column is measured from the marks:
    the closed vocabularies for what a row asks, the time and the priority, the tracker's own names
    and references for the tree, the slug and the blockers, and each group's own three, since a group
    of quick unblocked tickets has no use for the width an XL one needs."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "ledger.md", "open", priority=1, size="S")
    ticket(root / "quick.md", "review", parent="ledger", priority=2, size="S")
    ticket(root / "long-haul.md", "open", parent="ledger", priority=5, size="XL", blocked_by=["quick"])
    ticket(root / "waits-on-the-haul.md", "open", priority=3, size="M", blocked_by=["long-haul"])
    widths = board.columns(view_of(root))
    assert widths["#grp-needs"] == {"time": len("20 min"), "pri": len("p2 next"), "chips": 0}
    assert widths[":root"] == {
        "tree": len("ledger"),  # the one tree's slug
        "slug": len("waits-on-the-h"),  # the longest slug, capped at the column's width
        "asks": len("your answer"),  # the widest of the spec's four words
        "time": len("several sessions"),
        "pri": len("p5 someday"),
        "chips": len("long-haul"),
    }
    # the group whose only ticket is an S at p2 with nothing waiting on it (above) leaves the rest of
    # that width to the name and the brief, until an XL is folded under a row of it: a folded row's
    # marks land in the group's columns too
    ticket(root / "month.md", "review", priority=2, size="S")
    ticket(root / "month-part.md", "review", parent="month", priority=2, size="XL")
    assert board.columns(view_of(root))["#grp-needs"] == {"pri": len("p2 next"), "chips": 0}
    # the group holding the XL ticket and the widest reference narrows none of the three
    assert "#grp-blocked" not in widths, f"the blocked group narrows {widths.get('#grp-blocked')}, though its rows are the widest of each"


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
    (frontier,) = view_of(root).groups
    assert [r.ticket.slug for r in frontier.rows] == [
        "quick-p1", "middling-p1", "slow-p1", "quick-p2", "a-chore", "slowest-p5",
    ]


def test_the_stamp_the_open_tab_polls_moves_when_a_link_changes_state(tracker: Path) -> None:
    """A merge on GitHub moves nothing under the tracker, and the open tab has to hear about it."""
    read = list(load(tracker).values())
    stamps = [
        content_stamp(Reading("demo", read, "", gh))
        for gh in (github.NOTHING,
                   github.Answer({"acme/backend#317": "pr-open"}),
                   github.Answer({"acme/backend#317": "pr-merged"}),
                   github.Answer({}, "GitHub did not answer"))
    ]
    assert len(set(stamps)) == len(stamps)


def test_the_stamp_the_open_tab_polls_moves_when_a_ticket_is_reprioritised(tracker: Path) -> None:
    """An edit the page shows but the ticket's status does not: the open tab reloads on it or it
    never arrives."""
    before = content_stamp(Reading("demo", list(load(tracker).values()), ""))
    ticket(tracker / "second.md", "open", parent=TREE, priority=1, size="XS", brief="Why it matters, cold.")
    assert content_stamp(Reading("demo", list(load(tracker).values()), "")) != before


def test_the_stamp_the_open_tab_polls_moves_on_every_mark_a_row_shows(tracker: Path) -> None:
    """An edit that moves what a row says and not its status: the open tab reloads on it or it never
    arrives. One example per field the stamp carries that the status does not."""
    edits = {
        "needs-user": lambda: ticket(tracker / "second.md", "open", parent=TREE, needs_user=True),
        "parent": lambda: ticket(tracker / "second.md", "open"),
        "title": lambda: ticket(tracker / "second.md", "open", parent=TREE, name="Another name"),
        "blocked-by": lambda: ticket(tracker / "second.md", "open", parent=TREE, blocked_by=["small-chore"]),
    }
    was = (tracker / "second.md").read_text()
    for field, edit in edits.items():
        before = content_stamp(Reading("demo", list(load(tracker).values()), ""))
        edit()
        assert content_stamp(Reading("demo", list(load(tracker).values()), "")) != before, f"{field} moved and the stamp did not"
        (tracker / "second.md").write_text(was)


def test_the_stamp_the_open_tab_polls_moves_when_the_session_rewrites_the_briefing(tracker: Path) -> None:
    """The briefing is the other thing on the page that moves with no file under the tracker moving,
    and the open tab polls the stamp: an unmoved stamp is a briefing nobody ever reads."""
    read = list(load(tracker).values())
    when = datetime.fromisoformat("2026-09-21T09:30:00+02:00")
    stamps = [
        content_stamp(Reading("demo", read, "", github.NOTHING, said))
        for said in (None,
                     Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 0),
                     Briefing("One build waits on your ruling.", when, "abc-123", when, when, 1),
                     Briefing("Two builds wait on your ruling.", when + timedelta(hours=1), "abc-123", when, when, 1))
    ]
    assert len(set(stamps)) == len(stamps)


def test_what_each_row_asks_of_the_user_comes_from_its_ticket_file(demo: Demo) -> None:
    """The spec's four words, each against the fixture ticket that earns it: a build in review asks
    for a ruling; a ticket the user is in the loop for asks for the session the user sits in,
    whether or not its question is written down; a ticket a worker takes is stopped by an open
    question of its own and asks for the answer; one with no question asks nothing of the user.
    A proposed ticket asks for the triage the user starts, since no worker takes it before one."""
    rows = view_of(demo.root, demo.repo).rows
    expected = {
        "map-columns": "review",  # status: review, a build waiting on a ruling
        "speed-up-tests": "review",
        "retire-legacy-exporter": "session",  # needs-user, and its open question is that session
        "view-list-shape": "session",
        "staging-credentials": "session",  # needs-user, and its one question is ruled
        "read-the-bank-formats": "build",  # nothing open on it, and no worker is kept from it
        "flaky-upload-test": "answer",  # a build stopped on a question of its own
        "pick-a-date-library": "answer",  # a worker's ticket, stopped on a question
        "view-storage": "answer",
        "parse-rows": "build",  # no question, not in review, and the user is not in the loop
        "import-report": "triage",  # proposed, so off the frontier until a triage promotes it
        "tidy-cli-help": "triage",
    }
    for slug, kind in expected.items():
        asks = mark(rows[slug], "asks")
        assert (asks.shows, asks.look) == (ASK_WORDS[kind], kind), f"{slug} asks {asks.shows!r}, not {ASK_WORDS[kind]!r}"


def test_every_mark_on_the_page_says_its_own_words_on_hover() -> None:
    """Pins the format, the page's half of P2: whatever its kind, a mark shows its words and carries
    what it says it means as its hover words, which the page paints (test_board_layout.py)."""
    for kind in board.MARK_HTML:
        written = board.mark_html(board.Mark(kind, "p1 now", "What this mark means, in words.", look="x", href="#t-x"))
        assert 'data-tip="What this mark means, in words."' in written and ">p1 now<" in written, f"the {kind} mark: {written}"


def test_p2_every_mark_a_row_carries_says_in_four_words_or_more_what_it_means(demo: Demo) -> None:
    """`board-reads-rows-as-values#P2`, over the demo tracker's rows: every mark says what it means,
    and says it about itself, and so does the headline of every question a row lists. That the
    words then paint on hover is the layout check's (test_board_layout.py)."""
    rows = view_of(demo.root, demo.repo).rows
    worn = set()
    for slug, row in rows.items():
        for m in row.marks:
            worn.add(m.kind)
            assert len(m.says.split()) >= 4, f"{slug}: the {m.kind} mark {m.shows!r} says {m.says!r}"
        for q in row.questions:
            assert len(q.says.split()) >= 4, f"{slug}: {q.tag} says {q.says!r} of itself"
    assert worn == KINDS, f"the demo tracker has no row wearing {sorted(KINDS - worn)}, or one wearing a kind this check has never seen"
    # each mark's words are about that mark: the time's say whose time it is, the priority's who set it
    row = rows["map-columns"]
    assert "never the agent's" in mark(row, "time").says and "priority" not in mark(row, "time").says
    assert "an agent's reading" in mark(row, "pri").says and "Your time" not in mark(row, "pri").says
    assert "review page" in mark(row, "rp").says and "GitHub" in mark(row, "gh").says
    assert str(demo.root / "map-columns.md") in mark(row, "slug").says, "a copy button shows what it copies"
    assert "top-level ticket" in mark(row, "tree").says
    # a blocker says which ticket it waits on and whether that one is done (spec, The board)
    said = {(m.shows, m.says) for r in rows.values() for m in r.marks if m.kind == "chip"}
    assert {("parse-rows", "Waits on parse-rows, done."), ("map-columns", "Waits on map-columns, not done yet."),
            ("commit-import", "Waits on commit-import, not done yet.")} <= said


def test_the_page_writes_every_mark_and_question_a_row_carries(demo: Demo) -> None:
    """The demo tracker's rows as the page writes them: every mark a row carries, and the button of
    every question it lists, is on the row's element, in the form the format checks above pin."""
    for slug, row in view_of(demo.root, demo.repo).rows.items():
        written = board.row_html(row)
        for m in row.marks:
            assert board.mark_html(m) in written, f"{slug}: the page drops its {m.kind} mark {m.shows!r}"
        for c in [q.copy for q in row.questions] + ([row.copy_all] if row.copy_all else []):
            assert board.copy_html(c) in written, f"{slug}: the page drops the {c.kind} button copying {c.shows!r}"


# ---- questions and the needs-me group -------------------------------------
# The spec's Decisions on `## Questions` and on the board: every question lives on its ticket,
# shows under its row in the one needs-me group while that row is folded, and is copyable one at a
# time, per ticket, or all at once, each button saying what it will copy.


def test_a_needs_me_row_lists_the_questions_its_ticket_file_asks_and_no_ruled_one(demo: Demo) -> None:
    """The fixture's build stopped on two questions, of which a `Ruled` line answered one."""
    rows = view_of(demo.root, demo.repo).rows
    row = rows["flaky-upload-test"]
    assert [(q.tag, q.headline) for q in row.questions] == [("D1", "Retry the upload, or fake the clock?")], "D2 is ruled, and a ruled question is answered"
    written = f"{demo.root / 'flaky-upload-test.md'}\n- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing."
    assert [q.copy.text for q in row.questions] == [written]
    assert row.copy_all is None, "one question needs no copy-all beside it"
    # the ticket with three of them has one, and it copies all three under the one path
    three = rows["map-columns"]
    assert three.copy_all.text.splitlines() == [str(demo.root / "map-columns.md")] + [
        line for q in three.questions for line in q.copy.text.splitlines()[1:]
    ]


def test_a_build_in_review_shows_the_questions_and_the_closing_comment_its_report_brought_in(demo: Demo) -> None:
    """Both are in the tracker's own copy from the moment the build waits for a ruling: the import
    is what puts them there, and the branch carries the code alone."""
    on_branch = demo_git(demo.repo, "show", "ticket/map-columns:agent/tickets/map-columns.md")
    assert "## Questions" not in on_branch and "## Comments" not in on_branch
    row = view_of(demo.root, demo.repo).rows["map-columns"]
    assert [q.tag for q in row.questions] == ["D1", "D2", "D3"]
    assert row.questions[0].headline == "Remember the mapping per bank or per file name?"
    assert "<code>~/.config/ledger/mappings.toml</code>" in row.questions[2].headline, "a headline's own code and emphasis render on the row"
    assert "The mapping step is built and remembers a bank" in block(row, "comments").prose, "the closing comment, folded under the row"
    # the row cuts a headline to its column, so the question's own words are what the hover carries
    assert row.questions[0].says.startswith("Remember the mapping per bank or per file name?")
    assert "Per bank asks one more question on the first import" in row.questions[0].says, "the detail the row has no room for"
    copied = [q.copy for q in row.questions] + [row.copy_all] + row_copies(row)
    assert "[D4]" not in "".join(c.text for c in copied), "the tags a closing comment carries are not questions"


def test_a_build_in_flight_is_on_the_board_from_the_trackers_own_directory(tmp_path: Path) -> None:
    """One writer, one directory: the claim and the review flip are committed in the tracker's own
    checkout, and the worker's words reach it through the import, so the board reads no branch and
    no worktree. A worktree left on a ticket branch holds whatever it holds."""
    root = tmp_path / "repo" / "agent" / "tickets"
    root.mkdir(parents=True)
    repo = root.parent.parent
    path = root / "map-columns.md"
    ticket(path, "claimed", priority=1, size="S")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tracker")
    git(repo, "worktree", "add", "-q", str(tmp_path / "wt"), "-b", "ticket/map-columns")
    stale = tmp_path / "wt" / "agent" / "tickets" / "map-columns.md"
    stale.write_text(stale.read_text().replace("status: claimed", "status: review") + STALE)
    git(tmp_path / "wt", "commit", "-q", "-am", "a worker that wrote a ticket file")

    before = tracker_snapshot(root, repo)
    seen = view_of(root, repo)
    assert seen.rows["map-columns"].questions == (), "no question of the branch's reaches the board"
    assert rows_in(seen, "needs") == set(), "nothing waits on the user: the tracker says the build is claimed"

    # the import, as `dispatch review` makes it: in the tracker's own copy
    path.write_text(path.read_text().replace("status: claimed", "status: review") + STALE)
    assert tracker_snapshot(root, repo) != before, "a watching board renders the import"
    seen = view_of(root, repo)
    assert rows_in(seen, "needs") == {"map-columns"}
    assert [(q.tag, q.headline) for q in seen.rows["map-columns"].questions] == [("D1", "Per bank or per file name?")]


def test_the_board_renders_the_agent_repo_its_project_holds(tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """A project is a code repo with its `agent/` a repo of its own inside it: `board` run anywhere
    in the code repo renders that tracker, names the page after the code repo, and reads its commit
    log from there, while the tickets and the sessions that wrote them come from the agent repo.
    It reads the page `main` writes, so the tab's title pins the format."""
    code = tmp_path / "lamp"
    tickets = code / "agent" / "tickets"
    tickets.mkdir(parents=True)
    (code / "src").mkdir()
    ticket(tickets / "map-columns.md", "claimed", priority=1, size="S", name="Map columns once per bank")
    for at in (code, code / "agent"):
        git(at.parent, "init", "-q", "-b", "main", str(at))
    (code / ".gitignore").write_text("/agent/\n")
    (code / "src" / "importer.py").write_text("the importer\n")
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "the importer reads a bank export")
    git(code / "agent", "add", "-A")
    git(code / "agent", "commit", "-q", "-m", "map-columns: filed")

    assert board.find_tracker(code / "src") == tickets, "found from anywhere in the code repo"
    assert board.find_tracker(code / "agent") == tickets, "and from inside the agent repo"

    out = tmp_path / "board.html"
    board.main(board.Args(tickets_root=tickets, out=out, open=False, watch=False))
    page = out.read_text()
    assert "Map columns once per bank" in page
    assert "<title>board — lamp</title>" in page, "the project's name is the code repo's, on the browser's tab"
    assert "the importer reads a bank export" in page, "and its log is the code repo's"
    assert "map-columns: filed" not in page, "not the agent repo's, which is the tickets' own history"


def test_a_project_whose_agent_directory_is_not_a_repo_yet_still_renders(
    tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The state a project is in before the split: one repo holding both. The board reads it rather
    than dying on a checkout that is not there."""
    code = tmp_path / "lamp"
    tickets = code / "agent" / "tickets"
    tickets.mkdir(parents=True)
    ticket(tickets / "map-columns.md", "open", priority=1, size="S", name="Map columns once per bank")
    git(code.parent, "init", "-q", "-b", "main", str(code))
    git(code, "add", "-A")
    git(code, "commit", "-q", "-m", "the project, tracker and all")
    board.main(board.Args(tickets_root=tickets, out=tmp_path / "board.html", open=False, watch=False))
    page = (tmp_path / "board.html").read_text()
    assert "Map columns once per bank" in page and "the project, tracker and all" in page


STALE = """
## Questions

- [D1] **Per bank or per file name?** A bank renames its export.

## Comments

Built, not merged.
"""


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
    seen = view_of(root)
    assert rows_in(seen, "needs") == {"soon"}
    assert seen.rows["shipped"].questions == (), "a question left on a done ticket is a leftover, not a call"
    assert copies(seen) == [], "the done group grew a copy-all for a question no row on the board shows"


def test_p1_every_copy_button_a_row_carries_shows_what_it_copies(transcribed: Demo) -> None:
    """`board-reads-rows-as-values#P1`, over the demo tracker's rows: the words a button shows on
    hover are what its click puts on the clipboard, cut off only where they run long.

    The tracker is the one with its transcripts where this machine keeps its own, since the button
    that copies a resume command is only made for a session the board can name, and a check that
    read the tracker without them would hold the Property for four kinds of button out of five."""
    seen = view_of(transcribed.root, transcribed.repo)
    found = copies(seen)
    assert {c.kind for c in found} == {"qcopy", "qall", "qgroup", "runcopy", "resume"}
    for c in found:
        assert len(c.does.split()) >= 4 and "copy" in c.does, f"the {c.kind} button says {c.does!r} of the click"
        assert c.shows, f"the {c.kind} button shows nothing of what it copies"
        if c.shows.endswith("…"):  # a button whose text runs long shows the start of it and says so
            assert c.text.startswith(c.shows[:-1]) and len(c.shows) > 120, f"the {c.kind} button shows {c.shows!r}"
            assert len(c.shows) <= 260, f"the {c.kind} button spills {len(c.shows)} characters into the row"
        else:
            assert c.shows == c.text, f"the {c.kind} button shows {c.shows!r} and copies {c.text!r}"
        # the note the page shows once a click has landed names what it landed, in the terms that
        # button's own text is in: the file for the ones that copy a path or a command on it, a
        # count for the board's worth of questions, the session for the one that copies a resume
        if c.kind == "qgroup":
            assert c.note == f"{sum(line.startswith('- [D') for line in c.text.splitlines())} questions"
        elif c.kind == "resume":
            assert c.note.removeprefix("the command resuming ") not in ("", c.note)
        else:
            assert c.text.splitlines()[0].rsplit("/", 1)[-1] in c.note, f"the {c.kind} button's note says {c.note!r}"
    # the copy button the row already had says the same of itself (02-rows)
    assert str(transcribed.root / "flaky-upload-test.md") in mark(seen.rows["flaky-upload-test"], "slug").says


def test_a_copy_button_carries_what_it_copies_and_what_it_shows_onto_the_page() -> None:
    """Pins the format: the page's script copies `data-copy` and says `data-copied` once it has,
    and the hover paints `data-tip`, which is what the click does over what it shows of what it
    copies: all of it under the cap, the start of it past."""
    short = board.Copy("qcopy", "copy", "Click to copy this question.", "agent/tickets/a.md\n- [D1] **A & B?**", "D1 of a.md")
    assert board.copy_html(short) == (
        '<span class="copier qcopy" data-copy="agent/tickets/a.md\n- [D1] **A &amp; B?**" data-copied="D1 of a.md" '
        'data-tip="Click to copy this question.\n\nagent/tickets/a.md\n- [D1] **A &amp; B?**">copy</span>'
    )
    long = board.Copy("resume", "copy resume", "Click to copy the command.", "cd " + "a" * 300, "the command")
    assert board.copy_html(long) == (
        f'<span class="copier resume" data-copy="cd {"a" * 300}" data-copied="the command" '
        f'data-tip="Click to copy the command.\n\ncd {"a" * 217}\u2026">copy resume</span>'
    )


def test_the_needs_me_groups_copy_button_holds_every_open_question_under_its_tickets_path(demo: Demo) -> None:
    """What the user pastes into an editor to answer a board's worth of questions at once."""
    seen = view_of(demo.root, demo.repo)
    assert [g.state for g in seen.groups if g.copy] == ["needs"]
    (text,) = [g.copy.text for g in seen.groups if g.copy]
    blocks = [one.splitlines() for one in text.split("\n\n")]
    assert {lines[0] for lines in blocks} == {
        str(demo.root / name) for name in [
            "map-columns.md", "view-storage.md", "view-list-shape.md", "flaky-upload-test.md",
            "pick-a-date-library.md", "retire-legacy-exporter.md", "speed-up-tests.md", "carry-balances.md",
        ]
    }
    asked = [line for lines in blocks for line in lines[1:]]
    assert len(asked) == 12 and all(line.startswith("- [D") for line in asked)
    assert any("Remember the mapping per bank" in line for line in asked), "a build in review asks its own"
    # the file's own markdown, so a question pastes back into the ticket as it was written
    assert "- [D3] **The mappings live in `~/.config/ledger/mappings.toml`.** Fine there, or beside the ledger file so they travel with it?" in asked
    assert not any("Whose card does the sandbox go on" in line for line in asked), "a ruled question is answered"


# ---- an opened ticket ------------------------------------------------------
# The spec's Decisions on an opened ticket: blocks, not a wall of text, in one order, reading the
# artefacts from the ticket's show directory and folding the comments away as history.


def put(path: Path, text: str, runs: bool = False) -> None:
    """A file under a directory that may not exist yet: an artefact beside a ticket, executable
    where it is one that runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if runs:
        path.chmod(path.stat().st_mode | 0o111)


def made(row: board.Row) -> list[tuple[str, str, str]]:
    """What an opened ticket lists as its artefacts, in order: the words of each link, where it
    points, and the command its button copies, empty for a file that does not run."""
    held = block(row, "artefacts")
    return [(a.name, a.href, a.run.text if a.run else "") for a in (held.artefacts if held else ())]


def test_an_opened_ticket_reads_as_blocks_in_one_order(transcribed: Demo) -> None:
    """The build in review, which has one of every block: its questions, the sessions that worked
    on it, its artefacts, then its own sections as the file writes them, the comments last."""
    row = view_of(transcribed.root, transcribed.repo).rows["map-columns"]
    assert labels(row) == [
        "questions", "sessions on this machine", "artefacts", "what to build", "acceptance criteria", "comments",
    ]
    # the brief is the row's own: read before anything is opened, and written once
    assert "You tell the importer once" in row.ticket.brief
    assert all("You tell the importer once" not in b.prose for b in row.ticket.blocks)


def test_an_opened_ticket_carries_every_question_with_its_detail_and_the_ruling_on_it(demo: Demo) -> None:
    """The row shows the open headlines; the ticket shows all of them, the detail it had no room
    for, and what the user ruled on the ones that are answered."""
    row = view_of(demo.root, demo.repo).rows["flaky-upload-test"]
    assert asked(row) == [
        {"tag": "D1", "head": "Retry the upload, or fake the clock?",
         "detail": "A retry hides a real slowdown; a fake clock makes the test say nothing about timing."},
        {"tag": "D2", "head": "Keep the test in the fast suite?",
         "detail": "It takes four seconds with either fix.",
         "ruling": "Ruled 2026-09-21: keep it in the fast suite."},
    ]
    assert [q.tag for q in row.questions] == ["D1"], "the row lists the open one and no more"


def test_an_opened_ticket_copies_each_open_question_where_the_folded_row_does(demo: Demo) -> None:
    """An opened row lists its questions once: the list under the name goes (the page's style) and
    the block carries the same buttons beside the detail, copying the same line under the same
    path. The row's copy-all goes with the list it copies."""
    rows = view_of(demo.root, demo.repo).rows
    row = rows["flaky-upload-test"]
    written = (f"{demo.root / 'flaky-upload-test.md'}\n- [D1] **Retry the upload, or fake the clock?**"
               " A retry hides a real slowdown; a fake clock makes the test say nothing about timing.")
    assert [c.text for c in row_copies(row)] == [written], "the question as the file writes it, under its path"
    assert row_copies(row) == [q.copy for q in row.questions], "the same button, and none on the question a ruling answered"
    three = rows["map-columns"]
    assert [c.kind for c in row_copies(three)] == ["qcopy", "qcopy", "qcopy", "runcopy"]
    assert row_copies(three)[:3] == [q.copy for q in three.questions], "a question is copied the same way wherever the button for it sits"
    assert three.copy_all.kind == "qall"


def test_a_blocked_rows_questions_carry_the_same_buttons_in_both_places(tmp_path: Path) -> None:
    """A ticket's blocks are made from the status its file declares, and the board derives
    `blocked` from its blockers afterwards; the row and the block read the two. They have to agree
    on which questions carry a copy button, which they do while only a done ticket loses them."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "store.md", "open", priority=1, size="S")
    ticket(root / "waiting.md", "open", blocked_by=["store"], priority=1, size="S")
    waiting = root / "waiting.md"
    waiting.write_text(waiting.read_text() + "\n## Questions\n\n- [D1] **Which store?** The one that travels.\n")
    row = view_of(root).rows["waiting"]
    assert row.ticket.status == "blocked", "the fixture no longer exercises a derived status"
    assert [c.text for c in row_copies(row)] == [f"{waiting}\n- [D1] **Which store?** The one that travels."]
    assert row_copies(row) == [q.copy for q in row.questions], "the two readings of the status disagree"


def test_a_tickets_artefacts_are_read_from_its_show_directory(demo: Demo) -> None:
    """Every file in it as a link, and the one that runs on a button that copies the command
    running it from the repo root. Nothing in the ticket declares either: the directory is read."""
    rows = view_of(demo.root, demo.repo).rows
    assert made(rows["map-columns"]) == [
        ("mapping.svg", "show/map-columns/mapping.svg", ""),
        ("walkthrough", "show/map-columns/walkthrough", "agent/show/map-columns/walkthrough"),
    ]
    # every show directory is its ticket's slug's own, beside the tracker the ticket was read from
    assert made(rows["speed-up-tests"]) == [
        ("timings", "show/speed-up-tests/timings", "agent/show/speed-up-tests/timings"),
    ]
    assert "artefacts" not in labels(rows["flaky-upload-test"]), "nothing has been built on it yet"


def test_what_a_show_directory_offers_an_opened_ticket(tmp_path: Path) -> None:
    """Every file under it keeps the path that names it, a file that runs carries the command and
    one that does not carries none, and what a run regenerates under out/ is no artefact. Nothing
    names a show directory's files, so a name with a space in it is one a paste has to survive."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "map-columns.md", "review")
    ticket(root / "view-list.md", "open")
    show = tmp_path / "agent" / "show"
    put(show / "map-columns" / "walkthrough", "#!/bin/sh\necho two imports\n", runs=True)
    put(show / "map-columns" / "render sample", "#!/bin/sh\necho a sample\n", runs=True)
    put(show / "map-columns" / "shots" / "mapping.svg", "<svg/>")
    put(show / "map-columns" / "out" / "frame-01.png", "generated")
    put(show / "view-list" / "layouts.svg", "<svg/>")
    rows = view_of(root).rows
    assert made(rows["map-columns"]) == [
        ("render sample", "show/map-columns/render%20sample", "'agent/show/map-columns/render sample'"),
        ("shots/mapping.svg", "show/map-columns/shots/mapping.svg", ""),
        ("walkthrough", "show/map-columns/walkthrough", "agent/show/map-columns/walkthrough"),
    ]
    assert made(rows["view-list"]) == [
        ("layouts.svg", "show/view-list/layouts.svg", ""),
    ]


def test_a_parent_ticket_lists_its_own_show_directory(tmp_path: Path) -> None:
    """Where a tree's show lives (/mx:show): the parent ticket's own directory. A parent is read
    like any other ticket, so its children's show directories are theirs and none of its own."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "csv-import.md", "open")
    ticket(root / "map-columns.md", "review", parent="csv-import")
    show = tmp_path / "agent" / "show"
    put(show / "csv-import" / "index.html", "<html>the tree</html>")
    put(show / "map-columns" / "mapping.svg", "<svg/>")
    rows = view_of(root).rows
    assert made(rows["csv-import"]) == [
        ("index.html", "show/csv-import/index.html", ""),
    ]
    assert made(rows["map-columns"]) == [
        ("mapping.svg", "show/map-columns/mapping.svg", ""),
    ]


def test_the_page_folds_the_comments_away_as_history() -> None:
    """Pins the format: the comments open only when the reader asks for them, and a block of the
    ticket's own words is a section under its label."""
    assert board.block_html(board.Block("comments", "<p>Built, not merged.</p>")) == (
        '<details class="history"><summary><span class="label">comments</span></summary><p>Built, not merged.</p></details>'
    )
    assert board.block_html(board.Block("answer", "<p>JSON.</p>")) == (
        '<section class="block"><p class="label">answer</p><p>JSON.</p></section>'
    )


def test_the_acceptance_criteria_read_as_a_checklist(demo: Demo) -> None:
    """Pins the format of the criteria, which the page's style reads a criterion as met or not by:
    the build in review met one criterion on its branch and left the other, and neither reads as a
    line opening with a bracket."""
    criteria = block(view_of(demo.root, demo.repo).rows["map-columns"], "acceptance criteria").prose
    assert criteria.count('<li class="tick met"') == 1 and criteria.count('<li class="tick"') == 1
    met, _, unmet = criteria.partition('<li class="tick"')
    assert "The second import from a bank asks nothing" in met, "the criterion its branch ticked reads as met"
    assert "a mapping that fails halfway writes nothing" in unmet, "the one it left reads as not met"
    assert "[x]" not in criteria and "[ ]" not in criteria


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
    row = view_of(root).rows["pick-a-format"]
    assert labels(row) == ["questions", None, "answer", "comments"], "the provenance line, under no heading of its own"
    assert "The two are coupled" in block(row, "questions").prose, "what the questions section says besides its items"
    assert "Proposed by the orchestrator" in block(row, None).prose
    assert "JSON, until a profile says otherwise." in block(row, "answer").prose
    assert asked(row) == [{"tag": "D1", "head": "Protobuf or JSON?", "detail": "One is smaller, the other is read by hand."}]
    assert "## Questions" in block(row, "comments").prose, "the fenced sample is quoted, not read as a section of its own"


def test_a_nested_list_renders_nested_at_the_indent_its_writers_use(tmp_path: Path) -> None:
    """The board's half of the parent ticket's incident: a writer indents a question's options three
    spaces, as GitHub and CommonMark take them, and the board rendered them as flat items."""
    root = tmp_path / "agent" / "tickets"
    root.mkdir(parents=True)
    (root / "pick-a-store.md").write_text(
        "---\nstatus: open\npriority: 2\nsize: S\n---\n\n# Where a view lives\n\n"
        "## Brief\n\nIn the ledger file or beside it.\n\n"
        "## What to build\n\n- The two stores:\n   - the ledger file, which travels with the data\n"
        "   - a file beside it, which does not\n"
    )
    written = block(view_of(root).rows["pick-a-store"], "what to build").prose
    assert re.search(r"<li>The two stores:\s*<ul>", written), f"the three-space nesting rendered flat: {written}"


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
    row = view_of(root).rows["skip-imported-rows"]
    assert labels(row) == ["questions", "what to build"], "no artefacts, and nothing folded away"
    assert asked(row) == [{"tag": "D1", "head": "Match on the payee too, or only date and amount?"}]
    written = block(row, "what to build").prose
    assert 'class="tick' not in written, "the checkbox is in what to build, and only the criteria are a checklist"
    assert "[x] 3 rows skipped" in written, "the ticket's own words, as it wrote them"


def test_the_watcher_notices_an_artefact_landing_in_a_show_directory(repo: Path, tracker: Path) -> None:
    """A session writing a show moves no file under the tracker, and the artefacts are what an
    opened ticket would otherwise never show. A file made executable is a button appearing on the
    page, and `chmod` moves neither its size nor the time it was written."""
    before = tracker_snapshot(tracker, repo)
    walkthrough = tracker.parent / "show" / "built" / "walkthrough"
    walkthrough.parent.mkdir(parents=True)
    walkthrough.write_text("#!/bin/sh\necho the import, twice\n")
    written = tracker_snapshot(tracker, repo)
    assert written != before
    walkthrough.chmod(walkthrough.stat().st_mode | 0o111)
    assert tracker_snapshot(tracker, repo) != written


def test_a_qualified_tag_on_the_board_links_to_what_it_names_or_is_struck_where_that_is_gone(
    repo: Path, tracker: Path, tmp_path: Path,
) -> None:
    """`tags-linked-on-board-and-review-pages`: a tag naming another ticket's question links to that
    ticket's row with the question as its hover words, a headline on a folded row included; a retro
    entry links to its place on the retro's page, from where the board is written; and one naming
    an entry the retro's report does not hold shows as gone, linking nowhere."""
    ticket(tracker / "cites.md", "open", brief="Waits on second D1, as retro F2 asks, and on retro F9.")
    (tracker / "second.md").write_text((tracker / "second.md").read_text()
                                       + "\n## Questions\n\n- [D1] **Ship it now?** Or wait for the suite.\n")
    (tracker / "small-chore.md").write_text((tracker / "small-chore.md").read_text()
                                            + "\n## Questions\n\n- [D1] **After second D1?** Its answer decides.\n")
    retro = tracker.parent / "retro"
    retro.mkdir()
    (retro / "report.md").write_text("# Workflow retro: repo\n\n## Findings\n\n### F2 Builds add machinery\n")
    (retro / "report.html").write_text('<h3 id="f2">F2</h3>')
    out = tmp_path / "out" / "board.html"
    render(tracker, repo, out)
    page = out.read_text()

    def links(text: str) -> list[str]:
        return re.findall(rf'<a class="qualified" [^>]*>{re.escape(text)}</a>', page)

    to_second = '<a class="qualified" href="#t-second" title="second D1 · Ship it now? Or wait for the suite.">second D1</a>'
    assert links("second D1") and set(links("second D1")) == {to_second}
    assert f"Waits on {to_second}, as" in page, "the brief"
    assert f"After {to_second}?" in page, "the folded row's question headline"
    (to_retro,) = set(links("retro F2"))
    assert 'href="../repo/agent/retro/report.html#f2"' in to_retro and 'title="retro F2 · Builds add machinery"' in to_retro
    (gone,) = re.findall(r"<s [^>]*>retro F9</s>", page)
    assert 'class="qualified gone"' in gone and "href" not in gone and "no longer in the retro" in gone


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
    the repo with the ticket's own name under a directory of the ticket's own name. The session on
    the main branch has a session page; the one too new to have a title ran in the same directory
    and has none.

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
    put(repo / "agent" / "sessions" / HERE / "index.html", "<!doctype html>\n<title>Ledger imports</title>\n")
    return root, repo


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text() + text)


def sessions_in(row: board.Row) -> list[board.Worked]:
    """Every session an opened ticket lists, in the order it lists them."""
    held = block(row, "sessions on this machine")
    return list(held.worked) if held else []


def rows_read(root: Path, repo: Path, out: Path) -> dict[str, board.Row]:
    """The rows a render of the page `out` shows, read as the render reads them."""
    return board.view(board.read(root, repo, out).tickets).rows


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
    reading = board.read(root, repo, tmp_path / "board.html")
    rows = board.view(reading.tickets).rows
    assert [(s.title, s.when, s.resume.text) for s in sessions_in(rows["map-columns"])] == [
        ("Ledger imports", "2026-09-14 → 2026-09-16", f"cd '{repo}' && claude --resume {HERE}"),
        ("Mapping the Sparkasse export", "2026-09-18", f"claude --resume {NAMED}"),
        (NEW, "2026-09-19", f"cd '{repo}' && claude --resume {NEW}"),
    ]
    assert "sessions on this machine" not in labels(rows["view-list"]), "no trailer names a session"
    assert AWAY not in repr(rows), "the worker on another host is left out, not shown unresumable"
    assert "transcripts" not in [a.source for a in board.absences(reading)], "this machine has its transcripts"


def pages_in(row: board.Row) -> list[tuple[str, str]]:
    """(the session's title, where its link goes) for every session an opened ticket links a
    session page for."""
    return [(s.title, s.page) for s in sessions_in(row) if s.page]


def test_a_session_with_a_page_carries_it_and_one_without_carries_none(worked: tuple[Path, Path]) -> None:
    """board-links-session-pages, at the board's loader: the page is the one the session-page
    renderer writes under the directory the session ran in. The session sharing that directory
    never needed a page, and neither did the one whose directory dispatch removed."""
    root, repo = worked
    pages = {s.id: s.page for s in ticket_sessions(root / "map-columns.md", repo)}
    assert pages == {HERE: repo / "agent" / "sessions" / HERE / "index.html", NAMED: None, NEW: None}


def test_a_session_whose_worktree_is_gone_carries_the_page_its_ticket_s_project_keeps(worked: tuple[Path, Path]) -> None:
    """The page outlives the worktree dispatch removed: it sits in the agent repo of the project
    the ticket is in, which the session's gone directory no longer names."""
    root, repo = worked
    put(repo / "agent" / "sessions" / NAMED / "index.html", "<!doctype html>\n<title>Wave 1</title>\n")
    (named,) = [s for s in ticket_sessions(root / "map-columns.md", repo) if s.id == NAMED]
    assert named.page == repo / "agent" / "sessions" / NAMED / "index.html"


def test_a_session_that_moved_project_carries_the_page_it_wrote_in_the_later_one(worked: tuple[Path, Path]) -> None:
    """The page is written in the agent repo of the project the session was in when its turn
    ended: one that started in the repo and went on in another project has its page there, and its
    resume command still starts where it did."""
    root, repo = worked
    later = repo.parent / "the budget"
    (later / "agent" / "tickets").mkdir(parents=True)
    (written,) = board.TRANSCRIPTS.glob(f"*/{NEW}.jsonl")
    append(written, json.dumps({"type": "user", "sessionId": NEW, "cwd": str(later)}) + "\n")
    put(later / "agent" / "sessions" / NEW / "index.html", "<!doctype html>\n")
    (moved,) = [s for s in ticket_sessions(root / "map-columns.md", repo) if s.id == NEW]
    assert moved.page == later / "agent" / "sessions" / NEW / "index.html"
    assert moved.resume == f"cd '{repo}' && claude --resume {NEW}"


def test_a_session_in_a_worktree_carries_the_page_its_project_keeps_in_the_main_checkout(worked: tuple[Path, Path]) -> None:
    """A linked worktree of the code repo holds no `agent/`: the page of a session that went on in
    one is in the main checkout's, where the Stop hook writes it (session-stop-hook)."""
    root, repo = worked
    worktree = repo.parent / "ledger-map-columns"
    demo_git(repo, "worktree", "add", "-q", str(worktree), "ticket/map-columns")
    (written,) = board.TRANSCRIPTS.glob(f"*/{NEW}.jsonl")
    append(written, json.dumps({"type": "user", "sessionId": NEW, "cwd": str(worktree)}) + "\n")
    put(repo / "agent" / "sessions" / NEW / "index.html", "<!doctype html>\n")
    (moved,) = [s for s in ticket_sessions(root / "map-columns.md", repo) if s.id == NEW]
    assert moved.page == repo / "agent" / "sessions" / NEW / "index.html"
    assert not (worktree / "agent" / "sessions").exists()


def test_an_opened_ticket_links_the_page_of_each_session_that_has_one(worked: tuple[Path, Path], path_with: Callable[..., Path]) -> None:
    """A session with no page shows no link, and its resume button is there all the same."""
    root, repo = worked
    row = rows_read(root, repo, root.parent / "board.html")["map-columns"]
    assert pages_in(row) == [("Ledger imports", f"sessions/{HERE}/index.html")]
    assert len(sessions_in(row)) == 3, "every listed session keeps its resume button"


def test_the_page_opens_a_session_page_in_a_tab_of_its_own_and_says_so() -> None:
    """Pins the format: the link opens a new tab and says on hover what it opens, beside the button
    that resumes the session."""
    resume = board.Copy("resume", "copy resume", board.RESUME_TIP, "claude --resume abc", "the command resuming Ledger imports")
    written = board.block_html(board.Block("sessions on this machine", worked=(
        board.Worked("Ledger imports", "2026-09-14", "sessions/abc/index.html", resume),
    )))
    assert f'<a class="spage" href="sessions/abc/index.html" target="_blank" data-tip="{html.escape(board.PAGE_TIP)}">page</a><span class="copier resume"' in written


def test_a_session_page_in_another_projects_agent_repo_is_not_linked(worked: tuple[Path, Path], path_with: Callable[..., Path]) -> None:
    """The board is served from its own agent repo, so no link it writes reaches a page kept in
    another project's: the session is listed with its resume button and no page link."""
    root, repo = worked
    later = repo.parent / "the budget"
    (later / "agent" / "tickets").mkdir(parents=True)
    (written,) = board.TRANSCRIPTS.glob(f"*/{NEW}.jsonl")
    append(written, json.dumps({"type": "user", "sessionId": NEW, "cwd": str(later)}) + "\n")
    put(later / "agent" / "sessions" / NEW / "index.html", "<!doctype html>\n")
    (moved,) = [s for s in ticket_sessions(root / "map-columns.md", repo) if s.id == NEW]
    assert moved.page == later / "agent" / "sessions" / NEW / "index.html", "the board finds the page it leaves unlinked"
    row = rows_read(root, repo, root.parent / "board.html")["map-columns"]
    assert [title for title, _ in pages_in(row)] == ["Ledger imports"], "only the page this agent repo keeps"
    assert len(sessions_in(row)) == 3


def test_a_session_that_commits_between_two_renders_is_on_the_second(worked: tuple[Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The board reads the log again on every render: a session working while the board watches is
    on the ticket by the next one."""
    root, repo = worked
    out = tmp_path / "board.html"
    assert sessions_in(rows_read(root, repo, out)["view-list"]) == []
    append(root / "view-list.md", "\nThe list is a sidebar.\n")
    demo_commit(repo, HERE, "2026-09-21T10:00:00+02:00", "view-list: the list is a sidebar", "agent/tickets")
    assert [s.title for s in sessions_in(rows_read(root, repo, out)["view-list"])] == ["Ledger imports"]


def test_the_button_that_resumes_a_session_shows_the_command_it_copies(worked: tuple[Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The spec's reviewed Property, at the button this slice adds: what it says on hover is what
    the click puts on the clipboard, and its note names the session the way the reader knows it."""
    root, repo = worked
    listed = sessions_in(rows_read(root, repo, tmp_path / "board.html")["map-columns"])
    assert [s.resume.text for s in listed] == [
        f"cd '{repo}' && claude --resume {HERE}", f"claude --resume {NAMED}", f"cd '{repo}' && claude --resume {NEW}",
    ]
    for s in listed:
        assert len(s.resume.does.split()) >= 4 and "copy" in s.resume.does, f"the button says {s.resume.does!r} of the click"
        assert s.resume.shows == s.resume.text, f"the button shows {s.resume.shows!r} and copies {s.resume.text!r}"
        assert s.title in s.resume.note, f"the note says {s.resume.note!r} of a session the reader knows as {s.title!r}"


def test_a_resume_command_longer_than_a_button_shows_is_cut_where_every_other_one_is(worked: tuple[Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """A working directory nested deep enough to run past what a button shows: the words are cut
    with an ellipsis, as a question's are, rather than spilling into the row."""
    root, repo = worked
    deep = repo / ("one-mapping-per-bank-" * 6)
    deep.mkdir()
    write_transcript(board.TRANSCRIPTS, HERE, str(deep), "Ledger imports")
    (first, *_) = sessions_in(rows_read(root, repo, tmp_path / "board.html")["map-columns"])
    text, shown = first.resume.text, first.resume.shows
    assert str(deep) in text and len(text) > board.COPY_CAP, "the command has to run long for the cut to show"
    assert shown.endswith("\u2026") and text.startswith(shown[:-1])


def test_the_demo_trackers_ticket_lists_the_sessions_this_machine_can_resume(transcribed: Demo) -> None:
    """The fixture's build in review: four sessions on its commits, the two with a transcript here
    listed with their titles, the worker on another host left out. The second ran in a worktree
    dispatch has since removed, so its command resumes it where the reader stands."""
    rows = view_of(transcribed.root, transcribed.repo).rows
    row = rows["map-columns"]
    assert [(s.title, s.when, s.resume.text) for s in sessions_in(row)] == [
        ("Grilling the CSV import", "2026-09-14", f"cd {transcribed.repo} && claude --resume {S1}"),
        ("Dispatching csv-import, wave 1", "2026-09-17 → 2026-09-18", f"claude --resume {S2}"),
    ]
    assert S4 not in repr(rows), "the worker built it on another host, where the user cannot resume it"
    assert [title for title, _ in pages_in(row)] == ["Grilling the CSV import"], "only the grilling needed a page"


FILED = "b4c5d6e7-1111-4111-8111-111111111111"  # filed both tickets, before either moved
GRILLED = "b4c5d6e7-2222-4222-8222-222222222222"  # the grilling that renamed them both
LATER = "b4c5d6e7-3333-4333-8333-333333333333"  # worked on one after its second name


@pytest.fixture
def moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """(the tracker, its repo) of two tickets that moved: one renamed as a grilling sharpened what
    it was for, and one renamed twice.

    Beside the three sessions named above, AWAY edits one under its first path, so a carried session
    the board cannot resume has somewhere to show; and the second rename is the user's own `git mv`,
    under no session at all.
    """
    repo = tmp_path / "the ledger"
    root = repo / "agent" / "tickets"
    root.mkdir(parents=True)
    demo_git(repo, "init", "-q", "-b", "master")
    ticket(root / "split-rows.md", "open")
    ticket(root / "name-columns.md", "open")
    demo_commit(repo, FILED, "2026-09-14T10:00:00+02:00", "two csv tickets filed", "agent/tickets")
    append(root / "split-rows.md", "\nOne row per transaction.\n")
    demo_commit(repo, AWAY, "2026-09-15T11:00:00+02:00", "split-rows: one row per transaction", "agent/tickets")

    demo_git(repo, "mv", "agent/tickets/split-rows.md", "agent/tickets/row-splitting.md")
    demo_git(repo, "mv", "agent/tickets/name-columns.md", "agent/tickets/header-naming.md")
    demo_commit(repo, GRILLED, "2026-09-16T09:00:00+02:00", "the two tickets renamed for what they do", "agent/tickets")
    append(root / "header-naming.md", "\nThe header row names the bank.\n")
    # written during the grilling and cherry-picked over after the move, so the walk reaches it
    # after the commit whose date it has to widen the span back from
    demo_commit(repo, GRILLED, "2026-09-15T16:00:00+02:00", "header-naming: the header row", "agent/tickets")

    demo_git(repo, "mv", "agent/tickets/header-naming.md", "agent/tickets/header-row.md")
    demo_git(repo, "commit", "-q", "-m", "header-row: named again")  # moved by hand, no session
    append(root / "header-row.md", "\nAsked once per bank.\n")
    demo_commit(repo, LATER, "2026-09-19T08:00:00+02:00", "header-row: asked once per bank", "agent/tickets")

    written = tmp_path / "claude" / "projects"
    for sid, title in ((FILED, "Filing the csv tickets"), (GRILLED, "Grilling the csv import"), (LATER, "The header row")):
        write_transcript(written, sid, str(repo), title)
    monkeypatch.setattr(board, "TRANSCRIPTS", written)
    return root, repo


def test_a_ticket_that_moved_lists_the_sessions_from_under_its_old_path(moved: tuple[Path, Path]) -> None:
    """A moved ticket is one ticket: git records the move, so the session that filed it is listed on
    it wherever it now sits, and a chain of two moves carries both earlier paths."""
    root, repo = moved
    once = ticket_sessions(root / "row-splitting.md", repo)
    assert [(s.id, s.first, s.last) for s in once] == [
        (FILED, "2026-09-14", "2026-09-14"), (GRILLED, "2026-09-16", "2026-09-16"),
    ], "the session that filed it as agent/tickets/split-rows.md worked on this ticket"
    twice = ticket_sessions(root / "header-row.md", repo)
    assert [(s.id, s.first, s.last) for s in twice] == [
        (FILED, "2026-09-14", "2026-09-14"),
        (GRILLED, "2026-09-15", "2026-09-16"),
        (LATER, "2026-09-19", "2026-09-19"),
    ], "under each of its three names, the second rename itself under no session"


def test_a_session_the_board_cannot_resume_is_left_off_a_moved_ticket_too(moved: tuple[Path, Path]) -> None:
    """The Property that a listed session has a transcript on this machine, over a carried session:
    AWAY worked on the ticket under its first path and has no transcript here."""
    root, repo = moved
    under = board.session_log(repo)["agent/tickets/row-splitting.md"]
    assert AWAY in under, "it committed on the ticket while it was agent/tickets/split-rows.md"
    assert AWAY not in {s.id for s in ticket_sessions(root / "row-splitting.md", repo)}


def test_a_move_on_one_branch_leaves_the_sessions_on_the_path_another_branch_still_has(
    moved: tuple[Path, Path],
) -> None:
    """A move is a fact of the branch that made it, and the walk is over every branch at once. The
    ticket a worker moves on its own branch keeps its sessions where the main checkout still has
    it, until the merge."""
    root, repo = moved
    demo_git(repo, "checkout", "-q", "-b", "ticket/row-splitting")
    demo_git(repo, "mv", "agent/tickets/row-splitting.md", "agent/tickets/split-rows.md")
    demo_commit(repo, LATER, "2026-09-21T10:00:00+02:00", "row-splitting: named again on its branch", "agent/tickets")
    demo_git(repo, "checkout", "-q", "master")
    assert [s.id for s in ticket_sessions(root / "row-splitting.md", repo)] == [FILED, GRILLED], (
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
            "n6": pull(317, "OPEN"),  # the `built` ticket the tracker fixture already carries
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
    the two its `built` ticket already names."""
    ticket(tracker / "small-chore.md", "open", gh=[ref for ref in STATED if not ref.endswith(("#317", "#412"))])
    return tracker


def gh_answering(path_with: Callable[..., Path], answer: dict, said: str = "") -> Path:
    """A `gh` that answers every query with `answer`. Given `said`, it reports that on stderr and
    exits non-zero, as gh does with a request it considers failed."""
    # printf, a shell builtin, since this PATH holds only the tools the board reaches for itself
    spoken = f'printf "%s\\n" {shlex.quote(said)} >&2\nexit 1' if said else ""
    return path_with("gh", f"printf '%s' {shlex.quote(json.dumps(answer))}\n{spoken}")


def gh_marks(reading: Reading) -> dict[str, tuple[str, str]]:
    """(the state it wears, the words it says on hover) of every GitHub link a render shows, by
    reference."""
    rows = board.view(reading.tickets, reading.gh).rows.values()
    return {m.shows: (m.look, m.says) for r in rows for m in r.marks if m.kind == "gh"}


def sources(reading: Reading) -> list[str]:
    """Every optional source a render says it did without, once per time it says so."""
    return [a.source for a in board.absences(reading)]


def queries(record: Path) -> list[str]:
    """The GraphQL queries the render sent; an auth probe is not one."""
    return [r for r in runs(record) if "graphql" in r]


def stamp_of(out: Path) -> str:
    """The stamp the open tab polls against, which moves when anything the page shows moves."""
    return Path(f"{out}.stamp.js").read_text()


def test_a_reference_wears_the_state_github_gives_it_and_says_it_in_words(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """Every state the board tells apart, from one answer, and the words each says on hover: which
    of the two it is, and which state it is in."""
    gh_answering(path_with, ANSWERED)
    reading = board.read(referenced, repo, tmp_path / "board.html")
    marks = gh_marks(reading)
    assert {ref: state for ref, (state, _) in marks.items()} == STATED
    assert "merged" in marks["acme/backend#4"][1], "a merged pull request reads as merged without opening it"
    for ref, (state, tip) in marks.items():
        kind = "pull request" if state.startswith("pr-") else "issue"
        word = {"changes": "asked for changes"}.get(state.split("-", 1)[1], state.split("-", 1)[1])
        assert kind in tip and word in tip, f"{ref} is {state} and says {tip!r}"
    assert "github" not in sources(reading), "GitHub answered, so there is no absence to report"


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
    assert gh_marks(board.read(referenced, repo, tmp_path / "board.html"))["ACME/Backend#4"][0] == "pr-merged"


def test_one_query_per_render_resolves_every_reference_in_every_repository(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    record = gh_answering(path_with, ANSWERED)
    render(referenced, repo, tmp_path / "board.html")
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
    reading = board.read(referenced, repo, tmp_path / "board.html")
    marks = gh_marks(reading)
    assert marks["acme/backend#4"][0] == "pr-merged"
    assert [marks[ref][0] for ref in ("acme/helix#6", "acme/helix#7")] == ["unknown", "unknown"]
    assert marks["acme/helix#6"][1] == board.UNKNOWN_REF
    assert "github" not in sources(reading)


def test_the_page_says_why_github_did_not_answer_in_ghs_own_words(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """An answer with no data in it is no answer: a token GitHub refuses, a network that is not
    there. What gh said is what the user has to fix, so the note carries it."""
    gh_answering(path_with, {"message": "Bad credentials", "status": "401"}, said="gh: Bad credentials (HTTP 401)")
    reading = board.read(tracker, repo, tmp_path / "board.html")
    (said,) = [a.words for a in board.absences(reading) if a.source == "github"]
    assert "Bad credentials" in said
    assert gh_marks(reading)["acme/backend#317"] == ("unknown", board.UNKNOWN_REF)


def test_a_reference_filed_after_the_last_query_is_asked_about_at_once(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The cached answer serves the references it was asked about; a ticket filed with one it was
    not is worth the query it costs, rather than a window bare."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(referenced, repo, out)
    ticket(referenced / "loose-idea.md", "proposed", gh=["acme/coding#9"])
    render(referenced, repo, out)
    assert len(queries(record)) == 2
    assert queries(record)[1].count("issueOrPullRequest") == len(STATED) + 1


def test_an_answer_older_than_its_lifetime_is_asked_again(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The clock is what ages an answer, so the check moves the lifetime rather than the file: what
    the cache holds is the module's own business."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(referenced, repo, out)
    monkeypatch.setattr(github, "LIFETIME", timedelta(0))
    render(referenced, repo, out)
    assert len(queries(record)) == 2


def test_a_cached_answer_dresses_the_links_the_render_it_served_did_not_ask_about(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """What the cache is for: the second render shows every state the first one was told, and says
    nothing about an absence, having wanted nothing."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(referenced, repo, out)
    first = stamp_of(out)
    render(referenced, repo, out)
    assert len(queries(record)) == 1
    assert stamp_of(out) == first, "the tab has nothing to reload for"
    served = board.read(referenced, repo, out)
    assert len(queries(record)) == 1
    assert {ref: state for ref, (state, _) in gh_marks(served).items()} == STATED
    assert "github" not in sources(served)


def test_a_tracker_that_changed_without_its_references_changing_asks_nothing(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The watcher's everyday render: a claim, a ruling, a brief rewritten, and the same references
    on the rows."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    render(referenced, repo, out)
    was = stamp_of(out)
    ticket(referenced / "small-chore.md", "claimed", gh=[ref for ref in STATED if not ref.endswith(("#317", "#412"))])
    render(referenced, repo, out)
    assert len(queries(record)) == 1
    assert stamp_of(out) != was, "the render did happen"


def test_a_tracker_naming_no_pull_request_or_issue_asks_nothing_and_says_nothing(
    tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """A board with no GitHub reference on it has no source to miss, as a tracker with no review
    page rendered has no server to miss. Its own tracker, since the fixture's `built` ticket names
    two references of its own."""
    record = gh_answering(path_with, ANSWERED)
    root = tmp_path / "repo" / "agent" / "tickets"
    root.mkdir(parents=True)
    ticket(root / "only.md", "open")
    repo = root.parent.parent
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tracker")
    reading = board.read(root, repo, tmp_path / "board.html")
    assert queries(record) == []
    assert "github" not in sources(reading)
    assert gh_marks(reading) == {}


def test_a_cache_this_version_cannot_read_is_asked_past(
    repo: Path, referenced: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """A cache half-written by a killed render, or written by a board that held other fields: the
    render asks again rather than failing on it."""
    record = gh_answering(path_with, ANSWERED)
    out = tmp_path / "board.html"
    github.cache_path(out).parent.mkdir(parents=True, exist_ok=True)
    github.cache_path(out).write_text('{"asked": "2026-09-23T')
    reading = board.read(referenced, repo, out)
    assert len(queries(record)) == 1
    assert gh_marks(reading)["acme/backend#4"][0] == "pr-merged"


def test_a_gh_that_never_answers_leaves_the_render_to_go_on_without_it(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A render waits TIMEOUT for GitHub and no longer: a board that hung on a hung request would
    take its watcher with it."""
    monkeypatch.setattr(github, "TIMEOUT", 0.5)
    path_with("gh", "while :; do :; done")
    reading = board.read(tracker, repo, tmp_path / "board.html")
    assert sources(reading).count("github") == 1
    assert gh_marks(reading)["acme/backend#317"][0] == "unknown"


def test_every_state_a_link_can_wear_has_a_look_of_its_own_on_the_page() -> None:
    """The ticket's "a link shows its state in its own look": the state a link wears is its class
    on the page, and the stylesheet dresses each one apart. The layout checks render without gh, so
    the styles the states wear are only visible here."""
    written = board.mark_html(board.Mark("gh", "acme/backend#4", "A merged pull request.", look="pr-merged", href="https://github.com/acme/backend/issues/4"))
    assert written.startswith('<a class="gh pr-merged" href="https://github.com/acme/backend/issues/4"'), written
    rules = style_rules(board.STYLE)
    looks = {state: {prop: value for selectors, said in rules if any(re.search(rf"\.gh\.{state}\b", one) for one in selectors)
                     for prop, value in said.items()}
             for state in github.SAYS}
    assert all(looks.values()), f"states with no look of their own: {[s for s in looks if not looks[s]]}"
    assert len({tuple(sorted(look.items())) for look in looks.values()}) >= 4, "the states would not be told apart on the page"


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


def test_the_board_says_what_waits_on_the_user_until_a_session_writes_a_briefing(ranked: Path) -> None:
    """The spec's fallback: the counts the prototype's sentence gives, and no model behind them."""
    said = board.fallback(view_of(ranked))
    assert said.startswith(
        "One build to rule on, one question wanting a word and two tickets wanting a session wait on you."
    ), f"both near tickets the user is in the loop for are counted: {said}"


def test_the_fallback_orders_the_next_picks_by_priority_then_what_they_unlock_then_your_time(ranked: Path) -> None:
    """Three picks, in the order the spec names: priority, then what accepting one unblocks, then
    the user's own time on it."""
    said = board.fallback(view_of(ranked))
    picks = re.findall(r"^- \*\*(.+?)\*\*: (.+)$", said, re.MULTILINE)
    assert [name for name, _ in picks] == ["The hub", "The quick one", "A shape to pick"]
    assert picks[0][1] == "now · accepting it unblocks two · 1 h of yours"


def test_the_briefing_the_cache_holds_is_what_the_board_shows_with_the_time_it_was_written(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    out = tmp_path / "board.html"
    when = datetime.fromisoformat("2026-09-21T09:30:00+02:00")
    Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 2).write(cache_path(out))
    reading = board.read(tracker, repo, out)
    said = board.briefed(reading.briefing, board.view(reading.tickets))
    assert said.text == "Two builds wait on your ruling.", "the board's own count stands in only until a session writes one"
    assert said.when == "written 21 Sep 09:30", "the board shows when the briefing was written"
    assert "model" not in sources(reading), "a briefing already written is no absence whatever the machine has now"
    # the mark's own words, which are what the user is told the cadence is (the every-mark-explains
    # -itself Property, disposed reviewed): the numbers are the schedule's own, the sentence is not
    assert "status" in said.says, "the hover words do not say that a status is what reaches the session"
    assert f"{QUIET.seconds // 60} minutes" in said.says and f"{CADENCE.seconds // 60} minutes" in said.says, \
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
    assert "Two builds wait on your ruling." in out.read_text()


def test_a_watched_board_re_renders_on_a_change_under_the_tracker_and_tells_the_session_of_a_status(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The watcher's own reason to exist, which the pass above leaves out: a ticket file moves and
    the page follows it. Only a status moving is the session's business, though (the spec's
    Decisions under "The board briefing"): a ticket filed or retired is a status appearing or going,
    prose rewritten is a render and no more, and a status that goes back to what the session was
    last told leaves nothing to tell."""
    out = tmp_path / "board.html"
    when = datetime.now().astimezone()  # a briefing already written, so the opening pass arms nothing
    Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 0).write(cache_path(out))
    render(tracker, repo, out)  # as main() does before it starts watching
    watching, session = [Seen()], board.Briefer(repo, out)
    watching[0] = look(watching[0], session, tracker, repo, out)
    assert session.changed_at is None, "the opening pass has nothing to tell the session about"
    assert watching[0].statuses == render(tracker, repo, out), \
        "the baseline the first pass read is not the tracker the board draws"

    chore = tracker / "new-chore.md"
    second = tracker / "second.md"
    assert status_moved(watching, session, tracker, repo, out, lambda: ticket(chore, "open")), \
        "the briefing session was never told a ticket was filed"
    assert "new chore" in out.read_text(), "the new row is not on the page it re-rendered"
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
    told = (("second", "open"), ("small-chore", "open"))
    session = board.Briefer(Path("."), Path("board.html"), told=(), told_statuses=told)

    session.saw(claimed := (("second", "claimed"), ("small-chore", "open")), told, at)
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
    render(tracker, repo, out)
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
    render(tracker, repo, out)
    before = stamp()
    assert "model" not in sources(board.read(tracker, repo, out)), "the model is here and nothing has failed yet"

    watching, session = Seen(), board.Briefer(repo, out)
    watching = look(watching, session, tracker, repo, out)  # the first pass starts the run
    assert session.running
    session.running.join(30)
    assert len(runs(claude)) == 1 and briefing.SILENT, "the run that answered nothing said nothing of itself"

    look(watching, session, tracker, repo, out)
    assert stamp() != before, "the open tab has no reason to reload"
    assert out.read_text().count("it answered nothing") == 1, "the page does not say the run answered nothing, once"


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
    out = tmp_path / "board.html"
    at = datetime.now().astimezone()
    watcher = board.Briefer(repo, out)

    statuses = board.statuses(load_tickets(tracker, repo, tracker.parent))
    watcher.opened(tracker_snapshot(tracker, repo), statuses, at)
    watcher.tick(tracker, tracker_snapshot(tracker, repo), statuses, at)
    watcher.running.join(30)
    assert len(runs(claude)) == 1, "the change the watcher opened on starts one run"
    written = Briefing.read(cache_path(out))
    assert written and (written.text, written.session, written.pings) == (said["result"], "abc-123", 0)
    told = watcher.told

    watcher.saw(statuses + (("a-new-one", "open"),), statuses, at + timedelta(minutes=1))
    watcher.tick(tracker, tracker_snapshot(tracker, repo), statuses, at + timedelta(minutes=1))
    assert len(runs(claude)) == 1, "a change inside the quiet window waits it out"
    watcher.tick(tracker, tracker_snapshot(tracker, repo), statuses, at + QUIET + timedelta(minutes=1))
    assert len(runs(claude)) == 1, "a run inside the cadence of the last one is not tried again (Briefer.tried)"

    path_with("claude", "echo '{\"is_error\": true}'")  # a login that has lapsed, a run past its limit
    ticket(tracker / "small-chore.md", "done")
    # stamped while the session was exploring: a run's clock is read before it starts, so a change
    # landing during one reads as a change it has not heard, and the cadence after is when it does
    watcher.saw(statuses + (("small-chore", "done"),), statuses, written.last_activity + timedelta(seconds=1))
    # the cadence counts from the run's own clock, read on its thread a moment after `at`, and later under load
    second = written.last_activity + CADENCE + timedelta(seconds=1)
    watcher.tick(tracker, tracker_snapshot(tracker, repo), statuses, second)
    watcher.running.join(30)
    assert len(runs(claude)) == 2, "a change the session has not heard is pinged out the cadence after it"
    assert f"--resume {written.session}" in runs(claude)[1], "the cadence's change started a fresh exploration"
    assert Briefing.read(cache_path(out)) == written, "a run that answered nothing writes nothing"
    assert watcher.told == told, "what the session was told about waits for the run that reaches it"

    # and the run that answered nothing is tried again a cadence later, not on every pass after it
    watcher.tick(tracker, tracker_snapshot(tracker, repo), statuses, second + timedelta(seconds=30))
    assert len(runs(claude)) == 2, "a run that answered nothing was retried on the next pass"
    watcher.tick(tracker, tracker_snapshot(tracker, repo), statuses, second + CADENCE + timedelta(seconds=1))
    watcher.running.join(30)
    assert len(runs(claude)) == 3, "a run that answered nothing was never retried"

    cache_path(out).unlink()  # and with no briefing to fall back on, the page says why there is none
    assert sources(board.read(tracker, repo, out)).count("model") == 1


def refuse(path: Path, *fields: str) -> None:
    """Give the ticket at `path` fields the tracker does not know, in this order from its first line."""
    path.write_text(path.read_text().replace("---\n", "---\n" + "".join(f"{f}: [x]\n" for f in fields), 1))


def polled(out: Path) -> dict[str, object]:
    """What an open tab reads from the stamp file: `Stamp` and `Stale`."""
    said = Path(str(out) + ".stamp.js").read_text()
    return {name: json.loads(value) for name, value in re.findall(r"^window\.__board(\w+) = (.*);$", said, re.M)}


def test_failing_passes_say_each_error_once_and_mark_the_open_board_stale_until_one_succeeds(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The helferline watcher of 2026-10-13 printed one refusal every two seconds for six days, into
    a gigabyte of log, while the board it kept open showed nothing amiss."""
    clock = [datetime(2026, 10, 7, 9, 30).astimezone()]
    monkeypatch.setattr(board, "now", lambda: clock[0])
    out = tmp_path / "board.html"
    render(tracker, repo, out)
    watching = board.turn(board.Watch(Seen(), board.Briefer(repo, out)), tracker, repo, out)
    drawn = polled(out)
    assert drawn["Stale"] is None
    capsys.readouterr()

    def passes(n: int) -> str:
        nonlocal watching
        for _ in range(n):
            watching = board.turn(watching, tracker, repo, out)
        return capsys.readouterr().err

    second = tracker / "second.md"
    good = second.read_text()
    refuse(second, "flavour", "colour")  # a refusal two lines long
    assert passes(3).count("`flavour` is no ticket field") == 1
    stale = polled(out)
    assert stale["Stamp"] == drawn["Stamp"], "a failed pass reloads the tab"
    assert "stale since 07 Oct 09:30" in str(stale["Stale"]) and "`flavour` is no ticket field" in str(stale["Stale"])
    assert "`colour`" not in str(stale["Stale"]), "the mark carries more than the error's first line"

    clock[0] = datetime(2026, 10, 7, 10, 45).astimezone()
    second.write_text(good)
    refuse(second, "texture")
    assert passes(3).count("`texture` is no ticket field") == 1
    assert "stale since 07 Oct 09:30" in str(polled(out)["Stale"]), "a new error moved when the board went stale"
    assert "`texture`" in str(polled(out)["Stale"])

    second.write_text(good)
    assert passes(3).count("succeed again") == 1
    assert polled(out)["Stale"] is None


def test_the_watcher_watches_every_module_it_loaded() -> None:
    assert {"board.py", "tracker.py", "briefing.py", "github.py"} <= {path.name for path, _, _ in board.CODE}


class Stopped(Exception):
    """Raised by a check's own sleep to end a watcher's loop."""


def test_the_watcher_tries_changed_code_once_per_change_and_hands_itself_on_within_a_pass_once_it_starts(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Broken code tried and said every pass would be the helferline log again; retried a while on,
    it says nothing new."""
    out = tmp_path / "board.html"
    render(tracker, repo, out)
    module = tmp_path / "tracker.py"
    module.write_text("FIELDS = ('status',)\n")
    watching = board.Watch(Seen(), board.Briefer(repo, out), code=board.on_disk([module]))
    tried: list[str] = []
    monkeypatch.setattr(board, "starts", lambda: tried.append(module.read_text()) or "SyntaxError: '(' was never closed")

    def run(passes: int, *, then: Callable[[], None] = lambda: None) -> None:
        slept = [0]

        def sleep(_: float) -> None:
            slept[0] += 1
            if slept[0] == 2:
                then()
            if slept[0] == passes:
                raise Stopped
        monkeypatch.setattr(board.time, "sleep", sleep)
        with pytest.raises(Stopped):
            board.watch(watching, tracker, repo, out)

    module.write_text("FIELDS = ('status',\n")
    run(4, then=lambda: module.write_text("FIELDS = ('status', 'repos'\n"))
    assert tried == ["FIELDS = ('status',\n", "FIELDS = ('status', 'repos'\n"]
    assert capsys.readouterr().err.count("does not start") == 2

    monkeypatch.setattr(board, "CODE_RETRY", 0)
    tried.clear()
    run(3)
    assert len(tried) == 3
    assert capsys.readouterr().err.count("does not start") == 1

    monkeypatch.setattr(board, "starts", lambda: None)
    monkeypatch.setattr(board.time, "sleep", lambda _: pytest.fail("a second pass ran on code that changed under the first"))
    assert board.watch(watching, tracker, repo, out).seen.snapshot, "handed on without the pass it was in"


def test_a_watcher_restarted_on_new_code_keeps_its_tabs_address_and_its_briefing_schedule(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path], monkeypatch: pytest.MonkeyPatch,
    listening: str,
) -> None:
    out = tmp_path / "board.html"
    render(tracker, repo, out)
    at = datetime(2026, 10, 13, 9, 30).astimezone()
    told = tracker_snapshot(tracker, repo)
    session = board.Briefer(repo, out, told=told, told_statuses=(("second", "open"),), changed_at=at, tried=at - timedelta(minutes=3))
    failing = board.Failing(at - timedelta(days=6), "a.md:3: `flavour` is no ticket field")
    watching = board.Watch(Seen(statuses=(("second", "claimed"),)), session, f"{listening}/board.html", failing=failing)

    execs: list[list[str]] = []
    monkeypatch.setattr(board.os, "execv", lambda path, argv: execs.append(argv))
    monkeypatch.setenv(board.HANDOVER, "")  # so the variable restart sets goes with the check
    board.restart(watching, out)
    assert [argv[0] for argv in execs] == [str(Path(board.__file__).resolve())]

    resumed = board.taken(repo, out)
    assert resumed and resumed.address == f"{listening}/board.html"
    kept = (resumed.session.told, resumed.session.told_statuses, resumed.session.changed_at, resumed.session.tried)
    assert kept == (told, (("second", "open"),), at, at - timedelta(minutes=3))
    assert (resumed.failing, resumed.seen.statuses) == (failing, (("second", "claimed"),))

    rendered = out.stat().st_mtime_ns
    board.turn(resumed, tracker, repo, out)
    assert out.stat().st_mtime_ns != rendered, "the new code's first pass did not draw the page"


def test_a_hand_over_the_new_code_cannot_read_keeps_the_tabs_address(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A watcher that died here would leave the open tab stale for as long as nobody looks."""
    held = tmp_path / "board.html.handover"
    held.write_text(repr({"address": "http://127.0.0.1:4711/board.html", "seen": ()}))
    monkeypatch.setenv(board.HANDOVER, str(held))
    resumed = board.taken(repo, tmp_path / "board.html")
    assert resumed and resumed.address == "http://127.0.0.1:4711/board.html"
    assert not held.exists()


@pytest.mark.full_path
def test_a_running_watcher_runs_the_code_changed_under_it_and_keeps_its_tab(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path],
) -> None:
    """On a copy of the board's code, changed under a watcher running it. The server going away is
    what shows the new code holds the tab's address: it brings that server back."""
    if not shutil.which("uv"):
        pytest.skip("no uv to run the board's script with")
    here = Path(board.__file__).resolve().parent
    skills = tmp_path / "skills"
    for name in ("tracker", "session-page"):
        shutil.copytree(here.parent / name, skills / name, ignore=shutil.ignore_patterns("__pycache__", "corpus", "fixtures", "test_*"))
    module = skills / "tracker" / "tracker.py"
    loaded = module.read_text()

    server = socket.create_server(("127.0.0.1", 0))
    serves = path_with("diffview", f'echo "diffview: serving $2 at http://127.0.0.1:{server.getsockname()[1]}/"')
    opens = path_with("browser")

    said = tmp_path / "watcher.log"
    with said.open("w") as log:
        watcher = subprocess.Popen(
            [str(skills / "tracker" / "board.py"), str(tracker)], stdout=log, stderr=subprocess.STDOUT,
            env=os.environ | {"DIFFVIEW_BROWSER": str(opens.with_suffix(""))},
        )
    try:
        assert until(lambda: (tracker.parent / "board.html").exists()), said.read_text()
        module.write_text(loaded + "\ndef (\n")
        assert until(lambda: "does not start" in said.read_text()), said.read_text()
        assert watcher.poll() is None, said.read_text()

        module.write_text(loaded + '\nprint("tracker: the new code", file=sys.stderr)\n')
        assert until(lambda: "tracker: the new code" in said.read_text()), said.read_text()
        server.close()
        assert until(lambda: len(runs(serves)) == 2), said.read_text()
    finally:
        server.close()
        watcher.terminate()
        watcher.wait(10)
    log = said.read_text()
    assert log.count("does not start") == 1, log
    assert len(runs(opens)) == 1, "the restart opened a second tab"
    assert "Traceback" not in log, log


def until(holds: Callable[[], bool], seconds: float = 60) -> bool:
    deadline = time.monotonic() + seconds
    while not holds():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.2)
    return True


def test_a_cache_file_the_board_cannot_read_leaves_it_the_boards_own_count(
    repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]
) -> None:
    """The cache is written by a thread of its own while the board renders from it, and a version
    of the board older than the file that is there is the same case: neither is a render that
    fails."""
    out = tmp_path / "board.html"
    cache_path(out).write_text('{"text": "half a fi')
    reading = board.read(tracker, repo, out)
    assert board.briefed(reading.briefing, board.view(reading.tickets)).text.startswith("One build to rule on waits on you.")


def test_the_briefing_session_is_given_every_ticket_the_board_shows_and_the_file_to_read_it_in(demo: Demo) -> None:
    """What a fresh session starts from: the tracker as the board computes it, which is every row's
    marks, its brief, its open questions and the file the rest of it is in."""
    state = board.briefing_state(demo.root, demo.repo)
    shown = load_tickets(demo.root, demo.repo, demo.root.parent)
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
    # a row folded under its parent ticket's says which one, and its question is on its own line alone,
    # though the parent's row lists it too
    assert f"Carry the balances forward \u00b7 {demo.root / 'carry-balances.md'} \u00b7 folded under month-close\n" in state
    assert state.count("asks: [D1] Carry a closed month's balances") == 1
    # the tickets are written out under the tree each is part of, the ones in no tree under their own
    assert "## alone\nexport-to-xlsx \u00b7 blocked \u00b7 build \u00b7 p4 later \u00b7 20 min \u00b7 Export to Excel \u00b7 " in state


def test_a_tracker_change_reaches_the_session_as_the_files_that_moved(tmp_path: Path) -> None:
    """What a ping tells the session. Its own copy of the demo tracker: this check moves files under
    it, and the shared fixture is read by every later check in this file and the next."""
    own = build_demo(tmp_path / "demo")
    before = tracker_snapshot(own.root, own.repo)
    assert changed_note(before, before, own.repo) == "something under the tracker was touched without changing"

    ticket(own.root / "new-slice.md", "open", parent="csv-import")
    (own.root / "upgrade-python.md").unlink()
    faster = own.root / "speed-up-tests.md"
    faster.write_text(faster.read_text() + "\n## Questions\n\n- [D9] **Is the template rebuilt often enough?**\n")
    demo_commit(own.repo, S3, "2026-09-23T09:00:00+02:00", "tickets: a slice filed, a chore retired", "agent/tickets")
    note = changed_note(before, tracker_snapshot(own.root, own.repo), own.repo)

    assert "new: agent/tickets/new-slice.md" in note
    assert "gone: agent/tickets/upgrade-python.md" in note
    assert "changed: agent/tickets/speed-up-tests.md" in note
    assert "the repo has moved on: " in note and "a slice filed, a chore retired" in note


# ---- properties -----------------------------------------------------------
# The executable Properties of mx/skills/tracker/corpus/board-orients.md that live at these seams.


def runs(record: Path) -> list[str]:
    """What the board ran a stub tool with, one line per run (the path_with fixture)."""
    return record.read_text().splitlines() if record.exists() else []


# what the demo tracker's tickets ask of the user: the two builds in review, the parent ticket at
# its close-out, every ticket with a question no Ruled line answers, and the two near tickets the
# user is in the loop for, whose session is the work whether or not a question of theirs is open.
NEEDS_ME = {
    "map-columns", "view-storage", "view-list-shape", "flaky-upload-test",
    "pick-a-date-library", "retire-legacy-exporter", "speed-up-tests", "staging-credentials",
    "month-close",
}


def test_the_needs_me_group_holds_exactly_the_tickets_that_wait_on_the_user(demo: Demo) -> None:
    """Who waits on the user, at the seam the ticket's Testing seams name: a fixture tracker on disk
    in, groups out. map-columns carries its questions in the tracker's own copy, where the import
    left them."""
    seen = view_of(demo.root, demo.repo)
    assert rows_in(seen, "needs") == NEEDS_ME
    assert "read-the-bank-formats" not in rows_in(seen, "needs"), "a worker's ticket with nothing open"


# ---- a parent ticket ruled whole ------------------------------------------
# speculative-first's Decisions, The board: a leaf in review under a parent not yet closed out
# waits in its tree, not in the needs-me group; a parent at its close-out is one needs-me row with
# its children under it.


def test_a_leaf_merged_into_a_parent_still_being_built_waits_in_its_tree_not_on_the_user(demo: Demo) -> None:
    """duplicate-rule is in review, merged into the branch of csv-import, which is still claimed."""
    seen = view_of(demo.root, demo.repo)
    assert "needs" in [g.state for g in seen.groups]
    assert "duplicate-rule" not in anywhere_in(seen, "needs")
    assert "csv-import" in rows_in(seen, "claimed")
    parent = seen.rows["csv-import"]
    assert [r.ticket.slug for r in parent.kids] == ["duplicate-rule"], "the leaf sits under its parent's row"
    assert mark(seen.rows["duplicate-rule"], "asks").shows == "with parent"
    assert mark(parent, "kin").shows == "1 child ticket"


def test_a_parent_at_its_close_out_is_one_needs_me_row_with_its_children_folded_under_it(demo: Demo) -> None:
    """month-close is in review with carry-balances and lock-period. The group counts the parent
    as one row, and the parent's row asks carry-balances' question, which the button copying the
    group's questions copies with the rest."""
    seen = view_of(demo.root, demo.repo)
    children = {"carry-balances", "lock-period"}
    assert "month-close" in rows_in(seen, "needs")
    assert not children & {one for g in seen.groups for one in rows_in(seen, g.state)}
    parent = seen.rows["month-close"]
    assert {r.ticket.slug for r in parent.kids} == children
    (needs,) = [g for g in seen.groups if g.state == "needs"]
    assert len(needs.rows) == len(NEEDS_ME), "the parent and its children count as one row"
    assert mark(parent, "kin").shows == "2 child tickets"
    assert "closing a month writes each account's balance" in parent.search, "a word of a folded child finds the row holding it"
    asked = "Carry a closed month's balances, or recompute them from its transactions?"
    assert [(q.of, q.tag, q.headline) for q in parent.questions] == [("carry-balances", "D1", asked)]
    assert f"{demo.root / 'carry-balances.md'}\n- [D1] **{asked}**" in needs.copy.text


def test_the_fallback_counts_the_questions_a_parent_at_its_close_out_asks_for_its_children(tracker: Path) -> None:
    """lamp-ui at its close-out, `built` under it asking one question: the sentence counts it, as
    the parent's row asks it."""
    ticket(tracker / f"{TREE}.md", "review", priority=1, size="L", name="Feat")
    built = tracker / "built.md"
    built.write_text(built.read_text() + "\n## Questions\n\n- [D1] **Keep the suite serial?** It is slow.\n")
    said = board.fallback(view_of(tracker))
    assert said.startswith("One build to rule on and one question wanting a word wait on you."), said


def test_a_parent_still_being_built_asks_its_own_questions_and_not_a_merged_childs(tracker: Path, repo: Path) -> None:
    """lamp-ui is claimed and asks one question; `built`, merged into its branch, asks another,
    which waits for the close-out. The sentence, the row and the group's button all count the
    parent's one."""
    ticket(tracker / f"{TREE}.md", "claimed", priority=1, size="L", name="Feat")
    for slug, question in ((TREE, "Split the lamp from the ui?"), ("built", "Keep the suite serial?")):
        path = tracker / f"{slug}.md"
        path.write_text(path.read_text() + f"\n## Questions\n\n- [D1] **{question}** It is open.\n")
    built_on_its_branch(repo)
    merged_into_the_tree(repo)
    seen = view_of(tracker)
    assert [(q.tag, q.headline) for q in seen.rows[TREE].questions] == [("D1", "Split the lamp from the ui?")]
    (group,) = [g.copy for g in seen.groups if g.copy]
    assert "Keep the suite serial?" not in group.text and group.note == "1 question", group.note
    assert board.fallback(seen).startswith("One question wanting a word waits on you.")


def test_a_rows_copy_all_names_the_file_its_questions_are_on(tracker: Path) -> None:
    """lamp-ui at its close-out asks nothing itself; `built` under it asks two: the row's copy-all
    button says it copied built's."""
    ticket(tracker / f"{TREE}.md", "review", priority=1, size="L", name="Feat")
    built = tracker / "built.md"
    built.write_text(built.read_text() + "\n## Questions\n\n- [D1] **One?** It is open.\n- [D2] **Two?** It is open.\n")
    copy_all = view_of(tracker).rows[TREE].copy_all
    assert copy_all.text.startswith(str(built)) and copy_all.note == "2 questions of built.md", copy_all.note


def built_on_its_branch(repo: Path) -> None:
    """`built`'s round: lamp-ui's branch cut from main, and ticket/built one commit ahead of it."""
    git(repo, "branch", TREE)
    git(repo, "checkout", "-q", "-b", "ticket/built", TREE)
    (repo / "built.txt").write_text("the build\n")
    git(repo, "add", "built.txt")
    git(repo, "commit", "-q", "-m", "built")
    git(repo, "checkout", "-q", "main")


def merged_into_the_tree(repo: Path) -> None:
    """The orchestrator's read passing `built`: ticket/built merged --no-ff into lamp-ui's branch."""
    git(repo, "checkout", "-q", TREE)
    git(repo, "merge", "-q", "--no-ff", "-m", "merge built", "ticket/built")
    git(repo, "checkout", "-q", "main")


def test_a_child_in_review_folds_under_its_parent_once_merged_into_its_branch(tracker: Path, repo: Path) -> None:
    """The same rule at the tracker's seam, before and after the merge the orchestrator's read
    makes: `built` is in review under lamp-ui, which is still being built."""
    built_on_its_branch(repo)
    assert "built" in rows_in(view_of(tracker), "needs"), "not merged yet: it waits for the orchestrator's read"
    merged_into_the_tree(repo)
    seen = view_of(tracker)
    assert "built" not in anywhere_in(seen, "needs")
    assert [r.ticket.slug for r in seen.rows[TREE].kids] == ["built"]


def test_a_sibling_merged_into_the_parents_branch_blocks_nothing(tracker: Path, repo: Path) -> None:
    """The board's blocked is the frontier's: `after-built` waits on `built`, its sibling under
    lamp-ui in review. It is blocked until `built` merges into lamp-ui's branch, open from then on."""
    ticket(tracker / "after-built.md", "open", parent=TREE, blocked_by=["built"])
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "after-built")
    built_on_its_branch(repo)
    assert load(tracker)["after-built"].status == "blocked", "not merged yet: nothing may build on it"
    merged_into_the_tree(repo)
    assert load(tracker)["after-built"].status == "open"
    seen = view_of(tracker)
    assert "after-built" in rows_in(seen, "open")
    assert "in review and merged into the parent ticket's branch" in mark(seen.rows["after-built"], "chip").says, (
        "the chip of a blocker that frees it says so, rather than that the row still waits"
    )


def test_every_session_listed_on_a_ticket_has_a_transcript_on_this_machine(demo: Demo) -> None:
    path = demo.root / "map-columns.md"
    listed = ticket_sessions(path, demo.repo, demo.transcripts)
    assert {s.id for s in listed} <= set(demo.sessions)
    assert [s.id for s in listed] == [S1, S2], "the sessions that committed on it, oldest first; the worker S4 is on another host"
    assert [s.title for s in listed] == [demo.sessions[s.id]["title"] for s in listed]
    assert [s.cwd for s in listed] == [demo.sessions[s.id]["cwd"] for s in listed]


def test_the_board_renders_with_no_transcripts_and_says_the_absence_once(demo: Demo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_with: Callable[..., Path]) -> None:
    monkeypatch.setattr(board, "TRANSCRIPTS", tmp_path / "no-transcripts")
    reading = board.read(demo.root, demo.repo, tmp_path / "board.html")
    assert sources(reading).count("transcripts") == 1
    assert not any(b.worked for t in reading.tickets for b in t.blocks), "no session is resumable without a transcript"


def test_the_board_renders_without_github_and_says_the_absence_once(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    reading = board.read(tracker, repo, tmp_path / "board.html")
    assert sources(reading).count("github") == 1
    assert gh_marks(reading)["acme/backend#317"][0] == "unknown", "the references stay on the row, bare"


def test_the_board_renders_without_the_model_and_says_the_absence_once(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    assert sources(board.read(tracker, repo, tmp_path / "board.html")).count("model") == 1


def test_a_board_linking_a_review_page_carries_the_note_it_shows_when_opened_as_a_file(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """Whether the review pages save is a matter of how the board was opened, which only the open
    page knows: the render writes the note hidden, once, and the page shows it as a file."""
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "quoted.html").write_text("<html>")
    notes = [a for a in board.absences(board.read(tracker, repo, tmp_path / "board.html")) if a.source == "review-page-server"]
    assert [a.hidden for a in notes] == [True]


def test_a_tracker_with_no_review_pages_rendered_says_nothing_about_the_server(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """Nothing has been sent for review yet, so there is no page a server could be answering for:
    the absence the Property names is the server for pages that exist."""
    assert "review-page-server" not in sources(board.read(tracker, repo, tmp_path / "board.html"))


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
    said = board.fallback(board.view(read))
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
    render(demo.root, demo.repo, out)
    beside = sorted(p.name for p in out.parent.iterdir())
    assert beside == ["board.html", "board.html.github.json", "board.html.stamp.js"]
    rows = load_tickets(demo.root, demo.repo, demo.root.parent)
    about = [str(t.path) for t in rows] + [t.title for t in rows] + [t.brief for t in rows if t.brief]
    about += [q.tag for t in rows for q in t.questions]
    for sidecar in beside[1:]:
        held = (out.parent / sidecar).read_text()
        assert not any(said in held for said in about), f"{sidecar} says something about a ticket"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
