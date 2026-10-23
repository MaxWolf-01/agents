# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown", "markdown-it-py[linkify]"]  # the last four: the demo tracker and the board the shared fixtures import
# ///
"""What a qualified tag names. Run: uv run test_qualified.py

The seams are `qualified.resolver` and `cites`, which every page the user reads looks a tag up by,
and `link_html`, which the board and the retro's page link one by. The oracle is the ticket below,
written as the tracker skill shapes one, the retro report's shape (retro/REPORT.md), and
the Decisions of agent/tickets/fewer-workflow-concepts.md: a tag the user reads is `<ticket> D6`,
`retro F1` or `review <range> S13`, linked, with what it names as a hover preview; and criterion 2 of
agent/tickets/tags-linked-on-board-and-review-pages.md, that one naming what no longer exists shows as such.
"""

import subprocess
from pathlib import Path

import pytest

from qualified import QUALIFIED, cites, hrefs, link_html, resolver

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
  - [D5] a nested line is no entry of its own.
- A4 `mx/sync.py:12`: one remote per checkout.
"""


@pytest.fixture
def resolve(tmp_path: Path):
    """A tracker in `tickets/`, with a ticket beside it too that only a slug escaping it would reach."""
    (tmp_path / "tickets").mkdir()
    for path in (tmp_path / "tickets" / "sync.md", tmp_path / "sync.md"):
        path.write_text(TICKET)
    return resolver(tmp_path / "tickets")


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


def test_a_question_left_open_on_a_done_ticket_waits_on_nobody(tmp_path: Path) -> None:
    """The board shows a done ticket no question: one left open there is a leftover the ruling on
    the build filed as a proposed ticket, so no page lists it as waiting."""
    (tmp_path / "sync.md").write_text(TICKET.replace("status: review", "status: done"))
    assert resolver(tmp_path)("sync", "D1").open is False


def test_a_tag_names_nothing_where_its_ticket_or_the_tag_is_missing(resolve) -> None:
    cases = ("sync", "D9"), ("async", "D1"), ("../sync", "D1"), ("sync", "D5")
    assert [resolve(slug, tag) for slug, tag in cases] == [None, None, None, None]


def test_a_qualified_tag_is_found_in_text_by_its_slug_and_tag() -> None:
    """Either separator the tracker writes, and never a tag that only ends a longer word or path."""
    text = "sync D1 holds, as does two-main#P3; mx/sync D1, my_sync A4, sync D12x and syncD2 do not."
    assert [(m["ticket"], m["tag"]) for m in QUALIFIED.finditer(text)] == [("sync", "D1"), ("two-main", "P3")]


def test_a_retro_entry_and_a_review_finding_are_found_in_text_by_what_qualifies_them() -> None:
    text = "retro F1 and retro A3, review 2339177..8424220 S13; a retro F1x, review 23..84 S1 and retroF2 are none."
    assert [m.group() for m in QUALIFIED.finditer(text)] == ["retro F1", "retro A3", "review 2339177..8424220 S13"]


REPORT = """# Workflow retro: agents

Run 2026-10-23, over 2026-10-19 to 2026-10-23. ids: F33, A35

## Findings

- **A20**: see F2, which it would narrow.

### F2 The agent's how adds machinery

- **State**: live

## Candidates

### A20 `diffview --notes` also reads the markdown bullet form

## Dismissed

- **A23**, the worker prompt's shared style. max: "DROP THIS" (4d54054e, 2026-10-23).
"""


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True)


def reviews(agent: Path) -> Path:
    """Where code-review/review keeps a review's reports on this machine, one directory per repo."""
    return agent / "state" / "mx" / "reviews"


@pytest.fixture
def agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An agent repo: the tracker holding `sync`, git's history of it holding `old-sync` retired,
    the retro's report and its page, and one review's reports on this machine."""
    git(tmp_path, "init", "-q")
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "old-sync.md").write_text(TICKET)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "file old-sync")
    git(tmp_path, "rm", "-q", "tickets/old-sync.md")
    git(tmp_path, "commit", "-qm", "retire old-sync")
    (tmp_path / "tickets").mkdir(exist_ok=True)
    (tmp_path / "tickets" / "sync.md").write_text(TICKET)
    (tmp_path / "retro").mkdir()
    (tmp_path / "retro" / "report.md").write_text(REPORT)
    (tmp_path / "retro" / "report.html").write_text('<h3 id="f2">F2</h3><h3>A20</h3><li id="a23">A23</li>')
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    review = reviews(tmp_path) / "-code" / "2339177..8424220"
    review.mkdir(parents=True)
    (review / "standards.md").write_text("# Standards review\n\n## Findings\n\n### S1 `QUALIFIED` copies the slug pattern\n")
    return tmp_path


def cited(agent: Path, text: str):
    found = cites(agent)(QUALIFIED.fullmatch(text))
    return found and (found.path, found.anchor, found.preview)


def test_a_ticket_tag_cites_its_ticket_file_and_one_the_tracker_no_longer_holds_is_gone(agent) -> None:
    """A tag its ticket holds links that file; a tag the ticket dropped, or one of a retired ticket,
    names what no longer exists; a slug that never was a ticket's is prose, and names nothing."""
    assert cited(agent, "sync#P2") == ("tickets/sync.md", "", "sync P2 · A ticket file is written in one checkout only.")
    assert cited(agent, "sync D9") == (None, "", "sync D9 · no longer in its ticket")
    assert cited(agent, "old-sync D1") == (None, "", "old-sync D1 · its ticket is no longer in the tracker")
    assert cited(agent, "and P3") is None


def test_a_retro_entry_cites_its_place_on_the_retros_page_and_a_dropped_one_is_gone(agent) -> None:
    """A finding at the anchor its page gives it, a candidate the page gave none at the page's top,
    a dismissed one by its line under Dismissed, and an id the report no longer holds as gone."""
    assert cited(agent, "retro F2") == ("retro/report.html", "#f2", "retro F2 · The agent's how adds machinery")
    assert cited(agent, "retro A20") == ("retro/report.html", "", "retro A20 · `diffview --notes` also reads the markdown bullet form")
    assert cited(agent, "retro A23")[:2] == ("retro/report.html", "#a23")
    assert cited(agent, "retro A23")[2].startswith("retro A23 · dismissed: the worker prompt's shared style.")
    assert cited(agent, "retro F1") == (None, "", "retro F1 · no longer in the retro's report")


def test_a_review_finding_cites_its_report_where_this_machine_has_it(agent) -> None:
    assert cited(agent, "review 2339177..8424220 S1") == (
        str(reviews(agent) / "-code" / "2339177..8424220" / "standards.md"), "", "review 2339177..8424220 S1 · `QUALIFIED` copies the slug pattern")
    assert cited(agent, "review 2339177..8424220 S2")[0] is None
    assert cited(agent, "review 1111111..2222222 S1") == (None, "", "review 1111111..2222222 S1 · not in a report of that review on this machine")


def test_a_review_finding_cites_its_report_whichever_repo_the_review_read(agent) -> None:
    """A citation names a range and no repo, so a review of a listed repo or of the agent repo is
    found as one of the code repo is."""
    report = reviews(agent) / "-listed" / "3a4b5c6..7d8e9f0" / "correctness.md"
    report.parent.mkdir(parents=True)
    report.write_text("# Correctness review\n\n### C1 The board strikes every review citation\n")
    assert cited(agent, "review 3a4b5c6..7d8e9f0 C1") == (
        str(report), "", "review 3a4b5c6..7d8e9f0 C1 · The board strikes every review citation")


def link(agent: Path, page: str) -> str:
    return link_html(page, cites(agent), lambda c: f"#t-{c.ticket}" if c.ticket else c.path + c.anchor)


def test_a_page_links_what_lives_elsewhere_from_its_own_directory_and_a_place_on_itself_within_it(agent) -> None:
    """The retro's page citing its own entry jumps to it, and its tickets by the path up to them."""
    page = agent / "retro" / "report.html"
    linked = link_html("<p>retro F2, sync D1</p>", cites(agent), hrefs(agent, page))
    assert 'href="#f2" title=' in linked and 'href="../tickets/sync.md" target="_blank"' in linked


def test_every_qualified_tag_in_a_pages_prose_links_to_what_it_names(agent) -> None:
    """Written plain, as code, or with its slug alone as code: each a link with its preview as the
    link's hover words, and a link off the page opening in its own tab."""
    page = "<p>Builds on sync P2, <code>retro F2</code> and <code>sync</code> D1.</p>"
    assert link(agent, page) == (
        '<p>Builds on <a class="qualified" href="#t-sync" title="sync P2 · A ticket file is written in one checkout only.">sync P2</a>, '
        '<a class="qualified" href="retro/report.html#f2" target="_blank" rel="noopener" title="retro F2 · The agent&#x27;s how adds machinery">'
        '<code>retro F2</code></a> and '
        '<a class="qualified" href="#t-sync" title="sync D1 · Sync on every commit? Or on a timer."><code>sync</code> D1</a>.</p>')


def test_a_tag_naming_what_no_longer_exists_is_struck_through_saying_why_and_links_nowhere(agent) -> None:
    assert link(agent, "<p>old-sync D1</p>") == (
        '<p><s class="qualified gone" title="old-sync D1 · its ticket is no longer in the tracker">old-sync D1</s></p>')


def test_text_that_is_no_prose_of_the_page_stays_as_it_is(agent) -> None:
    """A link, code inside one, a code block, a figure (one closed where it opens included), a
    script, a style, a title, a text area, a button, an attribute, prose that only looks like a tag,
    and a link holding an element left open; the tag after all of them, in an element with hover
    words of its own, is linked."""
    page = ('<a href="x">sync D1</a><a href="x"><code>sync D1</code></a><pre>sync D1</pre>'
            '<svg><text>sync D1</text></svg><svg viewBox="0 0 1 1"/><script>let s = "<a>"; // sync D1</script>'
            '<style>/* sync D1 */</style><title>sync D1</title><textarea>sync D1</textarea><button>sync D1</button>'
            '<p title="sync D1">and P3</p><br><a href="x"><p>open</a>')
    after = '<span data-tip="its own words">then sync D1</span>'
    linked = link(agent, page + after)
    assert linked == page + ('<span data-tip="its own words">then <a class="qualified" href="#t-sync" '
                             'title="sync D1 · Sync on every commit? Or on a timer.">sync D1</a></span>')


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
