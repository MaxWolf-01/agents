# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown"]
# ///
"""Checks for the board's reading of a tracker. Run: uv run test_board.py

Four seams: the tracker loader (a fixture tracker on disk in, ticket and queue state out), the
checkout discovery (a git repo with worktrees in, which copy of what is read out), the graph
sources (which tickets become nodes, in which class, joined by which edges), and the rendered
page (groups, rows, the attributes the page's script matches against the graph sources). The
oracle is the tracker's MARKDOWN.md and the board's --help: the frontier is open, unblocked,
unclaimed; a proposed ticket is not open whatever blocks it; a build in review waits for the
user's ruling in its own group and unblocks nothing until the accept writes done; a gh reference
is a link to GitHub; a row copies the absolute path of the file it was read from; a review page
is linked on the address diffview serves it on, and as a file where nothing serves it; a reference whose file no longer exists counts as done; a graph draws only
tickets with an edge; a standalone ticket a branch added is shown, one it merely inherited is
not; the needs-human.md beside a set of tickets is their queue, not a ticket; a needs-human
bullet's detail continues on indented lines.

Under "properties" at the end sit the executable Properties of
agent/tickets/board-orients/spec.md that belong to these seams, each an expected failure naming
the slice that lifts it; that spec is their oracle.
"""

import html
import itertools
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

import board
from board import (
    STATUS_SYMBOL,
    TICKET_STATUSES,
    Diffviews,
    Queue,
    Roots,
    board_graph,
    content_stamp,
    feature_graph,
    load_features,
    load_needs_human,
    load_standalone,
    needs_me,
    read_questions,
    render,
    render_page,
    serve_diffviews,
    ticket_sessions,
    tracker_roots,
    tracker_snapshot,
)
from briefing import Briefing, cache_path
from demo_tracker import S1, S2, S4, Demo

FEAT = "feat-a"  # a hyphen, so a slugged id and the raw name can be told apart
NO_QUEUE = Queue(Path("needs-human.md"), [])
STUB_ADDRESS = "http://127.0.0.1:54321"


def ticket(path: Path, status: str, blocked_by: list[str] | None = None, kind: str | None = None, gh: list[str] | None = None) -> None:
    lines = ["---", f"status: {status}"]
    if kind:
        lines.append(f"type: {kind}")
    if blocked_by:
        lines.append(f"blocked-by: [{', '.join(blocked_by)}]")
    if gh:
        lines.append(f"gh: [{', '.join(gh)}]")
    title = path.stem.split("-", 1)[1] if path.stem[:2].isdigit() else path.stem
    lines += ["---", "", f"# {title.replace('-', ' ')}", "", "Cut from the worker's closing comment on 01: the `suite` is slow.", ""]
    path.write_text("\n".join(lines))


@pytest.fixture
def tracker(tmp_path: Path) -> Path:
    root = tmp_path / "repo" / "agent" / "tickets"
    feature = root / FEAT
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("---\nstatus: confirmed\n---\n\n# Feat\n")
    (feature / "needs-human.md").write_text("- debrief :: the suite is slow, see 03\n")
    ticket(feature / "01-first.md", "done")
    ticket(feature / "02-second.md", "open")
    ticket(feature / "03-faster-suite.md", "proposed", blocked_by=["02"])
    ticket(feature / "04-uses-fast-suite.md", "open", blocked_by=["03"])
    ticket(feature / "05-after-first.md", "open", blocked_by=["01"])
    ticket(feature / "06-needs-chore.md", "open", blocked_by=["small-chore"])
    ticket(feature / "07-built.md", "review", blocked_by=["01"], gh=["acme/backend#317", "acme/helix#412"])
    ticket(root / "loose-idea.md", "proposed", blocked_by=[f"{FEAT}/02"])
    ticket(root / "small-chore.md", "open")
    (root / "quoted.md").write_text(f'---\nstatus: open\nblocked-by: [{FEAT}/01]\n---\n\n# Say "no limit" plainly\n')
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


def load(root: Path):
    dv = Diffviews(root.parent / "diffviews", None)
    features = load_features(root, {}, dv)
    standalone = load_standalone(Roots(root, []), dv)
    return features, standalone


def by_num(feature):
    return {t.num: t for t in feature.tickets}


def page_of(root: Path) -> str:
    features, standalone = load(root)
    return render_page("demo", features, standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")


# ---- loader ---------------------------------------------------------------


def test_a_proposed_ticket_is_off_the_frontier_whatever_blocks_it(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    assert by_num(feature)["03"].status == "proposed"
    assert {k.slug: k.status for k in standalone} == {"loose-idea": "proposed", "quoted": "open", "small-chore": "open"}
    frontier = sorted(t.num for t in feature.tickets if t.status == "open")
    assert frontier == ["02", "05"]


def test_a_ticket_waiting_on_a_proposal_is_blocked_until_the_ruling_lands_as_done(tracker: Path) -> None:
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / FEAT / "03-faster-suite.md", "open", blocked_by=["02"])
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / FEAT / "03-faster-suite.md", "review")  # built, waiting for the ruling: still not done
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "blocked"
    ticket(tracker / FEAT / "03-faster-suite.md", "done")
    (feature,), _ = load(tracker)
    assert by_num(feature)["04"].status == "open"


def test_a_feature_ticket_waits_on_a_standalone_ticket_by_slug(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    assert by_num(feature)["06"].status == "blocked"
    ticket(tracker / "small-chore.md", "done")
    (feature,), _ = load(tracker)
    assert by_num(feature)["06"].status == "open"


def test_a_status_the_tracker_does_not_know_is_refused_with_the_file_named(tracker: Path) -> None:
    ticket(tracker / FEAT / "02-second.md", "opne")
    with pytest.raises(AssertionError, match=r"02-second\.md: status 'opne'"):
        load(tracker)


def test_a_gh_reference_that_is_not_owner_repo_number_is_refused_with_the_file_named(tracker: Path) -> None:
    ticket(tracker / FEAT / "07-built.md", "review", gh=["https://github.com/acme/backend/pull/317"])
    with pytest.raises(AssertionError, match=r"07-built\.md: gh reference 'https://github.com/acme/backend/pull/317'"):
        load(tracker)


def test_a_queue_entry_keeps_its_indented_detail(tmp_path: Path) -> None:
    queue = tmp_path / "needs-human.md"
    queue.write_text(
        "- debrief :: **fixed** a1b2c3 pins the averaging rule.\n"
        "  **proposed** 03, 04.\n\n"
        "  **left** two case-flip survivors, the value is case-insensitive.\n"
        "- Which colour :: the prototype at agent/prototypes/colour\n"
    )
    assert load_needs_human(queue).entries == [
        "debrief :: **fixed** a1b2c3 pins the averaging rule.\n**proposed** 03, 04.\n\n**left** two case-flip survivors, the value is case-insensitive.",
        "Which colour :: the prototype at agent/prototypes/colour",
    ]


# ---- graphs ---------------------------------------------------------------


def test_a_rejected_proposal_unblocks_what_waited_on_it_and_leaves_the_graph(tracker: Path) -> None:
    (tracker / FEAT / "03-faster-suite.md").unlink()
    (feature,), standalone = load(tracker)
    assert by_num(feature)["04"].status == "open"
    assert by_num(feature)["04"].blocked_by == []
    graph = feature_graph(feature)
    # 04 waits on nothing now and nothing waits on it: a row, not a node
    assert "uses fast suite" not in graph
    # 05 still waits on the done 01, which is drawn as its dashed context
    assert '01 first"]:::ghost' in graph
    assert "T_f_feat_a_01 --> T_f_feat_a_05" in graph
    assert "uses fast suite" not in str(board_graph([feature], standalone))


def test_a_feature_whose_tickets_wait_on_nothing_has_no_graph(tmp_path: Path) -> None:
    root = tmp_path / "agent" / "tickets"
    (root / "solo").mkdir(parents=True)
    ticket(root / "solo" / "01-only.md", "open")
    (feature,), standalone = load(root)
    assert feature_graph(feature) is None
    assert board_graph([feature], standalone) is None
    page = render_page("demo", [feature], standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert "nothing in solo waits on anything" in page
    assert "nothing waits on anything" in page


def test_a_proposed_ticket_is_a_node_in_its_own_class_once_something_waits_on_it(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    graph = feature_graph(feature)
    assert '03 faster suite"]:::proposed' in graph
    assert "T_f_feat_a_02 --> T_f_feat_a_03" in graph and "T_f_feat_a_03 --> T_f_feat_a_04" in graph
    assert 'click T_f_feat_a_03 "#t-feat-a-03"' in graph


def test_the_whole_tracker_graph_is_parts_per_feature_with_edges_naming_both_ends(tracker: Path) -> None:
    (feature,), standalone = load(tracker)
    parts = board_graph([feature], standalone)
    assert [f["name"] for f in parts["features"]] == [FEAT, "standalone"]
    ids = {f["name"]: [n["id"] for n in f["nodes"]] for f in parts["features"]}
    assert ids[FEAT] == ["T_b_feat_a_01", "T_b_feat_a_02", "T_b_feat_a_03", "T_b_feat_a_04", "T_b_feat_a_05", "T_b_feat_a_06", "T_b_feat_a_07"]
    assert ids["standalone"] == ["K_b_loose_idea", "K_b_quoted", "K_b_small_chore"]
    edges = {(e["a"], e["from"], e["b"], e["to"]) for e in parts["edges"]}
    assert (FEAT, "T_b_feat_a_02", "standalone", "K_b_loose_idea") in edges
    assert ("standalone", "K_b_small_chore", FEAT, "T_b_feat_a_06") in edges
    assert (FEAT, "T_b_feat_a_01", "standalone", "K_b_quoted") in edges
    lines = "\n".join(line for f in parts["features"] for n in f["nodes"] for line in n["lines"])
    assert 'loose idea"]:::proposed' in lines
    assert '◉ 07 built"]:::review' in lines
    assert '01 first"]:::ghost' in lines
    # a raw double quote in a label ends mermaid's string and breaks the whole flowchart
    assert 'K_b_quoted["○ Say ”no limit” plainly"]' in lines
    assert (FEAT, "T_b_feat_a_01", FEAT, "T_b_feat_a_05") in edges


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
    parts = board_graph(features, standalone)
    lines = "\n".join(line for f in parts["features"] for n in f["nodes"] for line in n["lines"])
    assert '01 storage"]:::ghost' in lines
    assert "cleanup" not in lines
    assert [(e["a"], e["b"], e["line"]) for e in parts["edges"]] == [("base", "top", "  T_b_base_01 --> T_b_top_01")]


# ---- page -----------------------------------------------------------------


def test_the_page_groups_rows_by_state_needs_me_first_and_done_folded(tracker: Path) -> None:
    page = page_of(tracker)
    assert re.findall(r'id="grp-(\w+)"', page) == ["needs", "review", "open", "blocked", "proposed", "done", "log"]
    assert '<h2>proposed <span class="n">2</span></h2>' in page  # 03 and the loose idea
    assert '<details class="grp" id="grp-done" data-state="done"><summary>' in page
    assert '<details class="grp" id="grp-open" data-state="open" open>' in page
    # a build waiting for the ruling is the user's to act on: its group sits right after the queue, unfolded
    assert '<details class="grp" id="grp-review" data-state="review" open><summary><h2>needs my review <span class="n">1</span></h2>' in page
    assert f'class="ticket row-review" id="t-{FEAT}-07"' in page
    assert f'class="ticket row-proposed" id="t-{FEAT}-03" data-feature="{FEAT}" data-num="03"' in page
    assert f'id="t-{FEAT}-03"' in page and 'class="badge proposed"' not in page  # the group says the status; a row does not repeat it
    assert f'id="needs-{FEAT}-0" data-feature="{FEAT}"' in page


def test_a_feature_chip_carries_the_counts_as_its_tooltip(tracker: Path) -> None:
    page = page_of(tracker)
    assert (
        f'<button class="featchip" data-feature="{FEAT}" title="spec confirmed · 1/6 done · 2 open · 1 review · 2 blocked · 1 proposed · 1 need me">'
        f'<i class="dot"></i>{FEAT} <span class="dim">1/6</span></button>' in page
    )
    assert 'standalone <span class="dim">3</span>' in page


def test_a_feature_with_a_build_in_review_and_no_queue_still_gets_the_dot(tmp_path: Path) -> None:
    root = tmp_path / "agent" / "tickets"
    (root / "solo").mkdir(parents=True)
    ticket(root / "solo" / "01-only.md", "review")
    (feature,), standalone = load(root)
    page = render_page("demo", [feature], standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert '<button class="featchip" data-feature="solo" title="0/1 done · 1 review"><i class="dot"></i>solo' in page


def test_a_gh_reference_is_a_link_on_the_row_and_in_its_search_text(tracker: Path) -> None:
    ticket(tracker / "quoted.md", "open", gh=["acme/coding#137"])
    page = page_of(tracker)
    assert (
        '<a class="dv gh" href="https://github.com/acme/backend/issues/317" target="_blank" onclick="event.stopPropagation()" title="on GitHub">acme/backend#317</a>'
        '<a class="dv gh" href="https://github.com/acme/helix/issues/412"' in page
    )
    assert 'href="https://github.com/acme/coding/issues/137"' in page
    searches = dict(re.findall(r'id="([\w-]+)" data-feature="[\w-]+" data-num="[^"]+" data-search="([^"]*)"', page))
    assert "acme/backend#317 acme/helix#412" in searches[f"t-{FEAT}-07"]
    assert "acme/coding#137" in searches["standalone-quoted"]


def test_a_row_carries_what_the_page_script_matches_against_the_graphs(tracker: Path) -> None:
    """The script hides rows by the chip's raw feature name, filters on data-search with
    String.includes, and marks the node T_f_<slug>_<num> (K_b_<slug> for a standalone ticket)
    in the graph container of the row's feature."""
    (feature,), standalone = load(tracker)
    page = render_page("demo", [feature], standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert page.count(f'data-feature="{FEAT}"') == 1 + len(feature.tickets) + 1 + 1  # chip, rows, needs row, graph container
    rows = re.findall(r'<details class="ticket row-\w+" id="([\w-]+)" data-feature="([\w-]+)" data-num="([^"]+)" data-search="([^"]*)"', page)
    assert len(rows) == len(feature.tickets) + len(standalone) + 1
    searches = {row_id: html.unescape(search) for row_id, _, _, search in rows}  # the script reads the attribute unescaped
    assert searches[f"t-{FEAT}-03"] == "03 faster suite cut from the worker's closing comment on 01: the suite is slow."
    assert all(s == s.lower() and "<" not in s for s in searches.values())
    graph = re.search(rf'<div class="g" data-feature="{FEAT}" hidden><pre class="mermaid" data-key="g:{FEAT}">(.*?)</pre>', page, re.S).group(1)
    for row_id, feat, num, _ in rows:
        if feat == FEAT and num in ("02", "03", "04", "05", "07"):  # the rows with an edge
            assert f"T_f_{feat.replace('-', '_')}_{num}[" in graph, row_id
    assert '<div class="g" data-feature="*" hidden><pre class="mermaid" data-key="g:*"></pre>' in page
    assert '"id": "K_b_quoted"' in page


def test_a_row_links_its_review_page(tracker: Path) -> None:
    dv = tracker.parent / "diffviews"
    (dv / FEAT).mkdir(parents=True)
    (dv / FEAT / "02-second.html").write_text("<html>")
    (dv / "quoted.html").write_text("<html>")
    page = page_of(tracker)
    assert f'href="file://{dv / FEAT / "02-second.html"}"' in page
    assert f'href="file://{dv / "quoted.html"}"' in page
    assert page.count('class="dv"') == 4  # a chip on each row, and the line at the top of each expanded ticket
    assert '<p class=dvline><a class="dv"' in page


def test_a_row_links_its_review_page_on_the_address_diffview_serves(tracker: Path, stub_diffview: Path) -> None:
    """A page opened as a file is read-only, so a review that starts from the board has to land on
    the served one, at the address diffview names for that directory of pages."""
    dv = tracker.parent / "diffviews"
    (dv / FEAT).mkdir(parents=True)
    (dv / FEAT / "02-second.html").write_text("<html>")
    (dv / "quoted.html").write_text("<html>")
    diffviews = serve_diffviews(dv)
    assert Path(f"{stub_diffview}.args").read_text().split() == ["--serve", str(dv)]
    features = load_features(tracker, {}, diffviews)
    standalone = load_standalone(Roots(tracker, []), diffviews)
    page = render_page("demo", features, standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert f'href="{STUB_ADDRESS}/{FEAT}/02-second.html"' in page
    assert f'href="{STUB_ADDRESS}/quoted.html"' in page


def test_a_review_page_nothing_serves_is_linked_as_the_file_it_is(tracker: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine without diffview has the pages but no server for them."""
    dv = tracker.parent / "diffviews"
    (dv / FEAT).mkdir(parents=True)
    (dv / FEAT / "02-second.html").write_text("<html>")
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools"))
    assert serve_diffviews(dv).link(dv / FEAT, "02-*.html") == f"file://{dv / FEAT / '02-second.html'}"


def test_class_defs_cover_every_status(tracker: Path) -> None:
    page = page_of(tracker)
    class_defs = re.search(r'const classDefs = \[([^\]]*)\]', page).group(1)
    for status in STATUS_SYMBOL:
        assert f'"{status}"' in class_defs
        assert f"--{status}-bg:" in page  # the classDef reads its colours off these tokens


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
    """The tracker committed on main, and a worktree on the feature's branch beside the repo."""
    repo = tracker.parent.parent
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tracker")
    git(repo, "worktree", "add", "-q", str(repo.parent / "wt"), "-b", FEAT)
    return repo


def test_a_standalone_ticket_a_branch_added_is_shown_and_one_it_inherited_is_not(repo: Path, tracker: Path) -> None:
    wt = repo.parent / "wt"
    # main retires a chore after the branch was cut; the branch's inherited copy must not bring it back
    git(repo, "rm", "-q", "agent/tickets/small-chore.md")
    git(repo, "commit", "-q", "-m", "small-chore: done")
    branch_root = wt / "agent" / "tickets"
    ticket(branch_root / "filed-on-branch.md", "open")  # untracked on the branch
    (branch_root / "notes.md").write_text("# not a ticket\n\njust a note beside the tickets\n")
    ticket(branch_root / "loose-idea.md", "open", blocked_by=[f"{FEAT}/02"])  # changed on the branch; main's copy wins
    ticket(branch_root / FEAT / "02-second.md", "claimed")  # a feature ticket changed on the branch is not a standalone one
    roots = tracker_roots(tracker)
    assert roots.main == tracker
    assert roots.repo == repo
    assert roots.branches == [(FEAT, branch_root)]
    assert roots.overrides == {FEAT: branch_root / FEAT}
    dv = Diffviews(tracker.parent / "diffviews", None)
    standalone = load_standalone(roots, dv)
    assert {k.slug: k.source for k in standalone} == {"loose-idea": None, "quoted": None, "filed-on-branch": FEAT}
    assert {k.slug: k.status for k in standalone}["loose-idea"] == "proposed"
    features = load_features(tracker, roots.overrides, dv)
    assert by_num(features[0])["02"].status == "claimed"  # the feature directory is read from the worktree
    page = render_page("demo", features, standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert f'title="filed on branch {FEAT}, not on the main branch">on {FEAT}</span>' in page


def test_a_row_copies_the_path_of_the_file_the_board_read(repo: Path, tracker: Path) -> None:
    """A feature in flight is read from its worktree and a ticket filed on a branch exists only
    there, so the main checkout's copy is the wrong path to hand to a session."""
    branch_root = repo.parent / "wt" / "agent" / "tickets"
    ticket(branch_root / "filed-on-branch.md", "open")
    (tracker / "needs-human.md").write_text("- rule on loose-idea :: built while proposed\n")
    roots = tracker_roots(tracker)
    dv = Diffviews(tracker.parent / "diffviews", None)
    features = load_features(tracker, roots.overrides, dv)
    standalone = load_standalone(roots, dv)
    page = render_page("demo", features, standalone, load_needs_human(tracker / "needs-human.md"), log="", stamp="s", stamp_src="s.js")
    paths = dict(re.findall(r'<details class="ticket row-\w+" id="([\w-]+)" [^>]*data-path="([^"]*)"', page))
    assert paths[f"t-{FEAT}-02"] == str(branch_root / FEAT / "02-second.md")
    assert paths[f"needs-{FEAT}-0"] == str(branch_root / FEAT / "needs-human.md")
    assert paths["standalone-filed-on-branch"] == str(branch_root / "filed-on-branch.md")
    assert paths["standalone-quoted"] == str(tracker / "quoted.md")
    assert paths["needs-standalone-0"] == str(tracker / "needs-human.md")


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
    ticket(wt / "agent" / "tickets" / FEAT / "02-second.md", "done")
    git(wt, "commit", "-q", "-am", "02 landed")
    assert tracker_roots(tracker).branches == [(FEAT, wt / "agent" / "tickets")]
    git(repo, "merge", "-q", "--no-ff", "-m", "feat-a: landed", FEAT)
    roots = tracker_roots(tracker)
    assert roots.branches == [] and roots.overrides == {}


def test_a_tracker_the_main_checkout_does_not_have_yet_renders_from_the_worktree(repo: Path, tracker: Path) -> None:
    git(repo, "rm", "-q", "-r", "agent/tickets")
    git(repo, "commit", "-q", "-m", "tracker moved out")
    roots = tracker_roots(repo.parent / "wt" / "agent" / "tickets")  # run from the worktree, the only tracker there is
    assert not roots.main.is_dir() and roots.overrides
    dv = Diffviews(roots.main.parent / "diffviews", None)
    features = load_features(roots.main, roots.overrides, dv)
    standalone = load_standalone(roots, dv)
    assert [f.name for f in features] == [FEAT]
    assert standalone == []  # the branch changed nothing at the tracker root


def test_the_stamp_changes_with_a_standalone_ticket_source(tracker: Path) -> None:
    features, standalone = load(tracker)
    before = content_stamp("demo", features, standalone, NO_QUEUE, "")
    standalone[0].source = "some-branch"
    assert content_stamp("demo", features, standalone, NO_QUEUE, "") != before


# ---- queues ---------------------------------------------------------------


def test_the_standalone_queue_is_the_tracker_roots_own_and_not_a_ticket(tracker: Path) -> None:
    (tracker / "needs-human.md").write_text("- rule on loose-idea :: built while proposed; its page is agent/diffviews/loose-idea.html\n")
    features, standalone = load(tracker)
    assert "needs-human" not in {k.slug for k in standalone}
    queue = load_needs_human(tracker / "needs-human.md")
    page = render_page("demo", features, standalone, queue, log="", stamp="s", stamp_src="s.js")
    assert 'id="needs-standalone-0" data-feature="standalone"' in page
    assert f'id="needs-{FEAT}-0" data-feature="{FEAT}"' in page


def test_a_queue_entry_outliving_its_ticket_still_shows_with_a_chip_to_toggle_it(tracker: Path) -> None:
    # the ruling on the last standalone ticket was `reject`, which deletes the file
    features, _ = load(tracker)
    queue = Queue(tracker / "needs-human.md", ["rule on loose-idea :: rejected"])
    page = render_page("demo", features, [], queue, log="", stamp="s", stamp_src="s.js")
    assert 'id="needs-standalone-0" data-feature="standalone"' in page
    assert '<button class="featchip" data-feature="standalone"' in page


def test_the_stamp_the_open_tab_polls_moves_when_the_queue_does(tracker: Path) -> None:
    features, standalone = load(tracker)
    path = tracker / "needs-human.md"
    assert content_stamp("demo", features, standalone, Queue(path, ["an entry"]), "") != content_stamp("demo", features, standalone, Queue(path, []), "")


def test_render_reads_the_queue_beside_the_standalone_tickets(repo: Path, tracker: Path, tmp_path: Path) -> None:
    (tracker / "needs-human.md").write_text("- rule on loose-idea :: built while proposed\n")
    out = tmp_path / "out" / "board.html"
    render(tracker_roots(tracker), repo, out)
    assert "rule on loose-idea" in out.read_text()


def test_an_unblocked_proposal_is_claimable_and_still_waits_for_its_ruling(tracker: Path) -> None:
    """The live case: a proposal an agent filed with nothing blocking it (`/mx:tracker`)."""
    ticket(tracker / FEAT / "08-render-check.md", "proposed")
    (feature,), standalone = load(tracker)
    assert by_num(feature)["08"].status == "proposed"
    assert by_num(feature)["08"].blocked_by == []
    page = render_page("demo", [feature], standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    proposed = page.split('id="grp-proposed"')[1].split('class="grp" id="grp-')[0]
    assert f'id="t-{FEAT}-08"' in proposed


# ---- properties -----------------------------------------------------------
# The executable Properties of agent/tickets/board-orients/spec.md that live at these seams. Each
# is an expected failure naming the slice that lifts it; one that already holds carries none.


def runs(record: Path) -> list[str]:
    """What the board ran a stub tool with, one line per run (the path_with fixture)."""
    return record.read_text().splitlines() if record.exists() else []


def absences(page: str, source: str) -> int:
    """How often the page says it did without `source` (board.absence_note)."""
    return page.count(f'data-absent="{source}"')


def rows_in(page: str, group: str) -> set[str]:
    """The ticket rows one of the board's groups holds; a queue entry, which is not a ticket, is not one."""
    body = page.split(f'id="grp-{group}"', 1)[1].split('class="grp" id="grp-', 1)[0]
    return {r for r in re.findall(r'<details class="ticket [^"]*" id="([\w-]+)"', body) if r.startswith(("t-", "standalone-"))}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="needs_me is a stub; lifted by 03-questions-and-needs-me")
def test_a_ticket_is_in_needs_me_exactly_when_it_waits_on_a_ruling_an_answer_or_a_design_session() -> None:
    """The whole space of what a ticket file can say, since it is small enough to enumerate.

    Two readings the spec's sentence leaves open: a design session is a grilling or a prototype
    decision, the two types the user sits for; and "nobody has claimed" means open or proposed,
    since a blocked or done ticket is not the user's to sit for either.
    """
    space = itertools.product(
        sorted(TICKET_STATUSES | {"blocked"}),
        [None, "research", "prototype", "grilling", "legwork"],
        [None, 1, 2, 3, 4, 5],
        [False, True],
    )
    for status, kind, priority, open_question in space:
        waits = status != "done" and (
            status == "review"
            or open_question
            or (kind in ("grilling", "prototype") and priority in (1, 2) and status in ("open", "proposed"))
        )
        assert needs_me(status, kind, priority, open_question) is waits, (status, kind, priority, open_question)


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


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="read_questions is a stub; lifted by 03-questions-and-needs-me")
@given(asked=QUESTIONS)
def test_a_question_a_ruled_line_answers_is_never_open(asked: tuple[int, list[tuple[str, str, str | None]]]) -> None:
    first, items = asked
    read = read_questions(ticket_asking(first, items))
    assert [q.tag for q in read] == [f"D{n}" for n in range(first, first + len(items))]
    assert [q.headline for q in read] == [headline for headline, _, _ in items]
    assert [q.ruled is None for q in read] == [ruled is None for _, _, ruled in items]
    assert all(detail in q.detail and "Ruled" not in q.detail for q, (_, detail, _) in zip(read, items))


# what the demo tracker's tickets ask of the user: the two builds in review, and every ticket with a
# question no Ruled line answers. staging-credentials, whose one question is ruled, is not one.
NEEDS_ME = {
    "t-csv-import-02", "t-saved-views-01", "t-saved-views-03", "standalone-flaky-upload-test",
    "standalone-pick-a-date-library", "standalone-retire-legacy-exporter", "standalone-speed-up-tests",
}


@pytest.mark.xfail(strict=True, reason="the board has no needs-me group yet; lifted by 03-questions-and-needs-me")
def test_the_needs_me_group_holds_exactly_the_tickets_that_wait_on_the_user(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The same two properties as the checks above, at the seam the spec's Testing Decisions names:
    a fixture tracker on disk in, groups out. 02-map-columns keeps its questions on its ticket
    branch, so the board has to read them there."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    assert rows_in(out.read_text(), "needs") == NEEDS_ME
    assert "standalone-staging-credentials" not in rows_in(out.read_text(), "needs"), "its one question is ruled"


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="ticket_sessions is a stub; lifted by 05-sessions")
def test_every_session_listed_on_a_ticket_has_a_transcript_on_this_machine(demo: Demo) -> None:
    ticket = demo.root / "csv-import" / "02-map-columns.md"
    listed = ticket_sessions(ticket, demo.repo, demo.transcripts)
    assert {s.id for s in listed} <= set(demo.sessions)
    assert [s.id for s in listed] == [S1, S2], "the sessions that committed on it, oldest first; the worker S4 is on another host"
    assert [s.title for s in listed] == [demo.sessions[s.id]["title"] for s in listed]
    assert [s.cwd for s in listed] == [demo.sessions[s.id]["cwd"] for s in listed]


@pytest.mark.xfail(strict=True, reason="the board lists no sessions yet; lifted by 05-sessions")
def test_the_board_renders_with_no_transcripts_and_says_the_absence_once(demo: Demo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_with: Callable[..., Path]) -> None:
    monkeypatch.setattr(board, "TRANSCRIPTS", tmp_path / "no-transcripts")
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    page = out.read_text()
    assert absences(page, "transcripts") == 1
    assert S1 not in page and S4 not in page, "no session is resumable without a transcript"


@pytest.mark.xfail(strict=True, reason="the board asks GitHub nothing yet; lifted by 07-github-state")
def test_the_board_renders_without_github_and_says_the_absence_once(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    page = out.read_text()
    assert absences(page, "github") == 1
    assert "acme/backend#317" in page, "the references stay on the row, bare"


@pytest.mark.xfail(strict=True, reason="the board has no briefing yet; lifted by 09-briefing")
def test_the_board_renders_without_the_model_and_says_the_absence_once(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    assert absences(out.read_text(), "model") == 1


def test_the_board_renders_with_no_review_page_server_and_links_its_pages_as_files(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    dv = tracker.parent / "diffviews"
    dv.mkdir(parents=True)
    (dv / "quoted.html").write_text("<html>")
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    assert f'href="file://{dv / "quoted.html"}"' in out.read_text()


@pytest.mark.xfail(strict=True, reason="the board asks GitHub nothing yet; lifted by 07-github-state")
def test_a_render_that_finds_nothing_changed_makes_no_github_request(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    gh = path_with("gh", 'echo "{}"')
    out = tmp_path / "board.html"
    queries = lambda: [r for r in runs(gh) if "graphql" in r]  # noqa: E731 — an auth probe is not a request for a reference
    render(tracker_roots(tracker), repo, out)
    assert len(queries()) == 1, "one query per render resolves both references"
    render(tracker_roots(tracker), repo, out)
    assert len(queries()) == 1, "the answer cached beside the board serves the unchanged render"


@pytest.mark.xfail(strict=True, reason="the board has no briefing yet; lifted by 09-briefing")
def test_a_render_that_finds_nothing_changed_makes_no_model_call(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    claude = path_with("claude")
    out = tmp_path / "board.html"
    when = datetime.fromisoformat("2026-09-21T09:30:00+02:00")
    briefing = Briefing("Two builds wait on your ruling.", when, "abc-123", when, when, 2)
    briefing.write(cache_path(out))
    render(tracker_roots(tracker), repo, out)
    render(tracker_roots(tracker), repo, out)
    assert runs(claude) == [], "an unchanged tracker has nothing to tell the briefing session"
    assert briefing.text in out.read_text(), "the board shows the briefing the cache holds"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
