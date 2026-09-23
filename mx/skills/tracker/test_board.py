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
from html.parser import HTMLParser
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


def ticket(
    path: Path, status: str, blocked_by: list[str] | None = None, kind: str | None = None,
    gh: list[str] | None = None, priority: int | None = None, size: str | None = None,
    brief: str | None = None, name: str | None = None,
) -> None:
    lines = ["---", f"status: {status}"]
    if kind:
        lines.append(f"type: {kind}")
    if blocked_by:
        lines.append(f"blocked-by: [{', '.join(blocked_by)}]")
    if gh:
        lines.append(f"gh: [{', '.join(gh)}]")
    if priority:
        lines.append(f"priority: {priority}")
    if size:
        lines.append(f"size: {size}")
    title = path.stem.split("-", 1)[1] if path.stem[:2].isdigit() else path.stem
    lines += ["---", "", f"# {name or title.replace('-', ' ')}", ""]
    if brief:
        lines += ["## Brief", "", brief, ""]
    lines += ["## What to build", "", "Cut from the worker's closing comment on 01: the `suite` is slow.", ""]
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
    features = load_features(root, {}, dv, None)
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
    assert re.findall(r'id="grp-(\w+)"', page) == ["needs", "open", "blocked", "proposed", "done", "log"]
    assert '<h2>proposed <span class="n">2</span></h2>' in page  # 03 and the loose idea
    assert '<details class="grp" id="grp-done" data-state="done"><summary>' in page
    assert '<details class="grp" id="grp-open" data-state="open" open>' in page
    # a build waiting for the ruling is the user's to act on: it sits in needs me, beside the queue
    assert '<details class="grp" id="grp-needs" data-state="needs" open><summary><h2>needs me <span class="n">2</span>' in page
    assert rows_in(page, "needs") == {f"t-{FEAT}-07"}, "the queue entry is not a ticket"
    assert f'class="ticket row-review" id="t-{FEAT}-07"' in page
    assert f'class="ticket row-proposed" id="t-{FEAT}-03" data-feature="{FEAT}" data-num="03"' in page
    assert f'id="t-{FEAT}-03"' in page and 'class="badge proposed"' not in page  # the group says the status; a row does not repeat it
    assert f'id="needs-{FEAT}-0" data-feature="{FEAT}"' in page


def test_a_feature_chip_carries_the_counts_as_its_tooltip(tracker: Path) -> None:
    page = page_of(tracker)
    assert (
        f'<button class="featchip" data-feature="{FEAT}" title="spec confirmed · 1/7 done · 2 open · 1 review · 2 blocked · 1 proposed · 1 need me">'
        f'<i class="dot"></i>{FEAT} <span class="dim">1/7</span></button>' in page
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
        '<a class="gh" href="https://github.com/acme/backend/issues/317" target="_blank" '
        'onclick="event.stopPropagation()" data-tip="A pull request or issue this ticket names, on GitHub.">acme/backend#317</a>'
        '<a class="gh" href="https://github.com/acme/helix/issues/412"' in page
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
    assert searches[f"t-{FEAT}-03"] == "03 faster suite what to build cut from the worker's closing comment on 01: the suite is slow."
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
    assert page.count('class="rp"') == 2  # once per row (the spec's Decisions), on the name's line


def test_a_row_links_its_review_page_on_the_address_diffview_serves(tracker: Path, stub_diffview: Path) -> None:
    """A page opened as a file is read-only, so a review that starts from the board has to land on
    the served one, at the address diffview names for that directory of pages."""
    dv = tracker.parent / "diffviews"
    (dv / FEAT).mkdir(parents=True)
    (dv / FEAT / "02-second.html").write_text("<html>")
    (dv / "quoted.html").write_text("<html>")
    diffviews = serve_diffviews(dv)
    assert Path(f"{stub_diffview}.args").read_text().split() == ["--serve", str(dv)]
    features = load_features(tracker, {}, diffviews, None)
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
    features = load_features(tracker, roots.overrides, dv, roots.repo)
    assert by_num(features[0])["02"].status == "claimed"  # the feature directory is read from the worktree
    page = render_page("demo", features, standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert f'data-tip="Filed on branch {FEAT}, not on the main branch.">on {FEAT}</span>' in page


def test_a_row_copies_the_path_of_the_file_the_board_read(repo: Path, tracker: Path) -> None:
    """A feature in flight is read from its worktree and a ticket filed on a branch exists only
    there, so the main checkout's copy is the wrong path to hand to a session."""
    branch_root = repo.parent / "wt" / "agent" / "tickets"
    ticket(branch_root / "filed-on-branch.md", "open")
    (tracker / "needs-human.md").write_text("- rule on loose-idea :: built while proposed\n")
    roots = tracker_roots(tracker)
    dv = Diffviews(tracker.parent / "diffviews", None)
    features = load_features(tracker, roots.overrides, dv, roots.repo)
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
    features = load_features(roots.main, roots.overrides, dv, roots.repo)
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


# ---- rows ------------------------------------------------------------------
# The marks' words come from the spec, not from board.py: these literals are the spec's own
# ("The ticket file": XS under 15 min ... XL several sessions; priority 1 to 5 named now, next,
# soon, later, someday; "The board": what the row asks is one of seven words).
SIZE_WORDS = {"XS": ("15 min", "under 15 min"), "S": ("20 min", "about 20 min"), "M": ("1 h", "about an hour"),
              "L": ("half a day", "half a day"), "XL": ("several sessions", "several sessions")}
PRIORITY_WORDS = {1: "now", 2: "next", 3: "soon", 4: "later", 5: "someday"}
ASK_WORDS = {"review": "to rule on", "answer": "your answer", "design": "design session",
             "prototype": "prototype", "research": "research", "legwork": "legwork", "build": "build"}
MARKS = {"ftag", "num", "asks", "time", "pri", "chip", "rp", "gh", "src", "qtag", "qhead", "copier"}


def rows_of(page: str) -> dict[str, str]:
    """Each ticket row's markup, by row id, in the order the page lists them."""
    found = re.findall(r'<details class="ticket [^"]*" id="([\w-]+)"(.*?)</details>', page, re.S)
    return {row_id: body for row_id, body in found}


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
    short name, the brief from `## Brief`. A ticket whose file is silent shows its row without
    those marks rather than inventing them."""
    root = tmp_path / "agent" / "tickets"
    (root / "ledger").mkdir(parents=True)
    ticket(root / "ledger" / "01-map-columns.md", "open", priority=1, size="M",
           name="Map columns once per bank", brief="You tell the importer once which column holds the `date`.")
    ticket(root / "ledger" / "02-silent.md", "open")
    (feature,), _ = load(root)
    mapped, silent = feature.tickets
    assert (mapped.priority, mapped.size) == (1, "M")
    assert mapped.title == "Map columns once per bank", "the H1 is the short name"
    assert mapped.brief == "You tell the importer once which column holds the <code>date</code>."
    assert (silent.priority, silent.size, silent.brief) == (None, None, "")
    page = render_page("demo", [feature], [], NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    rows = rows_of(page)
    shown = {mark: text for mark, text, _ in marks_on(rows["t-ledger-01"]) if mark in MARKS}
    assert shown["time"] == "1 h" and shown["pri"] == "p1 now"
    assert "Map columns once per bank" in rows["t-ledger-01"]
    assert "which column holds the <code>date</code>" in rows["t-ledger-01"]
    assert {mark for mark, _, _ in marks_on(rows["t-ledger-02"])}.isdisjoint({"time", "pri", "brief"})
    assert "## Brief" not in page and "<h2>Brief</h2>" not in page, "the brief has one home, and it is the row"
    # the brief is searchable, since the filter is how a reader narrows to a word they remember
    assert "which column holds the date" in html.unescape(
        re.search(r'id="t-ledger-01" [^>]*data-search="([^"]*)"', page).group(1)
    )


def test_a_priority_or_size_the_tracker_does_not_know_is_refused_with_the_file_named(tracker: Path) -> None:
    ticket(tracker / FEAT / "02-second.md", "open", priority=9)
    with pytest.raises(AssertionError, match=r"02-second\.md: priority 9"):
        load(tracker)
    ticket(tracker / FEAT / "02-second.md", "open", size="HUGE")
    with pytest.raises(AssertionError, match=r"02-second\.md: size 'HUGE'"):
        load(tracker)


def test_every_size_and_priority_shows_the_word_the_spec_gives_it(tmp_path: Path) -> None:
    """Five sizes and five priorities, each on a row of its own: the words the user reads are the
    spec's, and the tip's own definition of a mark stays in step with the word beside it."""
    root = tmp_path / "agent" / "tickets"
    (root / "ledger").mkdir(parents=True)
    for i, size in enumerate(SIZE_WORDS, start=1):
        ticket(root / "ledger" / f"0{i}-sized.md", "open", size=size, priority=i)
    (feature,), _ = load(root)
    page = render_page("demo", [feature], [], NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    rows = rows_of(page)
    for i, (size, (word, means)) in enumerate(SIZE_WORDS.items(), start=1):
        row = rows[f"t-ledger-0{i}"]
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
    (root / "ledger").mkdir(parents=True)
    ticket(root / "ledger" / "01-quick.md", "review", priority=2, size="S")
    ticket(root / "ledger" / "02-long-haul.md", "open", priority=5, size="XL", blocked_by=["01"])
    # a standalone ticket writes its blocker qualified, which is the widest a reference gets
    ticket(root / "waits-on-the-haul.md", "open", priority=3, size="M", blocked_by=["ledger/02"])
    features, standalone = load(root)
    page = render_page("demo", features, standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert columns_for(page, ":root") == {
        "ftag": str(len("standalone")),  # longer than the one feature's name
        "num": str(len("--")),
        "asks": str(len("design session")),  # the widest of the spec's seven words
        "time": str(len("several sessions")),
        "pri": str(len("p5 someday")),
        "chips": str(len("ledger/02")),
    }
    # the group whose only ticket is an S at p2 with nothing waiting on it leaves the rest of that
    # width to the name and the brief
    assert columns_for(page, "#grp-needs") == {"time": str(len("20 min")), "pri": str(len("p2 next")), "chips": "0"}
    # the group that holds the XL ticket keeps the board's width for every one of the three
    # the group holding the XL ticket and the widest reference narrows none of the three
    narrowed = columns_for(page, "#grp-blocked")
    assert narrowed == {}, f"the blocked group narrows {sorted(narrowed)}, though its rows are the widest of each"


def test_rows_sort_by_priority_then_by_the_users_time_within_a_group(tmp_path: Path) -> None:
    """The spec's Decision: the user reads a group top down. A ticket whose frontmatter says
    neither sorts after the ones that do, since nothing is known about what it costs."""
    root = tmp_path / "agent" / "tickets"
    (root / "ledger").mkdir(parents=True)
    ticket(root / "ledger" / "01-slow-p1.md", "open", priority=1, size="L")
    ticket(root / "ledger" / "02-quick-p2.md", "open", priority=2, size="XS")
    ticket(root / "ledger" / "03-quick-p1.md", "open", priority=1, size="XS")
    ticket(root / "ledger" / "04-silent.md", "open")
    ticket(root / "ledger" / "05-p1-no-size.md", "open", priority=1)
    (root / "aa-p3-standalone.md").write_text("---\nstatus: open\npriority: 3\nsize: S\n---\n\n# A chore\n")
    features, standalone = load(root)
    page = render_page("demo", features, standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert list(rows_of(page)) == [
        "t-ledger-03", "t-ledger-01", "t-ledger-05", "t-ledger-02", "standalone-aa-p3-standalone", "t-ledger-04",
    ]


def test_the_stamp_the_open_tab_polls_moves_when_a_ticket_is_reprioritised(tracker: Path) -> None:
    """An edit the page shows but the ticket's status does not: the open tab reloads on it or it
    never arrives."""
    features, standalone = load(tracker)
    before = content_stamp("demo", features, standalone, NO_QUEUE, "")
    ticket(tracker / FEAT / "02-second.md", "open", priority=1, size="XS", brief="Why it matters, cold.")
    features, standalone = load(tracker)
    assert content_stamp("demo", features, standalone, NO_QUEUE, "") != before


def test_what_each_row_asks_of_the_user_comes_from_its_ticket_file(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The spec's seven words, each against the fixture ticket that earns it: a build in review
    asks for a ruling; a grilling or prototype decision asks for the session the user sits in,
    whether or not its question is written down; research and legwork an agent does alone, so an
    open question on one is what stops it and the row asks for the answer; a build with no question
    asks nothing of the user."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    rows = rows_of(out.read_text())
    expected = {
        "t-csv-import-02": "review",  # status: review, a build waiting on a ruling
        "standalone-speed-up-tests": "review",
        "standalone-retire-legacy-exporter": "design",  # type: grilling, and its open question is that session
        "t-saved-views-03": "prototype",
        "standalone-read-the-bank-formats": "research",  # type: research, nothing open on it
        "standalone-staging-credentials": "legwork",  # its one question is ruled, and legwork is what is left
        "standalone-flaky-upload-test": "answer",  # a build stopped on a question of its own
        "standalone-pick-a-date-library": "answer",  # research an agent does alone, stopped on a question
        "t-saved-views-01": "answer",
        "t-csv-import-01": "build",  # no type, no question, not in review
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
        for mark, text, tip in marks_on(row):
            if mark not in MARKS or not text:
                continue
            seen.add(mark)
            assert tip and len(tip.split()) >= 4, f"{row_id}: the {mark} mark {text!r} says {tip!r}"
    assert seen == MARKS - {"src"}, "no standalone ticket in the fixture was filed on a branch"
    # each mark's words are about that mark: the time's say whose time it is, the priority's who set it
    row = rows_of(page)["t-csv-import-02"]
    tips = tips_on(row)
    assert "never the agent's" in tips["time"] and "priority" not in tips["time"]
    assert "an agent's reading" in tips["pri"] and "Your time" not in tips["pri"]
    assert "review page" in tips["rp"] and "GitHub" in tips["gh"]
    assert str(demo.root / "csv-import" / "02-map-columns.md") in tips["num"], "a copy button shows what it copies"
    assert "feature" in tips["ftag"]
    # a blocker says which ticket it waits on and whether that one is done (spec, The board)
    assert 'data-tip="Waits on 01, done.">01</a>' in page
    assert 'data-tip="Waits on 02, not done yet.">02</a>' in page
    assert 'data-tip="Waits on csv-import/04, not done yet.">csv-import/04</a>' in page
    # a queue entry is not a ticket, and its own words say so
    assert "has no ticket of its own yet" in tips_on(rows_of(page)["needs-standalone-0"])["asks"]


# ---- questions and the needs-me group -------------------------------------
# The spec's Decisions on `## Questions` and on the board: every question lives on its ticket,
# shows under its row in the one needs-me group, and is copyable one at a time, per ticket, or all
# at once, each button saying what it will copy.

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
    row = rows_of(out.read_text())["standalone-flaky-upload-test"]
    assert questions_on(row) == [("D1", "Retry the upload, or fake the clock?")], "D2 is ruled, and a ruled question is answered"
    written = f"{demo.root / 'flaky-upload-test.md'}\n- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing."
    assert [(which, text) for which, text, _, _ in copiers(row)] == [("qcopy", written)], "one question needs no copy-all beside it"
    # the ticket with three of them has one, and it copies all three under the one path
    three = copiers(rows_of(out.read_text())["t-csv-import-02"])
    assert [which for which, _, _, _ in three] == ["qcopy", "qcopy", "qcopy", "qall"]
    assert three[-1][1].splitlines() == [str(demo.root / "csv-import" / "02-map-columns.md")] + [
        line for which, text, _, _ in three[:-1] for line in text.splitlines()[1:]
    ]


def test_a_build_in_review_shows_the_questions_and_the_closing_comment_on_its_ticket_branch(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """Both live on the branch until the merge, and the checkout's copy of the ticket has neither."""
    checkout = (demo.root / "csv-import" / "02-map-columns.md").read_text()
    assert "## Questions" not in checkout and "## Comments" not in checkout
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    row = rows_of(out.read_text())["t-csv-import-02"]
    assert [tag for tag, _ in questions_on(row)] == ["D1", "D2", "D3"]
    assert "Remember the mapping per bank or per file name?" in row
    assert "<code>~/.config/ledger/mappings.toml</code>" in row, "a headline's own code and emphasis render on the row"
    assert "The mapping step is built and remembers a bank" in row, "the closing comment, folded under the row"
    # the row cuts a headline to its column, so the question's own words are what the hover carries
    tips = [tip for mark, _, tip in marks_on(row) if mark == "qhead"]
    assert tips[0].startswith("Remember the mapping per bank or per file name?")
    assert "Per bank asks one more question on the first import" in tips[0], "the detail the row has no room for"
    assert "[D4]" not in "".join(text for _, text, _, _ in copiers(row)), "the tags a closing comment carries are not questions"


BRANCH = "ticket/ledger/01-map-columns"
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
    (root / "ledger").mkdir(parents=True)
    repo = root.parent.parent
    path = root / "ledger" / "01-map-columns.md"
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
    assert questions_on(rows_of(page)["t-ledger-01"]) == [], "a claimed ticket's branch is a build in progress"
    assert 'id="grp-needs"' not in page, "nothing waits on the user, so the group is not on the page"
    ticket(path, "review", priority=1, size="S")  # the flip the orchestrator makes on the tracker's copy
    page = rendered(root, repo, out)
    assert rows_in(page, "needs") == {"t-ledger-01"}
    assert questions_on(rows_of(page)["t-ledger-01"]) == [("D1", "Per bank or per file name?")]
    assert 'class="ticket row-review" id="t-ledger-01"' in page, "the branch's own claimed does not outrank the tracker"
    assert "<h2>Brief</h2>" not in page, "the brief has one home, and the branch's copy does not open a second"


def test_a_ruling_in_the_tracker_answers_a_question_its_branch_asks(built: tuple[Path, Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The board hands out the tracker's path on the clipboard, so that is where the session taking
    the user's answer writes the `Ruled` line — the branch's copy is the worker's and does not move
    again until the merge."""
    root, repo, path = built
    ticket(path, "review", priority=1, size="S")
    path.write_text(path.read_text() + "\n## Questions\n\n- [D1] Ruled 2026-09-23: per bank.\n")
    page = rendered(root, repo, tmp_path / "board.html")
    assert questions_on(rows_of(page)["t-ledger-01"]) == [], "the ruling is in the file the board named"
    assert rows_in(page, "needs") == {"t-ledger-01"}, "the build still waits for its ruling"


def test_a_feature_ticket_reads_the_branch_its_own_feature_names_and_no_other(built: tuple[Path, Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """Another feature holding a ticket of the same number must not answer for this one."""
    root, repo, path = built
    git(repo, "checkout", "-q", "-b", "ticket/other/01-map-columns")
    path.write_text(path.read_text() + BUILT.replace("Per bank or per file name?", "Another feature's question?"))
    git(repo, "commit", "-q", "-am", "another feature's build")
    git(repo, "checkout", "-q", "main")
    ticket(path, "review", priority=1, size="S")
    out = tmp_path / "board.html"
    assert questions_on(rows_of(rendered(root, repo, out))["t-ledger-01"]) == [("D1", "Per bank or per file name?")]
    git(repo, "branch", "-D", BRANCH)  # its own branch merged and was deleted; the other one stays
    assert questions_on(rows_of(rendered(root, repo, out))["t-ledger-01"]) == []


def test_the_board_reads_the_ticket_branches_again_on_every_render(built: tuple[Path, Path, Path], tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """A worker cutting its branch and committing on it moves no file under the tracker, so the
    watcher's snapshot has to carry the branches, and a board that has been open for a day has to
    ask again rather than answer from the list it read first."""
    root, repo, path = built
    sha = git(repo, "rev-parse", BRANCH)
    git(repo, "branch", "-D", BRANCH)
    ticket(path, "review", priority=1, size="S")
    out = tmp_path / "board.html"
    assert questions_on(rows_of(rendered(root, repo, out))["t-ledger-01"]) == [], "no branch yet, nothing to read"
    before = tracker_snapshot(tracker_roots(root), repo)
    git(repo, "branch", BRANCH, sha)
    assert tracker_snapshot(tracker_roots(root), repo) != before, "a watching board would never render the build's questions"
    assert questions_on(rows_of(rendered(root, repo, out))["t-ledger-01"]) == [("D1", "Per bank or per file name?")]
    after = tracker_snapshot(tracker_roots(root), repo)
    git(repo, "branch", "-f", BRANCH, "main")  # as a commit on the branch moves its tip
    assert tracker_snapshot(tracker_roots(root), repo) != after


def test_a_question_is_read_in_the_shapes_a_ticket_file_is_written_in() -> None:
    """What the spec's prose allows and the generated check above does not draw: a `Ruled` line with
    no bullet under it, an item with no bold headline, a detail running over lines, a rationale that
    opens with the word Ruled and names no date, and a second `## Questions` section, which is how a
    worker's questions reach a ticket that already had some."""
    read = {q.tag: q for q in read_questions("""## Questions

- [D1] **Bulleted ruling?** One line.
  - Ruled 2026-09-21: per bank.
- [D2] **Unbulleted ruling?** One line.
  Ruled 2026-09-22: per bank.
- [D3] No bold headline, just the question?
- [D4] **A detail over two lines?** It starts here
  and carries on there.
- [D5] **Ruled out is not a ruling.** Two ways out.
  - Ruled out: a third, since the suite is already slow.

## Comments

The build, on its branch.

## Questions

- [D6] **Appended by the worker?** Under a second heading of its own.
""")}
    assert list(read) == ["D1", "D2", "D3", "D4", "D5", "D6"]
    assert (read["D1"].ruled, read["D2"].ruled) == ("2026-09-21", "2026-09-22")
    assert read["D3"].headline == "No bold headline, just the question?" and read["D3"].detail == ""
    assert read["D4"].detail == "It starts here and carries on there."
    assert read["D5"].ruled is None, "a line that opens with the word Ruled and names no date rules nothing"
    assert read["D6"].headline == "Appended by the worker?"


def test_a_near_design_session_is_in_needs_me_with_no_question_written_down(tmp_path: Path) -> None:
    """The needs-me clauses the demo tracker has no row for: a grilling or prototype decision the
    user would sit for soon is there before anyone has written its question, one nobody can sit for
    yet is not, and a done ticket is never there whatever it still carries (the spec's Property, as
    amended 2026-09-23)."""
    root = tmp_path / "agent" / "tickets"
    (root / "ledger").mkdir(parents=True)
    ticket(root / "ledger" / "01-soon.md", "open", kind="grilling", priority=2, size="S")
    ticket(root / "ledger" / "02-taken.md", "claimed", kind="grilling", priority=1, size="S")
    ticket(root / "ledger" / "03-someday.md", "open", kind="prototype", priority=3, size="S")
    ticket(root / "ledger" / "04-shipped.md", "done", priority=1, size="S")
    (root / "ledger" / "04-shipped.md").write_text(
        (root / "ledger" / "04-shipped.md").read_text() + "\n## Questions\n\n- [D1] **Left open when it landed?** Nobody ruled.\n"
    )
    features, standalone = load(root)
    page = render_page("demo", features, standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert rows_in(page, "needs") == {"t-ledger-01"}
    assert questions_on(rows_of(page)["t-ledger-04"]) == [], "a question left on a done ticket is a leftover, not a call"


def test_every_copy_button_on_the_board_shows_what_it_copies(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The spec's reviewed Property, at the loader-and-page seam its Testing Decisions names: the
    words a button shows on hover are what its click puts on the clipboard, cut off only where they
    run long."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    page = out.read_text()
    found = copiers(page)
    assert {which for which, _, _, _ in found} == {"qcopy", "qall", "qgroup"}
    for which, text, said, tip in found:
        what, _, shown = tip.partition("\n\n")
        assert len(what.split()) >= 4 and "copy" in what, f"the {which} button says {what!r} of the click"
        assert shown, f"the {which} button shows nothing of what it copies"
        if shown.endswith("…"):  # a button whose text runs long shows the start of it and says so
            assert text.startswith(shown[:-1]) and len(shown) > 120, f"the {which} button shows {shown!r}"
            assert len(shown) <= 260, f"the {which} button spills {len(shown)} characters into the row"
        else:
            assert shown == text, f"the {which} button shows {shown!r} and copies {text!r}"
        if which == "qgroup":  # the board's worth of them: the note counts what the text holds
            assert said == f"{sum(line.startswith('- [D') for line in text.splitlines())} questions"
        else:
            assert text.splitlines()[0].rsplit("/", 1)[-1] in said, f"the {which} button's note says {said!r}"
    # the copy button the row already had says the same of itself (02-rows)
    assert str(demo.root / "flaky-upload-test.md") in tips_on(rows_of(page)["standalone-flaky-upload-test"])["num"]


def test_the_needs_me_groups_copy_button_holds_every_open_question_under_its_tickets_path(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """What the user pastes into an editor to answer a board's worth of questions at once."""
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    page = out.read_text()
    (text,) = [text for kind, text, _, _ in copiers(page) if kind == "qgroup"]
    blocks = [block.splitlines() for block in text.split("\n\n")]
    assert {lines[0] for lines in blocks} == {
        str(demo.root / feature / name) for feature, name in [
            ("csv-import", "02-map-columns.md"), ("saved-views", "01-view-storage.md"),
            ("saved-views", "03-view-list-shape.md"), (".", "flaky-upload-test.md"),
            (".", "pick-a-date-library.md"), (".", "retire-legacy-exporter.md"), (".", "speed-up-tests.md"),
        ]
    }
    asked = [line for lines in blocks for line in lines[1:]]
    assert len(asked) == 10 and all(line.startswith("- [D") for line in asked)
    assert any("Remember the mapping per bank" in line for line in asked), "the questions on a ticket branch are in it too"
    # the file's own markdown, so a question pastes back into the ticket as it was written
    assert "- [D3] **The mappings live in `~/.config/ledger/mappings.toml`.** Fine there, or beside the ledger file so they travel with it?" in asked
    assert not any("Whose card does the sandbox go on" in line for line in asked), "a ruled question is answered"


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
    features = load_features(tracker, {}, diffviews, None)
    standalone = load_standalone(Roots(tracker, []), diffviews)
    page = render_page("demo", features, standalone, NO_QUEUE, log="", stamp="s", stamp_src="s.js")
    assert f'href="{STUB_ADDRESS}/quoted.html"' in page
    assert absences(page, "review-page-server") == 0


def test_a_tracker_with_no_review_pages_rendered_says_nothing_about_the_server(repo: Path, tracker: Path, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """Nothing has been sent for review yet, so there is no page a server could be answering for:
    the absence the Property names is the server for pages that exist."""
    out = tmp_path / "board.html"
    render(tracker_roots(tracker), repo, out)
    assert absences(out.read_text(), "review-page-server") == 0


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
