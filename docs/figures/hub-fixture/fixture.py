"""What the hub screenshot shows: a small ledger app, its tracker, and five orchestrator sessions on it.

Everything here is made up. `build.py` lays it down under a throwaway HOME and points the hub at it. A
session's records follow the shape `mx/skills/session-page/RULES.md` gives them; its `turns` are written
oldest first, each with how long before the shot it ended and the prompts the user sent before it.
"""

from dataclasses import dataclass

# --- the code repo: a skeleton, then the slice the selected session just landed ---------------------

SKELETON = {
    "ledger/__init__.py": "",
    "ledger/rows.py": '''from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Row:
    """One line of a statement, as the ledger keeps it."""

    on: date
    payee: str
    amount: Decimal
    category: str = ""
''',
    "ledger/filters.py": '''from dataclasses import dataclass, field
from datetime import date

from ledger.rows import Row


@dataclass(frozen=True)
class Filter:
    """What the sidebar narrows the rows to: a date range, categories, a payee's words."""

    since: date | None = None
    until: date | None = None
    categories: frozenset[str] = field(default_factory=frozenset)
    payee: str = ""

    def keeps(self, row: Row) -> bool:
        return ((self.since is None or row.on >= self.since)
                and (self.until is None or row.on <= self.until)
                and (not self.categories or row.category in self.categories)
                and self.payee.lower() in row.payee.lower())
''',
    "ledger/app.py": '''from ledger.db import connect
from ledger.filters import Filter
from ledger.web import Router, json

app = Router()


@app.get("/rows")
def rows(request):
    db = connect(request.user)
    keep = Filter(**request.query.filters())
    return json([r for r in db.rows() if keep.keeps(r)])
''',
}

SAVED_VIEWS = {
    "ledger/views.py": '''"""A saved view: the filters, sort and columns a user named once and reopens from the sidebar."""

from dataclasses import asdict, dataclass

from ledger.filters import Filter

COLUMNS = ("on", "payee", "amount", "category")


@dataclass(frozen=True)
class View:
    name: str
    filters: Filter
    sort: str = "on"
    descending: bool = True
    columns: tuple[str, ...] = COLUMNS


class NameTaken(Exception):
    """A view of that name exists; it carries the existing view, which is never overwritten."""

    def __init__(self, existing: View):
        super().__init__(f"a view named {existing.name!r} exists")
        self.existing = existing


def save(db, user: str, view: View) -> None:
    if existing := reopen(db, user, view.name):
        raise NameTaken(existing)
    db.execute("insert into views (user, name, body) values (?, ?, ?)", (user, view.name, db.encode(asdict(view))))


def reopen(db, user: str, name: str) -> View | None:
    """The view as it was saved, less any column the ledger no longer has (P3)."""
    row = db.execute("select body from views where user = ? and name = ?", (user, name)).fetchone()
    if row is None:
        return None
    body = db.decode(row[0])
    kept = tuple(c for c in body.pop("columns") if c in COLUMNS)
    return View(filters=Filter(**body.pop("filters")), columns=kept, **body)
''',
    "ledger/app.py": '''from ledger import views
from ledger.db import connect
from ledger.filters import Filter
from ledger.web import Router, json

app = Router()


@app.get("/rows")
def rows(request):
    db = connect(request.user)
    keep = Filter(**request.query.filters())
    return json([r for r in db.rows() if keep.keeps(r)])


@app.post("/views")
def save_view(request):
    db = connect(request.user)
    view = views.View(name=request.form["name"], filters=Filter(**request.query.filters()),
                      sort=request.query.get("sort", "on"), columns=tuple(request.query.getlist("column")))
    try:
        views.save(db, request.user, view)
    except views.NameTaken as taken:
        return json({"error": str(taken), "view": f"/views/{taken.existing.name}"}, status=409)
    return json({"view": f"/views/{view.name}"}, status=201)


@app.get("/views/<name>")
def reopen_view(request, name):
    view = views.reopen(connect(request.user), request.user, name)
    return json(view) if view else json({"error": f"no view named {name!r}"}, status=404)
''',
    "tests/test_views.py": '''from datetime import date

import pytest

from ledger import views
from ledger.filters import Filter


def test_a_reopened_view_keeps_the_rows_its_filters_keep(fresh_db, rows):
    """P1: reopening shows exactly the rows the same filters show now."""
    keep = Filter(since=date(2026, 9, 1), until=date(2026, 9, 30), categories=frozenset({"groceries"}))
    views.save(fresh_db, "sam", views.View("mine", keep))
    reopened = views.reopen(fresh_db, "sam", "mine")
    assert [r for r in rows if reopened.filters.keeps(r)] == [r for r in rows if keep.keeps(r)]


def test_a_taken_name_is_refused_with_the_view_that_has_it(fresh_db):
    """P2: a view's name is unique per user, and the first one stands."""
    first = views.View("groceries", Filter(categories=frozenset({"groceries"})))
    views.save(fresh_db, "sam", first)
    with pytest.raises(views.NameTaken) as taken:
        views.save(fresh_db, "sam", views.View("groceries", Filter(since=date(2026, 1, 1))))
    assert taken.value.existing == first
''',
}

REVIEW_SUMMARY = ("A user can name the filters, sort and columns they are looking at and reopen them from the "
                  "sidebar later. Views live in the ledger's own database, so a backup carries them; a name already "
                  "taken is refused with a link to the view that has it, never overwritten.")
REVIEW_NOTES = {"notes": [
    {"id": 1, "path": "ledger/views.py", "line": 28, "end": 29, "side": "new",
     "text": "Refused rather than overwritten: the worker's call, recorded in the ticket's Decisions. "
             "Overwriting would lose a view the user may already have shared."},
    {"id": 2, "path": "ledger/views.py", "line": 39, "end": 40, "side": "new",
     "text": "saved-views#P3: a column the ledger dropped since the view was saved is left out here, "
             "and the sidebar says which."},
]}

# --- the tracker ----------------------------------------------------------------------------------


@dataclass
class Ticket:
    slug: str
    title: str
    status: str
    brief: str
    priority: int = 2
    size: str = "M"
    parent: str | None = None
    blocked_by: tuple[str, ...] = ()
    needs_user: bool = False
    diff: bool = False  # the saved-views slice's range, filled in once the code repo has it
    criteria: tuple[str, ...] = ()
    properties: tuple[str, ...] = ()

    def text(self, diff: str = "") -> str:
        front = [f"status: {self.status}"]
        if self.parent:
            front.append(f"parent: {self.parent}")
        if self.blocked_by:
            front.append(f"blocked-by: [{', '.join(self.blocked_by)}]")
        if self.needs_user:
            front.append("needs-user: true")
        front += [f"priority: {self.priority}", f"size: {self.size}"]
        if self.diff:
            front.append(f"diff: [{diff}]")
        done = "x" if self.status in ("review", "done") else " "
        criteria = "\n".join(f"- [{done}] {c}" for c in self.criteria) or f"- [{done}] {self.title}, built and driven."
        props = "".join(f"- P{i} {p}\n" for i, p in enumerate(self.properties, 1))
        return ("---\n" + "\n".join(front) + f"\n---\n\n# {self.title}\n\n## Brief\n\n{self.brief}\n\n"
                + (f"## Properties\n\n{props}\n" if props else "")
                + f"## Acceptance criteria\n\n{criteria}\n\n## Comments\n")


TICKETS = [
    Ticket("saved-views", "Saved views", "claimed", priority=1, size="L",
           properties=("A reopened view shows exactly the rows its filters show now.",
                       "A view's name is unique per user, and the first view saved under it stands.",
                       "A view reopened after a column left the ledger drops that column and says so."),
           brief="A user names the filters, sort and columns they are looking at, reopens them from the sidebar, "
                 "and shares one by link. Today every visit starts from the default screen."),
    Ticket("save-and-reopen-a-view", "Save and reopen a view", "review", parent="saved-views", priority=1, diff=True,
           brief="Save what the screen shows under a name, and put it back from the sidebar.",
           criteria=("`saved-views#P1` and `saved-views#P2` hold, as the review reads the diff.",
                     "A taken name is refused with the existing view's link.")),
    Ticket("share-a-view-by-link", "Share a view by link", "open", parent="saved-views",
           blocked_by=("save-and-reopen-a-view",),
           brief="A link to a saved view that someone without the sender's login can open."),
    Ticket("csv-import", "Import a bank's CSV statement", "claimed", priority=1, size="XL",
           brief="A user drops a bank's CSV export on the ledger and gets its rows as entries, with every line the "
                 "import could not read named before anything is committed."),
    Ticket("upload-and-parse-report", "Upload and parse report", "done", parent="csv-import", size="S",
           brief="The upload answers with a report: each line the mapping could not read, with its number."),
    Ticket("map-columns-to-fields", "Map columns to fields", "claimed", parent="csv-import",
           brief="The user maps a bank's columns to the ledger's fields once, and the next statement reuses it."),
    Ticket("duplicate-rule", "Skip rows already in the ledger", "claimed", parent="csv-import", size="S",
           brief="A row the ledger already holds, by date, amount and payee, is skipped and counted."),
    Ticket("commit-the-import", "Commit the import", "open", parent="csv-import",
           blocked_by=("map-columns-to-fields", "duplicate-rule"),
           brief="A dry run says what will be added and skipped; the commit writes exactly that."),
    Ticket("flaky-upload-test", "Steady the upload report test", "claimed", priority=2, size="S",
           brief="`test_upload_report` fails about one run in forty on CI, never locally."),
    Ticket("retire-the-legacy-exporter", "Retire the legacy exporter", "proposed", priority=3, size="S",
           brief="Cut from csv-import's debrief: the old exporter writes a format nothing reads any more."),
    Ticket("budget-chart", "Chart a month against its budget", "claimed", priority=2, needs_user=True,
           brief="The month page shows spending per category against what was budgeted for it."),
]

# --- the sessions ---------------------------------------------------------------------------------


@dataclass
class Turn:
    record: str
    """The record's text: `turns/NN.md`, or a chat turn's reply."""
    ago: int
    """Minutes before the shot the turn ended."""
    prompts: tuple[str, ...]
    """What the user sent before it, oldest first."""
    chat: bool = False


@dataclass
class Session:
    id: str
    name: str
    """Its short name in Claude Code's registry, `<repo>-<n>`."""
    status: str
    """The registry's: idle, busy, waiting on something in the terminal, or shell (idle with a command it left
    running in the background)."""
    tickets: tuple[str, ...]
    """The tickets it filed or committed on, which give its unit a tree on the rail."""
    title: str
    brief: str
    turns: list[Turn]
    opens: tuple[str, ...] = ()
    """Pages it opened in the hub beside its session page, in order, as paths under `agent/`."""
    visited: bool = True
    """Whether the user has looked at its unit since its newest turn."""
    context: tuple[int, int] = (30, 60_000)
    """Its context use, as the statusline last had it: percent and tokens."""
    waiting_for: str | None = None
    pane: bool = False
    """Whether it runs in a tmux pane the hub can type into, which gives its box an offer to hand off."""
    handoff: tuple[str, str] | None = None
    """Its continuation handoff, committed after its last prompt, so fresh: the file's slug and its body."""
    runs: tuple[tuple[str, str], ...] = ()
    """What its last turn left running in the background, which no task notification has ended: description, command."""


SAVED = Session(
    id="3f6c2a91-8d4e-4b7a-9c15-2e7d40b8a6f3", name="ledger-14", status="idle", context=(78, 156_000), pane=True,
    tickets=("saved-views", "save-and-reopen-a-view", "share-a-view-by-link"),
    title="Saved views: reopening a view, then sharing one by link",
    brief="The saved-views tree: the filters, sort and columns a user names once and reopens from the sidebar, then "
          "a link that shows a view to someone else. The design is settled and its first slice has landed; sharing by "
          "link waits on what a shared link carries.",
    opens=("show/saved-views/what-a-view-holds.html", "diffviews/save-and-reopen-a-view.html",
           "show/share-a-view-by-link/link-resolves.html"),
    handoff=("share-a-view-by-link", """# Saved views: build sharing by link once Q3 is answered

## Purpose

Continuation. `save-and-reopen-a-view` has landed on the saved-views branch; what is left of the tree is
`share-a-view-by-link`, which waits on Q3 of this session's page: whether a shared link carries the view or a
snapshot of its rows.

## Where it stands

- The review of the landed slice checked P1 and P2 against the diff; P3 (a dropped column) is covered by `reopen`.
- My pick on Q3 is (a), the link names the view; the figure lays both answers side by side.

## Sources

- MUST READ `agent/tickets/saved-views.md`: the properties, and the two slices
- MUST READ `agent/show/share-a-view-by-link/link-resolves.html`: the two answers to Q3
- `ledger/views.py`: what a stored view holds, which a link would resolve through
"""),
    turns=[
        Turn(ago=26 * 60, prompts=((
            "saved views. people keep rebuilding the same filter every morning, groceries last 90 days etc. "
            "let's grill it, i want to be able to share one with my partner too"),), record="""---
date: {date}
---

# What a view holds, and where views are kept

## Questions

- [Q1] **Does a saved view keep its sort and columns, or only its filters?** A view that drops them reopens in the default order, which is not how the user left it.
  - (a) Filters, sort and columns, all three *my pick*
  - (b) Filters only; sort and columns stay as the session has them
  - Why: reopening a view is meant to put the screen back as it was, and the two extra fields are a few bytes each.
- [Q2] **A table in the ledger's database, or a views file beside it?** It decides whether a view survives a backup and an export.
  - (a) A `views` table in the ledger's own database *my pick*
  - (b) A `views.json` beside the database file
  - Why: the table travels with the ledger in a backup, and the app already opens that database on every request.

## Links

- [What a view holds](agent/show/saved-views/what-a-view-holds.html): the three fields, against the screen each restores

## Details

The ticket's properties so far: P1, a reopened view shows the rows the same filters show now; P2, a view's name is unique per user. Neither depends on Q1 or Q2.
"""),
        Turn(ago=25 * 60, prompts=("a and a. sharing can come after",), record="""---
date: {date}
answered:
  Q1: a
  Q2: a
---

# Saved views cut into two slices, save and reopen first

## Links

- [The saved-views ticket](agent/tickets/saved-views.md): properties P1 to P3, and the two slices

## Details

- `save-and-reopen-a-view` is dispatched; `share-a-view-by-link` waits on it, since a link resolves through the stored view.
- P3 came out of your answer to Q1: a view reopened after a column left the ledger drops that column and says so.
"""),
        Turn(ago=3 * 60, chat=True, prompts=("how's the worker doing",),
             record="The worker on `save-and-reopen-a-view` has views saving and reopening and is on the sidebar list; "
                    "nothing waits on you yet."),
        Turn(ago=14, prompts=("the worker is done, land it and tell me what sharing needs from me",), record="""---
date: {date}
---

# Save and reopen landed; what a shared link carries is your call

## Questions

- [Q3] **Does a shared link carry the view, or a snapshot of its rows?** It decides what `share-a-view-by-link` builds, and what your partner sees a week after you send it.
  - (a) The view: the link names the saved view, and whoever opens it sees today's rows through its filters *my pick*
  - (b) A snapshot: the link carries the rows as they stood when it was shared
  - Why: a view is how you read your ledger, and (a) keeps one copy of it. (b) needs storage of its own and a rule for when a snapshot expires, for a reader who wanted the numbers at a date, which an export already gives.

## Links

- [How a shared link resolves](agent/show/share-a-view-by-link/link-resolves.html): both answers, from the sender's click to what the reader sees
- [Review: save and reopen a view](agent/diffviews/save-and-reopen-a-view.html): the landed slice, with the worker's notes

## Details

- `save-and-reopen-a-view` is merged into the saved-views branch and waits for the tree's close-out; its review checked the diff against P1 and P2.
- One call the worker made: a name already taken is refused with a link to the view that has it, never overwritten. It is in the ticket's Decisions, and the review page notes it where the code does it.
- Context is at 78%, so the handoff is committed: the next session takes Q3's answer from there and builds the link.
"""),
    ],
)

IMPORT = Session(
    id="8a1d5e07-3c92-4f6b-b2e8-71c94d0a5e26", name="ledger-11", status="shell", context=(63, 126_000),
    runs=(("wait for the wave-2 workers to land", "dispatch-ctl wait map-columns-to-fields duplicate-rule"),),
    tickets=("csv-import", "upload-and-parse-report", "map-columns-to-fields", "duplicate-rule", "commit-the-import"),
    title="CSV import: wave 2, mapping columns and the duplicate rule",
    brief="Dispatching the csv-import tree. Wave 1 landed the upload's parse report; wave 2 runs map-columns-to-fields "
          "and duplicate-rule in parallel, and commit-the-import waits on both.",
    opens=("show/csv-import/waves.html",),
    turns=[
        Turn(ago=5 * 60, prompts=("dispatch csv-import",), record="""---
date: {date}
---

# Wave 1 landed: the upload reports every line it could not read

## Links

- [The waves](agent/show/csv-import/waves.html): which ticket runs in which wave, and why two run at once

## Details

`upload-and-parse-report` is merged into the csv-import branch. Its report names 3 of the 212 lines in the sample statement, each with its number and the reason.
"""),
        Turn(ago=50, prompts=("go on with wave 2",), record="""---
date: {date}
---

# Wave 2 dispatched: map-columns-to-fields and duplicate-rule, a worker each

## Details

The two share no file: the mapping lives in `ledger/importer/mapping.py`, the rule in `ledger/importer/duplicates.py`. `commit-the-import` starts once both land.
"""),
    ],
)

FLAKY = Session(
    id="c47e9b13-6a05-4d28-8f71-9be3a2d6c084", name="ledger-12", status="waiting", waiting_for="permission prompt",
    context=(24, 48_000), tickets=("flaky-upload-test",),
    title="Flaky upload test: the report test fails one run in forty",
    brief="`test_upload_report` fails on CI about one run in forty and never locally. Reproducing it under load, then "
          "fixing whatever the load exposes.",
    opens=("show/flaky-upload-test/runs.html",),
    turns=[
        Turn(ago=35, prompts=("the upload report test flaked again on CI, can you find out why",), record="""---
date: {date}
---

# The flake reproduced under load: two tests share one temp file

## Links

- [Four hundred runs](agent/show/flaky-upload-test/runs.html): the failures, by which test ran beside it

## Details

Every failure ran beside `test_upload_too_large`, which writes the same `upload.csv` under the shared temp directory. Giving each test its own directory is the fix; I am running the suite under load again to confirm it.
"""),
    ],
)

EXPORTER = Session(
    id="5b82f4d6-1e37-4a90-a6c3-0d58e7b21f94", name="ledger-9", status="busy", context=(12, 24_000),
    tickets=("retire-the-legacy-exporter",),
    title="Legacy exporter: what still calls it, before it goes",
    brief="The legacy exporter writes a format nothing reads any more. Finding what still calls it, so the proposal "
          "to retire it says what moves.",
    turns=[
        Turn(ago=3 * 60 + 20, prompts=("what still uses the old exporter?",), record="""---
date: {date}
---

# Two callers left, both in the monthly report, and both move cleanly

## Details

- `reports/monthly.py` calls it twice, for the totals table and the category breakdown; the new exporter writes both.
- The proposal `retire-the-legacy-exporter` now lists the two moves in its brief, and waits for your ruling on the board.
"""),
    ],
)

BUDGET = Session(
    id="e19a7c35-9f64-4b02-8d1e-6a3f05c8b7d2", name="ledger-15", status="idle", visited=False, context=(33, 67_000),
    tickets=("budget-chart",),
    title="Budget chart: a month's spending against its budget",
    brief="The month page's chart: spending per category against what was budgeted. Three shapes drawn from the same "
          "month, for you to pick one in front of them.",
    opens=("show/budget-chart/three-charts.html",),
    turns=[
        Turn(ago=40, prompts=("the month page needs a chart of spending vs budget, show me a few options",),
             record="""---
date: {date}
---

# Three ways to draw a month against its budget, side by side

## Links

- [Three charts](agent/show/budget-chart/three-charts.html): bars against a budget line, a bullet per category, and the month's running total

## Details

All three are drawn from September's real-looking sample, 14 categories. Pick one in front of them; the others go.
"""),
    ],
)

SESSIONS = [SAVED, IMPORT, FLAKY, EXPORTER, BUDGET]
SELECTED = SAVED
FRONT = "show/share-a-view-by-link/link-resolves.html"  # the page the shot brings to the front of its pane

# --- the pages the sessions opened ----------------------------------------------------------------

SHOW_HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400;1,6..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{tokens}
  body {{ font-size: 18px; padding: 24px 28px 40px; }}
  h1 {{ font-size: 1.35rem; line-height: 1.3; margin: 0 0 4px; color: var(--strong); font-weight: 600; }}
  .meta {{ font: 14px/1.5 var(--font-mono); color: var(--muted); margin: 0 0 18px; }}
  svg {{ display: block; width: 100%; height: auto; max-width: 760px; }}
  svg text {{ font-family: var(--font-mono); fill: var(--body); }}
  svg .head {{ font: 600 15px var(--font-body); fill: var(--strong); }}
  svg .note {{ fill: var(--muted); font-size: 11.5px; }}
  svg .box {{ fill: var(--ground-2); stroke: var(--edge); }}
  svg .pick {{ stroke: var(--accent); stroke-width: 1.5; }}
  svg .flow {{ stroke: var(--muted); fill: none; }}
  svg .tag {{ fill: var(--accent); font-weight: 500; }}
  p {{ max-width: 34rem; margin: 18px 0 0; }}
  table {{ border-collapse: collapse; font-size: 17px; margin-top: 14px; }}
  td, th {{ padding: 6px 14px 6px 0; border-bottom: 1px solid var(--edge); text-align: left; vertical-align: top; }}
  th {{ font: 500 14px var(--font-mono); color: var(--muted); }}
  code {{ font: 13.5px var(--font-mono); }}
</style></head><body>
"""


LINE = 18  # a box's line height, at the figure's 13.5px mono


def box(x: int, y: int, w: int, lines: list[str], pick: bool = False) -> str:
    h = 16 + LINE * len(lines)
    text = "".join(f'<text x="{x + 11}" y="{y + 25 + LINE * i}" font-size="13.5">{t}</text>' for i, t in enumerate(lines))
    return f'<rect class="box{" pick" if pick else ""}" x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>{text}'


def arrow(x: int, y1: int, y2: int) -> str:
    return (f'<path class="flow" d="M{x} {y1} V{y2 - 7}"/>'
            f'<path d="M{x - 4.5} {y2 - 8} L{x} {y2} L{x + 4.5} {y2 - 8} Z" style="fill: var(--muted)"/>')


def lane(x: int, tag: str, head: str, steps: list[list[str]], pick: bool) -> str:
    out = [f'<text class="tag" x="{x}" y="20" font-size="14">{tag}</text>', f'<text class="head" x="{x + 30}" y="20">{head}</text>']
    y = 38
    for i, lines in enumerate(steps):
        out.append(box(x, y, 246, lines, pick and i == len(steps) - 1))
        h = 16 + LINE * len(lines)
        if i < len(steps) - 1:
            out.append(arrow(x + 123, y + h, y + h + 26))
        y += h + 26
    return "".join(out)


LINK_RESOLVES = SHOW_HEAD.format(title="How a shared link resolves", tokens="__TOKENS__") + """
<h1>How a shared link resolves</h1>
<p class="meta">share-a-view-by-link · Q3, the two answers side by side</p>
<svg viewBox="0 0 520 430" role="img" aria-label="Two flows from the sender's share to what the reader sees">
""" + lane(2, "(a)", "the link names the view", [
    ["Sam shares the view", "“groceries, last 90 days”"],
    ["the link: /v/k3f9q2", "names the saved view"],
    ["opened, the server reads", "the view as Sam left it:", "filters, sort, columns"],
    ["Alex sees today's rows:", "41, through Sam's filters,", "and every later edit"],
], pick=True) + lane(272, "(b)", "the link carries rows", [
    ["Sam shares the view", "“groceries, last 90 days”"],
    ["the rows are copied:", "38 rows, as of Oct 6"],
    ["the link: /s/7hd2w1", "names the copy, which", "needs storage, an expiry"],
    ["Alex sees Oct 6's rows:", "38, however the ledger", "has moved since"],
], pick=False) + """
<text class="note" x="2" y="424">outlined: the pick, one copy of the view, read as the ledger is now</text>
</svg>
<table>
<tr><th>after the link is sent</th><th>(a) the view</th><th>(b) a snapshot</th></tr>
<tr><td>Sam edits the view</td><td>Alex sees the edit</td><td>Alex does not</td></tr>
<tr><td>a new row lands</td><td>it shows</td><td>it does not</td></tr>
<tr><td>Sam revokes the link</td><td>it stops opening</td><td>it stops opening</td></tr>
<tr><td>new storage</td><td>none</td><td>the copied rows, until they expire</td></tr>
</table>
<p>Either way the link opens without Sam's login. What differs is whether Alex reads the ledger as it is, or as it
was the moment Sam shared it.</p>
</body></html>
"""

WHAT_A_VIEW_HOLDS = SHOW_HEAD.format(title="What a view holds", tokens="__TOKENS__") + """
<h1>What a view holds</h1>
<p class="meta">saved-views · Q1 and Q2</p>
<table>
<tr><th>field</th><th>restores</th><th>example</th></tr>
<tr><td>filters</td><td>which rows show</td><td><code>groceries, since Jul 8</code></td></tr>
<tr><td>sort</td><td>their order</td><td><code>amount, largest first</code></td></tr>
<tr><td>columns</td><td>what each row says</td><td><code>on, payee, amount</code></td></tr>
</table>
<p>Kept in a <code>views</code> table in the ledger's database, keyed by user and name.</p>
</body></html>
"""

WAVES = SHOW_HEAD.format(title="csv-import waves", tokens="__TOKENS__") + """
<h1>The csv-import waves</h1>
<p class="meta">csv-import · dispatch</p>
<table>
<tr><th>wave</th><th>tickets</th><th>why together</th></tr>
<tr><td>1</td><td>upload-and-parse-report</td><td>everything reads its report</td></tr>
<tr><td>2</td><td>map-columns-to-fields, duplicate-rule</td><td>no file in common</td></tr>
<tr><td>3</td><td>commit-the-import</td><td>waits on both of wave 2</td></tr>
</table>
</body></html>
"""

RUNS = SHOW_HEAD.format(title="Four hundred runs", tokens="__TOKENS__") + """
<h1>Four hundred runs under load</h1>
<p class="meta">flaky-upload-test</p>
<table>
<tr><th>ran beside</th><th>runs</th><th>failed</th></tr>
<tr><td>test_upload_too_large</td><td>96</td><td>10</td></tr>
<tr><td>any other test</td><td>304</td><td>0</td></tr>
</table>
</body></html>
"""

THREE_CHARTS = SHOW_HEAD.format(title="Three charts", tokens="__TOKENS__") + """
<h1>Three ways to draw a month against its budget</h1>
<p class="meta">budget-chart · September</p>
<p>Bars against a budget line; a bullet per category; the month's running total against the budget's.</p>
</body></html>
"""

PAGES = {
    "show/share-a-view-by-link/link-resolves.html": LINK_RESOLVES,
    "show/saved-views/what-a-view-holds.html": WHAT_A_VIEW_HOLDS,
    "show/csv-import/waves.html": WAVES,
    "show/flaky-upload-test/runs.html": RUNS,
    "show/budget-chart/three-charts.html": THREE_CHARTS,
}

# What the statusline last read of the account's rate limits: percent used, and hours until the window resets.
USAGE = {"five_hour": (34, 2.2), "seven_day": (58, 76)}
