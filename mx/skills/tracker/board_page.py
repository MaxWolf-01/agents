"""The board's page: what it shows of the tickets, as values, those values as markup, and the
template the markup goes into, with the page's stylesheet and its scripts.

board.py reads the tracker into these values and fills the template with them; nothing here reads
the tracker. What a ticket writes in prose reaches the values already rendered (board.render_body),
a criterion's checkbox included (board.ticked).
"""

import html
from dataclasses import dataclass
from string import Template
from typing import TYPE_CHECKING, Literal

import markdown

if TYPE_CHECKING:
    from board import Ticket


# ---- what the page shows, as values ---------------------------------------


ALONE = "alone"  # the pill for a ticket with no parent ticket and no child tickets


@dataclass(frozen=True)
class Absence:
    """An optional source the render did without, said once on the page: GitHub, the model, the
    transcripts. A server is one only the open page can tell it lacks, so the notes for the review
    pages' and the board's own are `hidden` and the page shows them."""

    source: str
    words: str
    hidden: bool = False


@dataclass(frozen=True)
class Copy:
    """A button that copies `text`: `word` is what the button itself says, `does` what its click
    does, and `note` what the page says once it has."""

    kind: Literal["qcopy", "qall", "qgroup", "resume", "runcopy"]
    word: str
    does: str
    text: str
    note: str

    @property
    def shows(self) -> str:
        """What it copies, as its hover words carry it: cut off with an ellipsis where it runs past
        COPY_CAP."""
        return self.text if len(self.text) <= COPY_CAP else self.text[:COPY_CAP].rstrip() + "…"


COPY_CAP = 220  # how much of what it copies a button shows before the rest is an ellipsis


@dataclass(frozen=True)
class Asked:
    """One question, as a row lists it or an opened ticket carries it. The headline, the detail and
    the ruling are inline HTML; `says` is the question in full, which the row's headline carries on
    hover since its column may cut it short. `copy` is None where no button copies it: a ruled
    question, or one left on a done ticket. `of` is the slug of the folded child ticket a parent's
    row asks it for, "" for the row's own."""

    tag: str
    headline: str
    detail: str
    ruling: str  # "Ruled <date>: <answer>", "" while it is open
    says: str
    copy: Copy | None
    of: str = ""


@dataclass(frozen=True)
class Worked:
    """A session that worked on the ticket, as an opened ticket lists it."""

    title: str
    when: str  # the days it committed on the ticket
    page: str  # the link to its session page, "" where the board links none
    resume: Copy


@dataclass(frozen=True)
class Artefact:
    """A file of the ticket's show directory, as an opened ticket links it."""

    name: str  # its path inside the show directory
    href: str
    run: Copy | None  # the button copying the command that runs it, for a file that runs


@dataclass(frozen=True)
class Block:
    """One block of an opened ticket: its label, the ticket's own words in it, rendered, and the
    questions, sessions or artefacts it lists. The comments are the block labelled `comments`,
    which the page folds away as history; the words a ticket writes above its first heading are a
    block with no label."""

    label: str | None
    prose: str = ""
    asked: tuple[Asked, ...] = ()
    worked: tuple[Worked, ...] = ()
    artefacts: tuple[Artefact, ...] = ()


PAGE_TIP = "This session's page: its turns, the questions it waits on you for, and what it produced. Opens in a new tab."


WHEN_TIP = "When this session first committed on the ticket, and when it last did."


MarkKind = Literal["tree", "slug", "asks", "kin", "rp", "gh", "time", "pri", "chip"]  # in the order a row shows them


@dataclass(frozen=True)
class Mark:
    """A row mark: the words it shows, and what it says it means on hover. `look` is what dresses
    it beyond its kind: what a row asks, a priority, the state GitHub gave a link, a blocker's
    status. `href` is where a mark that is a link goes."""

    kind: MarkKind
    shows: str
    says: str
    look: str = ""
    href: str = ""


@dataclass(frozen=True)
class Row:
    """One ticket as the board shows it. `group` is the group it sits in, board.FOLDED for a row folded
    under its parent ticket's, and `kids` are the rows folded under it. `questions` are the open
    questions it lists while folded, `copied` those questions as a copy button puts them on the
    clipboard ("" where it asks none), with `copy_all` copying them once there are two; `search` is
    the words a filter finds it by, its folded rows' included. What it reads as opened is its
    ticket's `blocks`."""

    ticket: Ticket
    group: str
    marks: tuple[Mark, ...]
    questions: tuple[Asked, ...]
    copied: str
    copy_all: Copy | None
    search: str
    kids: tuple["Row", ...]


@dataclass(frozen=True)
class Group:
    """One of the board's groups: its rows in the order it lists them, and the button copying every
    question they ask, which only a group whose rows ask one has. The done group is `folded`."""

    state: str
    label: str
    rows: tuple[Row, ...]
    copy: Copy | None
    folded: bool


@dataclass(frozen=True)
class Pill:
    """A tree's pill in the top bar, which hides and shows its rows: its counts, said in full on
    hover, whether any ticket in it waits on the user, and the dependency graph the side column
    draws for it, None where nothing in it waits on anything."""

    tree: str
    says: str
    done: int
    total: int
    waits: bool
    graph: str | None


@dataclass(frozen=True)
class View:
    """The board as values: every ticket's row by slug, the ones folded under another's included,
    the groups that hold a row in the order the page shows them, and a pill per tree."""

    rows: dict[str, Row]
    groups: tuple[Group, ...]
    pills: tuple[Pill, ...]


TAG_TIP = (
    "The ticket's own numbering for this question.\n"
    "A session that takes your answer records it under this tag as a `Ruled <date>:` line, which is "
    "what clears the question from the board."
)


@dataclass(frozen=True)
class Briefed:
    """The head of the side column: the briefing as markdown, when it was written as the column
    shows it, and the words that says on hover."""

    text: str
    when: str
    says: str


# ---- the values as markup -------------------------------------------------


def group_html(g: Group) -> str:
    return (
        f'<details class="grp" id="grp-{g.state}" data-state="{g.state}"{"" if g.folded else " open"}>'
        f'<summary><h2>{g.label} <span class="n">{len(g.rows)}</span>{copy_html(g.copy) if g.copy else ""}</h2></summary>'
        f'<div class="tickets">{"".join(map(row_html, g.rows))}</div></details>'
    )


def row_html(r: Row) -> str:
    """One ticket row, every mark in a fixed column: the tree, the slug and what the row asks, then
    the name with the marks of its line, the brief under it and, while the row is folded, the open
    questions under that; then the user's time, the priority and the blockers, which move under the
    name below a width. The rows folded under it, then the ticket's remaining text, fold under the
    row."""
    t = r.ticket

    def some(*kinds: MarkKind) -> str:
        return "".join(mark_html(m) for m in r.marks if m.kind in kinds)

    brief = f'<span class="brief">{clipped_html(t.brief)}</span>' if t.brief else ""
    inner = f'<div class="kids">{"".join(map(row_html, r.kids))}</div>' if r.kids else ""
    return (
        row_open(r) + some("tree", "slug", "asks")
        + f'<span class="main"><span class="titleline"><span class="title" data-tip="{html.escape(t.title)}">{clipped(t.title)}</span>'
        f'{some("kin", "rp", "gh")}</span>{brief}{asks_html(r)}</span>'
        f'<span class="meta">{some("time", "pri")}<span class="chips">{some("chip")}</span></span>'
        f'</summary>{inner}<div class="body">{"".join(map(block_html, t.blocks))}</div></details>'
    )


def row_open(r: Row) -> str:
    """The element every row is: what the page's script matches a row on, the file a click on its
    slug copies, and the questions it asks, which the needs-me group's button copies while the row
    is on show."""
    t = r.ticket
    asked = f' data-asks="{len(r.questions)}" data-asked="{html.escape(r.copied)}"' if r.copied else ""
    return (
        f'<details class="ticket row-{t.status}" id="t-{t.slug}" data-tree="{html.escape(t.tree or ALONE)}" '
        f'data-slug="{html.escape(t.slug)}" data-search="{html.escape(r.search)}" data-path="{html.escape(str(t.path))}"{asked}><summary>'
    )


# Each mark's element by its kind. A tree or a slug clips its words to its column inside an element
# of its own, since a box that hides its overflow would hide its own hover words too.
MARK_HTML = {
    "tree": '<span class="tree" data-tip="{says}">{clipped}</span>',
    "slug": '<span class="slug" data-tip="{says}">{clipped}</span>',
    "asks": '<span class="asks a-{look}" data-tip="{says}">{shows}</span>',
    "kin": '<span class="kin" data-tip="{says}">{shows}</span>',
    "rp": '<a class="rp" href="{href}" target="_blank" onclick="event.stopPropagation()" data-tip="{says}">{shows}</a>',
    "gh": '<a class="gh {look}" href="{href}" target="_blank" onclick="event.stopPropagation()" data-tip="{says}">{shows}</a>',
    "time": '<span class="time" data-tip="{says}">{shows}</span>',
    "pri": '<span class="pri {look}" data-tip="{says}">{shows}</span>',
    "chip": '<a class="chip {look}" href="{href}" onclick="event.stopPropagation()" data-tip="{says}">{shows}</a>',
}


def mark_html(m: Mark) -> str:
    return MARK_HTML[m.kind].format(
        shows=html.escape(m.shows), says=html.escape(m.says), look=html.escape(m.look), href=html.escape(m.href),
        clipped=clipped(m.shows),
    )


def clipped(text: str) -> str:
    """A mark's words, cut off with an ellipsis where its column is too narrow."""
    return clipped_html(html.escape(text))


def clipped_html(markup: str) -> str:
    """The same, for words already rendered: a question's headline carries code and emphasis."""
    return f'<span class="clip">{markup}</span>'


def asks_html(r: Row) -> str:
    """The open questions under a folded row: each one's tag and headline with the button that
    copies it, a folded child's under its slug, and the row's copy-all.

    The page's style hides the list while the row is open, where the block below and the rows
    folded under it carry the same questions, so an opened row shows each of them once."""
    if not r.questions:
        return ""
    lines = "".join(
        f'<span class="q"><span class="qtag" data-tip="{html.escape(TAG_TIP)}">'
        + (f"{html.escape(q.of)} " if q.of else "") + f"{q.tag}</span>"
        f'<span class="qhead" data-tip="{html.escape(q.says)}">{clipped_html(q.headline)}</span>'
        + copy_html(q.copy) + "</span>"
        for q in r.questions
    )
    return f'<span class="qs">{lines}' + (copy_html(r.copy_all) if r.copy_all else "") + "</span>"


def copy_html(c: Copy) -> str:
    """A button that copies and says so: what it copies is its hover words, and its note is what
    the page's own note says once it has. It is a span, as the row's number is, since the page
    handles the click itself."""
    return (f'<span class="copier {c.kind}" data-copy="{html.escape(c.text)}" data-copied="{html.escape(c.note)}" '
            f'data-tip="{html.escape(c.does)}\n\n{html.escape(c.shows)}">{html.escape(c.word)}</span>')


def block_html(b: Block) -> str:
    """One block of an opened ticket. The comments are folded, so they open only when the reader
    asks for them: the conversation on a ticket and a build's closing comment are what happened,
    not what the ticket is."""
    if b.label == "comments":
        return f'<details class="history"><summary><span class="label">comments</span></summary>{b.prose}</details>'
    label = f'<p class="label">{html.escape(b.label)}</p>' if b.label else ""
    asked = "".join(
        f'<li class="question{" ruled" if q.ruling else ""}">'
        f'<span class="tag" data-tip="{html.escape(TAG_TIP)}">{q.tag}</span><div>'
        f'<p class="head">{q.headline}</p>'
        + (f'<p class="detail">{q.detail}</p>' if q.detail else "")
        + (f'<p class="ruling">{q.ruling}</p>' if q.ruling else "")
        + "</div>" + (copy_html(q.copy) if q.copy else "") + "</li>"
        for q in b.asked
    )
    worked = "".join(
        f'<li><span class="stitle">{html.escape(s.title)}</span>'
        f'<span class="when" data-tip="{html.escape(WHEN_TIP)}">{html.escape(s.when)}</span>'
        + (f'<a class="spage" href="{html.escape(s.page)}" target="_blank" data-tip="{html.escape(PAGE_TIP)}">page</a>' if s.page else "")
        + copy_html(s.resume) + "</li>"
        for s in b.worked
    )
    made = "".join(
        f'<li><a href="{html.escape(a.href)}" target="_blank">{html.escape(a.name)}</a>'
        + (copy_html(a.run) if a.run else "") + "</li>"
        for a in b.artefacts
    )
    lists = "".join(f'<ul class="{kind}">{items}</ul>' for kind, items in
                    (("asked", asked), ("sessions", worked), ("artefacts", made)) if items)
    return f'<section class="block">{label}{b.prose}{lists}</section>'


def pill_html(p: Pill) -> str:
    # the dot says the tree holds work of the user's own; the counts beside it already say how much
    dot = '<i class="dot"></i>' if p.waits else ""
    return (
        f'<button class="treechip" data-tree="{html.escape(p.tree)}" title="{html.escape(p.says)}">{dot}{html.escape(p.tree)} '
        f'<span class="dim">{p.done}/{p.total}</span></button>'
    )


def briefing_html(b: Briefed) -> str:
    return (
        f'<div class="bhead"><span class="label">briefing</span>'
        f'<span class="bwhen" title="{html.escape(b.says)}">{html.escape(b.when)}</span></div>'
        f'<div class="btext">{markdown.markdown(b.text)}</div>'
    )


def absence_html(a: Absence) -> str:
    return f'<p class="absent" data-absent="{html.escape(a.source)}"{" hidden" if a.hidden else ""}>{html.escape(a.words)}</p>'


PADDING = {"asks": 0.85, "pri": 0.95}  # the tag's border and the pill's, which sit outside the words


def column_tokens(selector: str, widths: dict[str, int]) -> str:
    """Column widths as the CSS tokens the row's grid reads."""
    return f"  {selector} {{\n" + "".join(
        f"    --col-{kind}: calc({count} * var(--mark-char) + {PADDING.get(kind, 0)}rem);\n"
        for kind, count in widths.items()
    ) + "  }\n"


# ---- the template ---------------------------------------------------------


# The full size graph, as the overlay over the board and the window of its own both wear it: one
# head with the tree/whole-tracker switch and whatever that view adds, over one box holding
# either a note or the drawing. Two views of one thing, so one markup and one script for both.
GRAPH_VIEW = Template(
    '<div class="gfhead"><span class="label">dependencies</span><span class="gname"></span>'
    '<span class="seg"><button class="btn" data-gmode="tree" title="${tree_says}">tree</button>'
    '<button class="btn" data-gmode="all" title="${all_says}">all</button></span>${extra}</div>'
    '<div class="gfbody"><div class="gnote" hidden></div><div class="gsvg"></div></div>'
)


OVERLAY = GRAPH_VIEW.substitute(
    tree_says="the graph of the row's top-level ticket (a)", all_says="the whole tracker's graph (a)",
    extra='<button class="btn" id="gwinfull" title="the same graph in a window of its own, beside the board (w)">window</button>'
          '<button class="btn" id="gclose" title="back to the board (Esc)">close</button>',
)


# the window has no keys of its own, so its switch says what it does without naming one
GRAPH_WINDOW = GRAPH_VIEW.substitute(
    tree_says="the graph of the row the board is on", all_says="the whole tracker's graph",
    extra='<span class="gorphan">the board this followed is gone</span>',
)


# What the two views do, run in the board's page and again in the window's: the window is another
# document, and once the board has reloaded once it is another origin too, so nothing it calls can
# live in the board's script. One home here, two realms at run time.
VIEW_JS = r"""
  const hrefOf = (a) => a && (a.getAttribute("href") ?? a.getAttribute("xlink:href"));

  function markCur(root, id) {
    for (const n of root.querySelectorAll("g.node.cur")) n.classList.remove("cur");
    if (id) root.querySelector('g.node[id*="-' + id + '-"]')?.classList.add("cur");
  }

  // A graph at full size is wider than the box it sits in, so the box is dragged as well as
  // scrolled. The click a drag ends with is swallowed wherever it lands, or a pan that finished
  // over a node would open that node, and one that finished on the overlay's backdrop would close
  // the overlay.
  function pannable(el) {
    const doc = el.ownerDocument;
    let from = null, swallow = false;
    el.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      from = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop, moved: 0 };
      e.preventDefault();  // no text or node selection under the drag
    });
    doc.addEventListener("mousemove", (e) => {
      if (!from) return;
      from.moved = Math.max(from.moved, Math.abs(e.clientX - from.x) + Math.abs(e.clientY - from.y));
      el.classList.toggle("panning", from.moved > 4);
      el.scrollLeft = from.left - (e.clientX - from.x);
      el.scrollTop = from.top - (e.clientY - from.y);
    });
    doc.addEventListener("mouseup", () => {
      if (!from) return;
      swallow = from.moved > 4;
      el.classList.remove("panning");
      from = null;
    });
    doc.addEventListener("click", (e) => {
      if (!swallow) return;
      swallow = false;
      e.preventDefault();
      e.stopPropagation();
    }, true);
  }

  // A node at full size takes the board to its row: the overlay closes on it, the window of its own
  // stays where it is and the board moves behind it.
  function nodeClicks(el, go) {
    el.addEventListener("click", (e) => {
      const href = hrefOf(e.target.closest("a"));
      if (href?.startsWith("#")) { e.preventDefault(); go(href); }
    });
  }
  function attach(el, go) { pannable(el); nodeClicks(el, go); }

  // One paint for both views. A view whose key has not moved keeps its drawing, and with it
  // whatever the reader had panned to; only the mark on the cursor's node moves.
  function paintView(root, view, last) {
    const name = root.querySelector(".gname");
    name.textContent = view.name;
    for (const b of root.querySelectorAll("[data-gmode]")) b.classList.toggle("on", b.dataset.gmode === view.mode);
    const body = root.querySelector(".gfbody"), svg = body.querySelector(".gsvg");
    if (view.key !== last) {
      const note = body.querySelector(".gnote");
      note.textContent = view.note;
      note.hidden = !!view.svg;
      svg.innerHTML = view.svg;
      body.scrollTo(0, 0);
    }
    markCur(svg, view.cur);
    return view.key;
  }
"""


# The page's stylesheet: the house tokens, then the board's own rules. `${columns}` is where PAGE
# puts the widths of a row's fixed columns (board.columns).
STYLE = r"""  /* The house tokens, copied from mx/skills/house-style/tokens.css: colours as light-dark() pairs,
     the fonts, and the base rules. The type roles there are for a page of prose; a board sets its
     own below. --muted goes darker than the house value, which is a day-scheme readability fix:
     the board's small text is read on parchment at 100% zoom. */
  :root {
    color-scheme: light dark;
    --ground: light-dark(#f4e4cd, #14110e);
    --ground-2: light-dark(#eddabe, #1b1713);
    --edge: light-dark(#cfbca3, #463f37);
    --muted: light-dark(#4c443c, #b0a89e);
    --body: light-dark(#37261d, #ede3d2);
    --strong: light-dark(#22140b, #faf2dc);
    --accent: light-dark(#426724, #75a252);
    --accent-2: light-dark(#674806, #cdb78a);
    --wash: light-dark(rgb(66 103 36 / 0.16), rgb(117 162 82 / 0.22));
    --wash-ink: color-mix(in srgb, var(--muted) 6%, transparent);
    --mark: light-dark(rgb(168 139 81 / 0.35), rgb(205 183 138 / 0.35));
    --font-body: "Newsreader", Georgia, serif;
    --font-mono: "IBM Plex Mono", ui-monospace, monospace;
    --radius: 6px;
    --topbar-h: 52px;  /* measured once the bar is laid out, since it wraps on a narrow window */
    /* one character of a mark: the marks are monospace at .78rem, and IBM Plex Mono advances .6em,
       with the rest the slack a fallback mono needs */
    --mark-char: calc(.78rem * .64);
  }
  /* the row's fixed columns, each as wide as the widest mark that lands in it (board.columns) */
${columns}
  [data-theme="day"] { color-scheme: light; }
  [data-theme="night"] { color-scheme: dark; }

  /* The callout hues of mwolf.dev: what a row asks wears one each, the priority ramps on the
     first, a question's tag takes the same rose as the answer it waits for, and the user's time
     has the last to itself. The teal is picked again from the
     prototype's, away from the moss accent, which it read as by day. Each day value clears 4.6:1
     against its own 12% tint, since that is the background the tag's text sits on. */
  :root {
    --c-pink: light-dark(#7d4172, #d9a2d0);
    --c-gold: light-dark(#725614, #d9b36f);
    --c-rose: light-dark(#963f37, #fabeb4);
    --c-purple: light-dark(#6546b3, #b8a4ff);
    --c-time: light-dark(#255a63, #86bcc4);
  }

  * { box-sizing: border-box; }
  html { scrollbar-color: var(--edge) var(--ground); }
  body { margin: 0; background: var(--ground); color: var(--body);
    font: 400 15.5px/1.5 var(--font-body); -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
  p { margin: 0; }
  a { color: inherit; text-decoration: none; transition: color 150ms; }
  a:hover { color: var(--accent); }
  ::selection { background: var(--mark); }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
  code, kbd, pre { font-family: var(--font-mono); }
  .tree, .slug, .asks, .pri, .time, .chip, .rp, .gh, .label, .n, .treechip, .search,
    .btn, .gname, .log, .footmeta, kbd { font-family: var(--font-mono); }

  /* ---- the top bar: the project, the tree pills, the filter, the graph mode, the scheme ---- */
  .top { position: sticky; top: 0; z-index: 10; display: flex; gap: 1rem; align-items: center; min-height: 52px;
    padding: .4rem 1.25rem; background: var(--ground); border-bottom: 1px solid var(--edge); }
  .top .name { font-weight: 600; color: var(--strong); white-space: nowrap; }
  .top .name span { color: var(--muted); font-weight: 400; }
  .treenav { display: flex; gap: .4rem; overflow-x: auto; flex: 1; min-width: 0; scrollbar-width: none; }
  .treechip { padding: .1rem .7rem; border: 1px solid var(--edge); border-radius: 999px; background: var(--ground-2);
    font-size: .8rem; color: var(--muted); cursor: pointer; white-space: nowrap; display: inline-flex; gap: .4em;
    align-items: center; transition: color 150ms, border-color 150ms; }
  .treechip:hover { color: var(--accent); border-color: var(--accent); }
  .treechip.off { opacity: .5; text-decoration: line-through; }
  .dim { color: var(--muted); }
  .dot { display: inline-block; width: .45em; height: .45em; border-radius: 50%; background: var(--accent-2); }
  .search { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius); color: var(--body);
    font-size: .82rem; padding: .25rem .6rem; width: 12rem; }
  .search:focus { outline: none; border-color: var(--accent); }
  .btn { background: none; border: 0; color: var(--muted); font-size: .82rem; cursor: pointer; padding: .2rem .45rem;
    transition: color 150ms; white-space: nowrap; }
  .btn:hover, .btn.on { color: var(--accent); }
  .seg { display: inline-flex; border: 1px solid var(--edge); border-radius: var(--radius); }
  .seg .btn.on { background: var(--wash); }
  .seg .btn + .btn { border-left: 1px solid var(--edge); }
  .scheme { display: inline-flex; align-items: center; }
  [data-theme="night"] .sun, [data-theme="day"] .moon { display: none; }

  /* what this render did without, said once each */
  .absences { padding: .6rem 1.25rem 0; display: grid; gap: .2rem; max-width: 110rem; margin: 0 auto; }
  .absences:empty { display: none; }
  .absent { font-size: .92rem; color: var(--muted); border-left: 2px solid var(--accent-2); padding-left: .6rem; }

  /* ---- the rows, the graph panel beside them on a wide window ---- */
  main { display: grid; grid-template-columns: minmax(0, 1fr); gap: 1.5rem; padding: 1rem 1.25rem 5rem;
    align-items: start; max-width: 110rem; margin: 0 auto; }
  /* one column: the graph above the rows, where a glance still reaches it, rather than past every group */
  .side { order: -1; position: sticky; top: var(--topbar-h); max-height: 40vh; overflow: auto; z-index: 5;
    background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); padding: .7rem .9rem; }
  .side.folded .gbody { display: none; }
  @media (min-width: 1400px) {
    main { grid-template-columns: minmax(0, 1fr) minmax(16rem, 22rem); gap: 2.5rem; }
    .side { order: 0; top: calc(var(--topbar-h) + 1rem); max-height: calc(100vh - var(--topbar-h) - 2rem);
      border: 0; border-left: 1px solid var(--edge); border-radius: 0; padding: 0 0 0 1.75rem; }
    /* the column leaves a name beside the buttons a few letters, so it takes the line under them */
    .ghead .label { flex: 1; }
    .ghead .gname { order: 1; flex-basis: 100%; }
    .ghead .gname:empty { display: none; }  /* no row under the cursor: no graph, so no line for its name */
  }
  /* the briefing, at the head of the column: prose, so it is set as the page's prose is */
  .briefing { margin-bottom: 1.1rem; }
  .bhead { display: flex; gap: .5rem; align-items: baseline; justify-content: space-between; margin-bottom: .3rem; }
  .bwhen { color: var(--muted); font-size: .8rem; font-family: var(--font-mono); }
  .btext { font-size: .92rem; line-height: 1.55; }
  .btext > :first-child { margin-top: 0; }
  .btext > :last-child { margin-bottom: 0; }
  .btext h1, .btext h2 { font-size: .82rem; color: var(--muted); font-family: var(--font-mono); font-weight: 400;
    margin: .9rem 0 .35rem; text-transform: lowercase; }
  .btext h1::after, .btext h2::after { content: none; }  /* the rule an h2 carries over a group of rows is for a group of rows */
  .btext ul, .btext ol { margin: .2rem 0; padding-left: 1.1rem; }
  .btext li { margin-top: .3rem; }
  .btext strong { color: var(--strong); font-weight: 600; }

  .ghead { display: flex; flex-wrap: wrap; gap: .5rem; align-items: baseline; margin-bottom: .3rem; }
  /* the name says which graph is on show, so it wraps rather than being cut short */
  .gname { color: var(--muted); font-size: .8rem; flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .gnote { color: var(--muted); font-size: .92rem; padding: .4rem 0; }
  .mermaid { margin: 0; display: flex; justify-content: center; }
  /* out of the layout, not merely invisible: a graph source is one unwrappable line, and a render
     that has not come back yet would widen the column it sits in */
  .mermaid:not(:has(svg)) { display: none; }
  .mermaid svg { max-width: 100%; height: auto; }
  .side g.node.cur rect, .side g.node.cur polygon,
    .gfbody g.node.cur rect, .gfbody g.node.cur polygon { stroke-width: 2.5px !important; }

  /* ---- the same graph at full size: over the board, or in a window of its own ---- */
  .side .gbody { cursor: zoom-in; }  /* the preview opens the full size view */
  .side .gbody a { cursor: pointer; }
  #gfull { position: fixed; inset: 0; z-index: 90; display: none; padding: 1.25rem;
    background: color-mix(in srgb, var(--strong) 40%, transparent); }
  #gfull.open { display: block; }
  #gfull .card { height: 100%; display: flex; flex-direction: column; overflow: hidden;
    background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); }
  .gfhead { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap;
    padding: .45rem .8rem; border-bottom: 1px solid var(--edge); }
  /* safe centring: a graph that fits sits in the middle of the box, one that does not starts at
     the edge the scroll starts from rather than having its first node cut off */
  .gfbody { flex: 1; min-width: 0; min-height: 0; overflow: auto; padding: 1rem;
    display: flex; justify-content: safe center; align-items: safe center; }
  .gfbody.panning { cursor: grabbing; user-select: none; }
  /* full size is the graph's own size: what shrinks it in the preview is the width it is given */
  .gfbody svg { max-width: none !important; }
  /* the window of its own is the same head and body, with nothing else in the document */
  body.gwin { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
  .gorphan { display: none; color: var(--accent-2); font-size: .8rem; font-family: var(--font-mono); }
  [data-orphan="1"] .gorphan { display: inline; }

  /* ---- a group of rows ---- */
  .grp { margin-bottom: 1.75rem; }
  .grp > summary { list-style: none; cursor: pointer; padding: .3rem 0 .6rem; position: relative; }
  .grp > summary::-webkit-details-marker { display: none; }
  .grp.empty { display: none; }
  h2 { font-size: .82rem; font-weight: 400; color: var(--muted); margin: 0; display: flex; align-items: center;
    gap: .6rem; font-family: var(--font-mono); }
  h2::after { content: ""; flex: 1; border-top: 1px solid var(--edge); }
  h2 .n { color: var(--muted); }
  .grp > summary::before { content: "▾"; color: var(--muted); font-size: .7rem; margin-right: .4rem; }
  .grp:not([open]) > summary::before { content: "▸"; }
  .label { font-size: .82rem; color: var(--muted); font-family: var(--font-mono); }

  /* ---- a row: every mark in a fixed column, so the eye scans one ---- */
  .ticket { border-top: 1px solid var(--edge); scroll-margin-top: calc(var(--topbar-h) + 3rem); scroll-margin-bottom: 3rem; }
  .ticket:first-child { border-top: 0; }
  .ticket.off, .ticket.miss { display: none; }
  .ticket > summary { display: grid; column-gap: .9rem; row-gap: .2rem; align-items: baseline; padding: .55rem .5rem;
    cursor: pointer; list-style: none; border-radius: var(--radius); transition: background-color 150ms;
    grid-template-columns: var(--col-tree) var(--col-slug) var(--col-asks) minmax(0, 1fr) var(--col-time) var(--col-pri) var(--col-chips);
    grid-template-areas: "tree slug asks main time pri chips"; }
  .ticket > summary::-webkit-details-marker { display: none; }
  .ticket > summary:hover { background: var(--wash-ink); }
  .ticket.kcur > summary, .ticket.flash > summary { background: var(--wash); }
  .tree { grid-area: tree; font-size: .78rem; color: var(--muted); min-width: 0; }
  /* a box that hides its overflow hides its own tooltip with it, so the ellipsis sits one level in */
  .clip { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .slug { grid-area: slug; font-size: .78rem; color: var(--muted); cursor: copy; min-width: 0; }
  .slug:hover { color: var(--accent); }
  .main { grid-area: main; display: grid; gap: .1rem; min-width: 0; }
  /* the name is what a row is read by, so it keeps its words: the links wrap under it rather than
     taking the width off it */
  .titleline { display: flex; flex-wrap: wrap; gap: 0 .6rem; align-items: baseline; min-width: 0; }
  .title { color: var(--strong); min-width: 0; }
  .row-done > summary .title, .row-blocked > summary .title, .row-proposed > summary .title { color: var(--muted); }
  .titleline > a { flex: none; }
  .brief { color: var(--muted); font-size: .88rem; line-height: 1.4; min-width: 0; }
  /* an opened row reads its brief whole, so nothing there cuts it */
  .ticket[open] > summary .brief .clip { white-space: normal; overflow: visible; }
  /* a needs-me row's open questions, under the name they belong to; an opened row reads them in
     its questions block instead */
  .qs { display: grid; gap: .15rem; justify-items: start; padding: .2rem 0 .1rem; min-width: 0; }
  .ticket[open] > summary .qs { display: none; }
  .q { display: flex; gap: .5rem; align-items: baseline; max-width: 100%; min-width: 0; }
  .qtag, .asked .tag { flex: none; font-family: var(--font-mono); font-size: .74rem; color: var(--c-rose); }
  .qhead { color: var(--body); font-size: .88rem; min-width: 0; }
  .copier { flex: none; font-family: var(--font-mono); font-size: .72rem; color: var(--muted);
    border: 1px solid var(--edge); border-radius: 4px; padding: 0 .35rem; cursor: copy; overflow: visible; }
  .copier:hover { color: var(--accent); border-color: var(--accent); }
  .meta { display: contents; }
  .asks, .pri, .time, .rp, .gh, .kin { font-size: .78rem; white-space: nowrap; }
  .chip { font-size: .78rem; }
  .asks { grid-area: asks; --c: var(--muted); color: var(--c); justify-self: start; max-width: 100%;
    background: color-mix(in srgb, var(--c) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 38%, transparent); border-radius: 4px; padding: 0 .4rem; }
  .a-review { --c: var(--c-gold); }
  .a-answer { --c: var(--c-rose); }
  .a-session { --c: var(--c-purple); }
  .a-build { background: none; border-color: transparent; padding-left: 0; }
  .a-whole { --c: var(--muted); }
  .kin { color: var(--muted); }
  /* the rows folded under a parent ticket's row, set in by the rule the opened body carries: a
     row's fixed columns leave the name no width to give up to a deeper indent on a narrow window */
  .kids { margin-left: .5rem; border-left: 1px solid var(--edge); }
  .time { grid-area: time; color: var(--c-time); justify-self: end; font-variant-numeric: tabular-nums; }
  /* the priority is a ramp, not a set of categories: one hue, strongest at p1 */
  .pri { grid-area: pri; color: var(--c-pink); justify-self: start; padding: 0 .45rem; border-radius: 999px;
    background: color-mix(in srgb, var(--c-pink) 16%, transparent); }
  .pri.p3 { background: color-mix(in srgb, var(--c-pink) 8%, transparent); }
  .pri.p4, .pri.p5 { color: var(--muted); background: none; padding-left: 0; }
  /* the blockers' column is as fixed as the rest, so a long reference wraps within
     it rather than widening it and pulling the time and the priority out of line */
  .chips { grid-area: chips; display: flex; gap: .35rem; justify-content: flex-end; flex-wrap: wrap; }
  .chip { color: var(--body); overflow-wrap: anywhere; }
  .chip.done { color: var(--muted); text-decoration: line-through; }
  .rp { color: var(--accent); }
  .rp:hover { text-decoration: underline; text-underline-offset: 3px; }
  /* a GitHub reference in the look of its state; github.SAYS says the same in words on hover.
     Open work takes the accent, a review asking for changes the rose a question wears, a merge the
     callout purple, as GitHub marks a merge. Anything closed is struck through and a draft
     underlined. A reference GitHub was not asked about keeps the muted link it has always been. */
  .gh { color: var(--muted); }
  .gh.pr-open, .gh.issue-open { color: var(--accent); }
  .gh.pr-changes { color: var(--c-rose); }
  .gh.pr-merged { color: var(--c-purple); }
  .gh.pr-draft { text-decoration: underline dotted; text-underline-offset: 3px; }
  .gh.pr-closed, .gh.issue-closed { text-decoration: line-through; }

  /* below this width the time, the priority and the blockers move under the name, and the top
     bar's pills take a line of their own rather than scrolling out of sight */
  @media (max-width: 1000px) {
    .top { flex-wrap: wrap; padding: .4rem .75rem; }
    .treenav { flex-basis: 100%; order: 1; }
    main { padding: 1rem .75rem 5rem; }
    .absences { padding: .6rem .75rem 0; }
    .ticket > summary { grid-template-columns: var(--col-tree) var(--col-slug) var(--col-asks) minmax(0, 1fr);
      grid-template-areas: "tree slug asks main" ".    .    .    meta"; }
    .meta { grid-area: meta; display: flex; gap: .9rem; align-items: baseline; flex-wrap: wrap; }
    .time, .pri, .chips { grid-area: auto; justify-self: auto; }
  }
  /* narrower still: the name takes the row's width, with its marks over it and under it */
  @media (max-width: 620px) {
    .ticket > summary { grid-template-columns: minmax(0, var(--col-tree)) var(--col-slug) minmax(0, 1fr);
      grid-template-areas: "tree slug asks" "main main main" "meta meta meta"; }
    .search { flex: 1; width: auto; }
  }

  /* ---- a row, opened ---- */
  .body { padding: .4rem .5rem 1.4rem 1rem; margin-left: .5rem; border-left: 1px solid var(--edge);
    max-width: 46rem; color: var(--body); font-size: .96rem; }
  .body > * + * { margin-top: .8em; }
  .body h3 { font-size: .96rem; font-weight: 600; color: var(--strong); }
  .body a { color: var(--accent); }
  .body code { background: var(--ground-2); border-radius: 3px; padding: 0 .25em; font-size: .85em; }
  .body pre { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius);
    padding: .6rem .8rem; overflow-x: auto; font-size: .82rem; }
  .body pre code { background: none; padding: 0; }
  .body ul, .body ol { padding-left: 1.2em; }
  .body li + li { margin-top: .3em; }
  .body li::marker { color: var(--muted); }
  .body table { border-collapse: collapse; font-size: .9rem; }
  .body th, .body td { text-align: left; padding: .2rem .8rem .2rem 0; border-bottom: 1px solid var(--edge); }
  /* the blocks an opened ticket reads as, each under the word for what it is. The ticket's own
     prose keeps the body's spacing; the word above it sits closer, as a label does */
  .block > * + *, .history > * + * { margin-top: .8em; }
  .block > .label + *, .history > summary + * { margin-top: .35rem; }
  .body .asked, .body .artefacts, .body .sessions { list-style: none; padding: 0; display: grid; gap: .45rem; }
  /* a line of a block is its own containing block, so a mark's words are laid out from that line
     rather than from the whole block */
  .asked > li, .artefacts > li, .sessions > li { display: flex; gap: .6rem; align-items: baseline; position: relative; }
  .asked .head { color: var(--strong); }
  .asked > li > div > * + * { margin-top: .2rem; }
  /* the button that copies the question sits at the end of its line, clear of the words */
  .asked > li > .copier { margin-left: auto; }
  /* a question the user has answered is history: its words stay, the colours that call for one go */
  .asked .ruled > .tag, .asked .ruled .head { color: var(--muted); }
  .artefacts a { overflow-wrap: anywhere; font-size: .82rem; }
  /* the button that copies the command sits at the end of its line, clear of the name */
  .artefacts > li > .copier { margin-left: auto; }
  /* a session is its name and the days it worked, the command that resumes it on the button */
  .sessions .stitle { color: var(--strong); }
  .sessions .when { flex: none; font-family: var(--font-mono); font-size: .74rem; color: var(--muted); }
  .sessions .spage { flex: none; font-size: .82rem; }
  /* a criterion's mark is the glyph its list item carries instead of a bullet */
  .body li.tick { list-style: none; position: relative; }
  .body li.tick::before { content: "○"; display: inline-block; width: 1.2em; margin-left: -1.2em;
    color: var(--muted); font-size: .85em; }
  .body li.tick.met::before { content: "✓"; color: var(--accent); }
  .history > summary { list-style: none; cursor: pointer; }
  .history > summary::-webkit-details-marker { display: none; }
  .history > summary > .label::before { content: "▸"; margin-right: .4rem; }
  .history[open] > summary > .label::before { content: "▾"; }

  /* ---- a mark says in words what it means ---- */
  /* The words appear under the row, at its left edge: the row is the box that is always on screen
     and never hides its overflow, so they cannot be clipped by the mark they belong to or run off
     a narrow window, wherever in the row that mark sits. A group's header is the same box for the
     one mark that sits on it, the button that copies every question in the group. */
  .ticket > summary { position: relative; }
  [data-tip]:hover::after { content: attr(data-tip); position: absolute; z-index: 60; top: calc(100% - .2rem); left: .5rem;
    width: max-content; max-width: min(28rem, 100%); white-space: pre-line; background: var(--ground); color: var(--body);
    border: 1px solid var(--edge); border-radius: var(--radius); padding: .5rem .7rem;
    font: .8rem/1.5 var(--font-mono); text-decoration: none; pointer-events: none;
    box-shadow: 0 2px 10px color-mix(in srgb, var(--strong) 14%, transparent); }

  .log { margin: 0; font-size: .8rem; line-height: 1.8; overflow-x: auto; white-space: pre-wrap; }
  .hash { color: var(--muted); }
  .footmeta { color: var(--muted); font-size: .78rem; margin-top: .8rem; }

  #toast { position: fixed; bottom: 1.2rem; left: 50%; transform: translateX(-50%); z-index: 50; max-width: 90vw;
    background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); padding: .3rem .9rem;
    font: .8rem var(--font-mono); color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    opacity: 0; transition: opacity 200ms; pointer-events: none; }
  #toast.on { opacity: 1; }

  #help { position: fixed; inset: 0; z-index: 100; display: none; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--strong) 40%, transparent); }
  #help.open { display: flex; }
  #help .card { background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); padding: 1.2rem 1.5rem; }
  #help table { border-collapse: collapse; font-size: .9rem; }
  #help td { padding: .2rem 1rem .2rem 0; }
  kbd { font-size: .78rem; border: 1px solid var(--edge); border-radius: 4px; padding: 0 .4rem; color: var(--body); }
"""


PAGE = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>board — ${project}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<script type="importmap">
{"integrity": {
  "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.2.2/dist/mermaid-layout-elk.esm.min.mjs": "sha256-xBkLW+qMellY+DuZMpYPTCrktZEq5EF2eXDqaqcznEU=",
  "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.2.2/dist/chunks/mermaid-layout-elk.esm.min/chunk-SP2CHFBE.mjs": "sha256-OlxTRTJXQsIIjtqqpnZh8ACC0go+GQLkhkrF/rXpGPk=",
  "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.2.2/dist/chunks/mermaid-layout-elk.esm.min/render-FL5BWEWF.mjs": "sha256-Hnzk53loGUiOW5BNdXfD72ZHqAiFm6ndvA8CAGoQZns="
}}
</script>
<script>
  // The scheme before first paint: ?theme= pins it, for a screenshot or a layout check; else the
  // switch's last answer, else the system's.
  (() => {
    const asked = new URLSearchParams(location.search).get("theme");
    const kept = localStorage.getItem("board-theme");
    const night = asked ? asked === "night" : kept ? kept === "night" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = night ? "night" : "day";
  })();
</script>
<style>
""" + STYLE + r"""</style>
</head>
<body data-stamp="${stamp}" data-stamp-src="${stamp_src}">
<div class="top">
  <span class="name">board <span>${project}</span></span>
  <nav class="treenav" id="treenav">${chips}</nav>
  <input class="search" id="search" type="search" placeholder="filter  /" autocomplete="off">
  <span class="seg" id="modes"><button class="btn" data-gmode="tree" title="the graph of the row's top-level ticket (a)">tree</button><button class="btn" data-gmode="all" title="the whole tracker's graph (a)">all</button></span>
  <button class="btn" id="helpbtn" title="keys (?)">?</button>
  <button class="btn scheme" id="scheme" title="the other colour scheme">
    <svg class="sun" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="moon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
  </button>
</div>
<div class="absences">${absences}</div>
<main>
<div class="rows" id="rows">
${groups}
<details class="grp" id="grp-log"><summary><h2>recent commits</h2></summary>
  <pre class="log">${log}</pre>
  <p class="footmeta">${footmeta}</p>
</details>
</div>
<aside class="side" id="side">
  <div class="briefing" id="briefing">${briefing}</div>
  <div class="ghead"><span class="label">dependencies</span><span class="gname" id="gname"></span>
    <button class="btn" id="gopen" title="the graph at full size, over the board (f)">full</button>
    <button class="btn" id="gwinopen" title="the graph at full size, in a window of its own beside the board (w)">window</button>
    <button class="btn" id="sidefold" title="fold the graph (b)">fold</button></div>
  <div class="gbody" id="gbody" title="a preview: a click anywhere but a node opens the graph at full size, over the board">
    <div class="g" data-tree=""><div class="gnote">open a row or move onto one (j / k)</div></div>
    ${graphs}
    <div class="gnote" id="gunloaded" hidden>the graph could not load: its engine, from cdn.jsdelivr.net, did not arrive, or arrived other than its pinned copy</div>
    <div class="gnote" id="gundrawn" hidden>the graph could not be drawn: a piece of its engine, from cdn.jsdelivr.net, did not arrive, or arrived other than its pinned copy; a reload tries again</div>
  </div>
</aside>
</main>

<div id="gfull"><div class="card">${overlay}</div></div>

<div id="help"><div class="card"><table>
<tr><td><kbd>j</kbd> <kbd>k</kbd></td><td>next / previous row (the graph follows)</td></tr>
<tr><td><kbd>J</kbd> <kbd>K</kbd></td><td>next / previous group</td></tr>
<tr><td><kbd>gg</kbd> <kbd>G</kbd></td><td>top / bottom</td></tr>
<tr><td><kbd>x</kbd> <kbd>o</kbd> <kbd>Enter</kbd></td><td>open / close the row</td></tr>
<tr><td><kbd>X</kbd> <kbd>O</kbd></td><td>close / open every group</td></tr>
<tr><td><kbd>z</kbd></td><td>fold / unfold the row's group</td></tr>
<tr><td><kbd>d</kbd></td><td>open the row's review page</td></tr>
<tr><td><kbd>y</kbd></td><td>copy the path of the row's file; a click on its number does too</td></tr>
<tr><td><kbd>a</kbd></td><td>graph: the row's top-level ticket / the whole tracker</td></tr>
<tr><td><kbd>b</kbd></td><td>fold / unfold the graph</td></tr>
<tr><td><kbd>f</kbd></td><td>the graph at full size over the board; a click on a node goes to its row</td></tr>
<tr><td><kbd>w</kbd></td><td>the graph at full size in a window of its own, beside the board</td></tr>
<tr><td><kbd>t</kbd></td><td>the other colour scheme</td></tr>
<tr><td><kbd>1</kbd>…<kbd>9</kbd> <kbd>0</kbd></td><td>hide / show the nth tree; all on</td></tr>
<tr><td><kbd>/</kbd></td><td>filter rows; <kbd>Esc</kbd> clears</td></tr>
<tr><td><kbd>?</kbd></td><td>this help</td></tr>
</table></div></div>
<div id="toast" role="status"></div>

<script>
  // Synchronous state restore, before first paint. The module below runs once the page has
  // parsed; doing any of this there makes every reload visibly collapse the groups and drop
  // expanded tickets for a beat.
  (() => {
    let saved = null, cache = {};
    try {
      saved = JSON.parse(sessionStorage.getItem("board-view") ?? "null");
      cache = JSON.parse(sessionStorage.getItem("board-svg") ?? "{}");
    } catch {}
    // window.name survives navigation in every browser: the fallback carrier
    if (!saved && window.name.startsWith("board:")) {
      try { ({ saved = null, cache = {} } = JSON.parse(window.name.slice(6))); } catch {}
    }
    const off = new Set(JSON.parse(localStorage.getItem("board-off:" + document.title) ?? "[]"));
    for (const b of document.querySelectorAll(".treechip")) b.classList.toggle("off", off.has(b.dataset.tree));
    for (const t of document.querySelectorAll(".ticket")) t.classList.toggle("off", off.has(t.dataset.tree));
    // re-inject cached SVGs: an unchanged graph paints instantly instead of re-running mermaid.
    // Keyed by the scheme too, since mermaid bakes the palette into the SVG.
    for (const el of document.querySelectorAll(".mermaid")) {
      const hit = cache[el.dataset.key + "@" + document.documentElement.dataset.theme];
      if (hit && hit.src === el.textContent) { el.dataset.src = hit.src; el.innerHTML = hit.svg; }
    }
    if (saved) {
      for (const d of document.querySelectorAll("details.grp")) d.open = saved.groups?.includes(d.id) ?? d.open;
      for (const id of saved.open ?? []) document.getElementById(id)?.setAttribute("open", "");
      for (const id of saved.comments ?? []) document.getElementById(id)?.querySelector("details.history")?.setAttribute("open", "");
      document.getElementById("side").classList.toggle("folded", !!saved.folded);
      scrollTo(0, saved.scroll ?? 0);
    }
    window.boardState = { saved, off, cache };
  })();
</script>

<script type="module">
  // The graph engine and its layout come from the CDN the first time a graph is drawn, so a board
  // with no way to the CDN loses its graph and nothing else. A failed load is not retried. Every
  // file is pinned by hash, the layout's chunks through the import map in the head: the local server
  // that opens this page also serves every agent directory to it, so a file changed at the CDN is
  // refused, and the board says the engine did not arrive. mermaid comes as its one-file classic build, which needs
  // one pin where its module build would need one per chunk.
  const MERMAID = ["https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.min.js",
                   "sha256-WB7X10vZBI0OOpE2OSfXLvIpQtdyJUayf3zCnjU5Drg="];
  const ELK = "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.2.2/dist/mermaid-layout-elk.esm.min.mjs";
  const classic = ([src, integrity]) => new Promise((loaded, failed) => {
    const s = Object.assign(document.createElement("script"), { src, integrity, crossOrigin: "anonymous" });
    // the classic build draws every .mermaid on the page at window load unless told not to
    s.onload = () => { globalThis.mermaid.startOnLoad = false; loaded(globalThis.mermaid); };
    s.onerror = () => failed(new Error("refused or missing: " + src));
    document.head.append(s);
  });
  let mermaid = null, loading = null;
  function engine() {
    if (loading) return loading;
    loading = Promise.all([classic(MERMAID), import(ELK)]).then(([m, elk]) => {
      mermaid = m;
      mermaid.registerLayoutLoaders(elk.default);
      setupMermaid();
      return mermaid;
    });
    loading.catch((e) => console.error("the graph engine did not load:", e));
    return loading;
  }
  const drawable = () => engine().then(() => true, () => false);
  const unloaded = document.getElementById("gunloaded"), undrawable = document.getElementById("gundrawn");
  // the engine fetches the rest of itself while it draws, so a draw can fail after the engine loaded
  const drawOf = (id, src) => mermaid.render(id, src + "\n" + classDefs)
    .catch((e) => console.error("the graph did not draw:", e));

  // What the two full size views do, shared with the window of its own, which runs its own copy
  // (VIEW_JS).
${viewjs}

  // Mermaid bakes the colours into the SVG, and a light-dark() token never resolves through
  // getPropertyValue, so every colour is read off a probe element in the scheme on show, and read
  // again when the scheme switches. A node's class names its tokens (board.GRAPH_INK).
  const probe = document.createElement("span");
  probe.style.display = "none";
  document.body.append(probe);
  const rgb = (name) => { probe.style.color = "var(" + name + ")"; return getComputedStyle(probe).color.match(/[\d.]+/g).map(Number); };
  // mermaid's classDef parser takes no rgba(), so a translucent token is laid over the ground and written as hex
  const hex = ([r, g, b, a = 1], [R, G, B] = [0, 0, 0]) =>
    "#" + [r * a + R * (1 - a), g * a + G * (1 - a), b * a + B * (1 - a)].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  let classDefs = "";
  function setupMermaid() {
    const ground = rgb("--ground");
    const ink = (token) => hex(rgb("--" + token), ground);
    const c = Object.fromEntries(["ground", "edge", "muted", "body"].map((n) => [n, ink(n)]));
    classDefs = Object.entries(${graphink}).map(([s, [fill, stroke, text, dash]]) =>
      "  classDef " + s + " fill:" + ink(fill) + ",stroke:" + ink(stroke) + ",color:" + ink(text) +
      (dash ? ",stroke-dasharray:" + dash : "")).join("\n");
    // SVG text labels, not HTML ones: mermaid switches an HTML label into wrapping
    // mode only when its measured width equals the wrap width exactly, and the
    // measurement misses by a fraction of a pixel at any page zoom other than 100%
    // and at some device scale factors (1.75 and 2.225, though not 1.25 or 2), so
    // every long label stays on one line and clips (mermaid-js/mermaid#7794).
    // SVG labels wrap by mermaid's own measure.
    mermaid?.initialize({
      startOnLoad: false, suppressErrorRendering: true, layout: "elk", securityLevel: "loose", theme: "base", htmlLabels: false,
      elk: { mergeEdges: false }, flowchart: { htmlLabels: false },
      themeVariables: {
        fontFamily: getComputedStyle(document.body).getPropertyValue("--font-body").trim(), fontSize: "13px",
        primaryColor: c.ground, primaryTextColor: c.body, primaryBorderColor: c.edge, lineColor: c.muted,
        clusterBkg: c.ground, clusterBorder: c.edge, titleColor: c.muted,
      },
    });
  }
  setupMermaid();

  let seq = 0, drawing = 0;
  // data-drawing on the root counts the calls under way, so "0" is the page's word that the graph
  // on show has settled, drawn or not; something that has to see the drawing waits on it.
  async function renderGraphs() {
    document.documentElement.dataset.drawing = ++drawing;
    try { await drawGraphs(); } finally { document.documentElement.dataset.drawing = --drawing; }
  }
  async function drawGraphs() {
    // mermaid.render (string -> svg), never mermaid.run: run's in-DOM processing
    // contaminates across the page's many diagrams, render is hermetic per call.
    // Only the graph on show renders; the others wait for their turn.
    // What is drawn already, or restored from the svg cache, is left as it is; the composed graph
    // with every tree hidden has no source, and its note shows instead.
    const undrawn = () => [...document.querySelectorAll(".g:not([hidden]) .mermaid")]
      .filter((el) => !el.querySelector("svg") && el.textContent.trim());
    const drawn = !undrawn().length || await drawable();
    // asked again after the wait, which can outlast the cursor's stay on the graph that started it
    unloaded.hidden = drawn || !undrawn().length;
    for (const el of drawn ? undrawn() : []) {
      if (el.querySelector("svg")) continue;  // drawn by a call that started before this one
      el.dataset.src = el.textContent;
      const done = await drawOf("m" + Date.now() + "_" + seq++, el.dataset.src);
      // a failed graph is left undrawn, so the next call tries it again
      if (!done) { el.dataset.failed = ""; continue; }
      delete el.dataset.failed;
      el.innerHTML = done.svg;
      nodeHover(el);
    }
    undrawable.hidden = !document.querySelector(".g:not([hidden]) .mermaid[data-failed]");
    markNode();
    paintFull();
  }

  // Every node carries its full title as a native tooltip.
  function nodeHover(root) {
    for (const n of root.querySelectorAll("g.node")) {
      const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
      // each wrapped row is its own tspan with no space at the boundary, so join the rows
      const rows = [...n.querySelectorAll(".text-outer-tspan")].map((r) => r.textContent.trim());
      t.textContent = (rows.length ? rows.join(" ") : n.textContent).replace(/\s+/g, " ").trim();
      n.prepend(t);
    }
  }
  for (const el of document.querySelectorAll(".mermaid")) if (el.querySelector("svg")) nodeHover(el);

  // ---- state: hidden trees, the cursor row, the graph mode ----
  const { saved, off, cache } = window.boardState;
  const rowsEl = document.getElementById("rows"), side = document.getElementById("side");
  const search = document.getElementById("search");
  let mode = saved?.mode ?? "tree";
  let cur = saved?.cur ? document.getElementById(saved.cur) : null;
  const inField = (e) => e.target.closest("input, textarea, [contenteditable]");
  const visible = (el) => el.checkVisibility();  // false inside a closed group too, where offsetParent still holds
  const rows = () => [...rowsEl.querySelectorAll(".ticket")].filter(visible);
  const groups = () => [...rowsEl.querySelectorAll("details.grp")].filter(visible);

  function applyFilters() {
    const q = search.value.trim().toLowerCase();
    for (const t of rowsEl.querySelectorAll(".ticket")) {
      t.classList.toggle("off", off.has(t.dataset.tree));
      t.classList.toggle("miss", !!q && !t.dataset.search.includes(q));
    }
    for (const g of rowsEl.querySelectorAll("details.grp[data-state]")) {
      const n = g.querySelectorAll(":scope > .tickets > .ticket:not(.off):not(.miss)").length;
      g.querySelector(".n").textContent = n;
      g.classList.toggle("empty", n === 0);
    }
    for (const c of rowsEl.querySelectorAll(".qgroup")) recount(c);
    for (const b of document.querySelectorAll(".treechip")) b.classList.toggle("off", off.has(b.dataset.tree));
    localStorage.setItem("board-off:" + document.title, JSON.stringify([...off]));
    if (cur && (cur.classList.contains("off") || cur.classList.contains("miss"))) setCur(null);  // a hidden tree takes its row, and its graph, with it
    showGraph();
  }

  // The needs-me group's copy button, worded as group_copy words it for the rows a filter leaves on
  // show, and gone while none of them asks a question.
  function recount(c) {
    const asking = [...c.closest("details.grp").querySelectorAll(":scope > .tickets > .ticket[data-asked]:not(.off):not(.miss)")];
    const n = asking.reduce((sum, t) => sum + Number(t.dataset.asks), 0), text = asking.map((t) => t.dataset.asked).join("\n\n");
    const counted = n + " question" + (n === 1 ? "" : "s");
    const shows = text.length <= ${copycap} ? text : text.slice(0, ${copycap}).trimEnd() + "…";
    Object.assign(c.dataset, { copy: text, copied: counted, tip: c.dataset.tip.split("\n\n")[0] + "\n\n" + shows });
    c.textContent = "copy all " + counted;
    c.hidden = !n;
  }

  // The whole tracker's graph is composed here from its parts, so a hidden tree drops out of it
  // with its edges, and a node left without an edge goes with them. One composition per set of
  // hidden trees is rendered and kept.
  function composeAll() {
    const g = side.querySelector('.g[data-tree="*"]'), pre = g.querySelector(".mermaid");
    if (!pre) return;
    const key = "g:*:" + [...off].sort().join(",");
    if (pre.dataset.key === key) return;
    const parts = JSON.parse(g.querySelector(".parts").textContent);
    const on = (f) => !off.has(f);
    const edges = parts.edges.filter((e) => on(e.a) && on(e.b));
    const keep = new Set(edges.flatMap((e) => [e.from, e.to]));
    const lines = ["flowchart LR"];
    for (const f of parts.trees) {
      const nodes = f.nodes.filter((n) => keep.has(n.id));
      if (!on(f.name) || !nodes.length) continue;
      lines.push('  subgraph S_b_' + f.name.replace(/[^a-zA-Z0-9]/g, "_") + '["' + f.name + '"]');
      for (const n of nodes) lines.push(...n.lines);
      lines.push("  end");
    }
    lines.push(...edges.map((e) => e.line));
    pre.dataset.key = key;
    pre.textContent = edges.length ? lines.join("\n") : "";
    delete pre.dataset.src;
    pre.hidden = !edges.length;
    g.querySelector(".gnote").hidden = !!edges.length;
    const hit = cache[key + "@" + document.documentElement.dataset.theme];
    if (hit && hit.src === pre.textContent) { pre.dataset.src = hit.src; pre.innerHTML = hit.svg; nodeHover(pre); }
  }

  // The graph panel shows one pre-rendered graph at a time: the cursor row's tree, or the whole
  // tracker. Switching shows another element and marks another node; nothing re-renders, so moving
  // between rows of one tree never flickers.
  function showGraph() {
    const tree = cur?.dataset.tree ?? "";
    const key = mode === "all" ? "*" : tree;
    for (const g of side.querySelectorAll(".g")) g.hidden = g.dataset.tree !== key;
    if (key === "*") composeAll();
    document.getElementById("gname").textContent = mode === "all" ? "whole tracker" : (tree || "");
    for (const b of document.querySelectorAll("[data-gmode]")) b.classList.toggle("on", b.dataset.gmode === mode);
    renderGraphs();
  }
  function setMode(m) { mode = m; showGraph(); }

  // the cursor row's node in the graph on show, which carries the namespace that graph was built
  // with: f for one tree's own, b for the whole tracker composed from its parts
  function curNode() {
    if (!cur?.dataset.slug) return "";
    const composed = side.querySelector(".g:not([hidden])")?.dataset.tree === "*";
    return "T_" + (composed ? "b" : "f") + "_" + cur.dataset.slug.replace(/[^a-zA-Z0-9]/g, "_");
  }
  function markNode() { markCur(side, curNode()); }

  // ---- the graph at full size: over the board, or in a window of its own ----
  // The preview is one graph given a column's width; both full size views are the same graph given
  // its own, drawn again from the preview's source so that a node keeps the id and the "#t-..."
  // link the board matches a row by. A drawing is kept per source and scheme, so opening and
  // closing costs one render of each graph rather than one per opening.
  const full = document.getElementById("gfull");
  const fullCache = {};
  let gwin = null;  // the window of its own, while one is open
  let fullKey = null, viewSeq = 0;

  // what the preview is showing, as the two full size views need it
  function shownGraph() {
    const g = side.querySelector(".g:not([hidden])"), pre = g?.querySelector(".mermaid");
    return {
      src: (pre?.dataset.src ?? pre?.textContent ?? "").trim(),
      note: g?.querySelector(".gnote:not([hidden])")?.textContent ?? "",
      name: document.getElementById("gname").textContent, mode, cur: curNode(),
      theme: document.documentElement.dataset.theme,
    };
  }

  async function svgFor(src) {
    const key = src + "@" + document.documentElement.dataset.theme;
    // a failure is kept too: the window of its own asks every second, and only a reload can mend it
    if (!(key in fullCache)) {
      const done = await drawOf("gf" + Date.now() + "_" + seq++, src);
      if (!done) return fullCache[key] = "";
      const box = document.createElement("div");
      box.innerHTML = done.svg;
      nodeHover(box);  // the titles are markup, so they travel to the window of its own with it
      // mermaid sizes its drawing to whatever box it is given (width="100%", capped at the size it
      // drew); full size is that size, which is the one its viewBox counts in.
      const el = box.querySelector("svg"), [, , w, h] = el.getAttribute("viewBox").split(/[\s,]+/);
      el.setAttribute("width", w);
      el.setAttribute("height", h);
      fullCache[key] = box.innerHTML;
    }
    return fullCache[key];
  }

  // The whole of what a full size view shows, drawing included, so the window of its own is sent a
  // picture rather than a source it has no mermaid to draw.
  async function viewOf(g) {
    const draw = g.src && await drawable(), svg = draw ? await svgFor(g.src) : "";
    const note = !g.src ? g.note : !draw ? unloaded.textContent : !svg ? undrawable.textContent : g.note;
    return {
      key: [g.name, g.mode, g.theme, g.src, note].join("|"), name: g.name, mode: g.mode,
      theme: g.theme, note, cur: g.cur, svg,
    };
  }

  // Paint whichever full size views are open. The sequence number is what keeps a slow drawing
  // from landing after a faster one started later: mermaid resolves in whatever order it finishes.
  async function paintFull() {
    if (!full.classList.contains("open") && !gwin) return;
    const me = ++viewSeq;
    const view = await viewOf(shownGraph());
    if (me !== viewSeq) return;
    if (full.classList.contains("open")) fullKey = paintView(full, view, fullKey);
    sendView(view);
  }

  function openFull(on) {
    full.classList.toggle("open", on);
    if (on) paintFull();
  }

  attach(full.querySelector(".gfbody"), (href) => { openFull(false); openTarget(href); });

  // ---- the window of its own ----
  // It talks to the board by message rather than by reaching into it. A board opened as a file has
  // an opaque origin, and a reload mints another one: from the reload on, the window's
  // `opener.<anything>` throws and the board's own handle on the window is gone. A message crosses
  // either way regardless, so the window says hello on a timer and the board answers whoever asked,
  // which is how the two find each other again after every re-render.
  function sendView(view) {
    try {
      if (gwin && !gwin.closed) gwin.postMessage({ graph: "view", view }, "*");
    } catch { gwin = null; }
  }

  addEventListener("message", async (e) => {
    // the only things a message moves are the board's own cursor and its graph mode, so an opaque
    // origin nobody can check costs nothing
    const said = e.data;
    if (said?.graph === "hello") {
      gwin = e.source;
      const view = await viewOf(shownGraph());
      e.source.postMessage(view.key === said.key ? { graph: "alive" } : { graph: "view", view }, "*");
    } else if (said?.graph === "goto") {
      openTarget(said.href);
    } else if (said?.graph === "mode") {
      setMode(said.mode);
    }
  });

  function openWindow() {
    if (gwin && !gwin.closed) { gwin.focus(); return; }
    const win = open("", "board-graph", "popup,width=980,height=800");
    if (!win) { say("the browser blocked the graph window"); return; }
    // the fonts are linked rather than in the stylesheet, and the window renders the same labels
    const head = [...document.querySelectorAll('link[rel="stylesheet"], link[rel="preconnect"]')]
      .map((l) => l.outerHTML).join("")
      + "<style>" + [...document.querySelectorAll("style")].map((s) => s.textContent).join("\n") + "</style>";
    try {
      win.document.write(
        '<!doctype html><html data-theme="' + document.documentElement.dataset.theme + '">' +
        '<head><meta charset="utf-8"><title>' + document.querySelector(".top .name span").textContent +
        " dependencies</title>" + head + '</head><body class="gwin">' + ${graphwin} +
        "<script>" + WINDOW_JS + "<\/script></body></html>"
      );
      win.document.close();
    } catch {
      win.focus();  // a window this page did not open: the board reloaded under one already running
    }
    gwin = win;
  }

  const WINDOW_JS = `
    ${viewjs}
    let last = null, heard = Date.now();
    const body = document.querySelector(".gfbody");
    attach(body, (href) => opener.postMessage({ graph: "goto", href }, "*"));
    for (const b of document.querySelectorAll("[data-gmode]"))
      b.addEventListener("click", () => opener.postMessage({ graph: "mode", mode: b.dataset.gmode }, "*"));
    addEventListener("message", (e) => {
      heard = Date.now();
      if (e.data?.graph !== "view") return;
      document.documentElement.dataset.theme = e.data.view.theme;
      last = paintView(document.body, e.data.view, last);
    });
    // the board answers this, so silence past a few rounds of it is a board that has gone away
    setInterval(() => {
      try { opener.postMessage({ graph: "hello", key: last }, "*"); } catch { }
      document.documentElement.dataset.orphan = Date.now() - heard > 3000 ? "1" : "";
    }, 1000);
  `;

  document.getElementById("gopen").addEventListener("click", () => openFull(true));
  document.getElementById("gclose").addEventListener("click", () => openFull(false));
  document.getElementById("gwinopen").addEventListener("click", openWindow);
  // from inside the overlay, the window is where the graph is going, so the board comes back with it
  document.getElementById("gwinfull").addEventListener("click", () => { openFull(false); openWindow(); });
  full.addEventListener("click", (e) => { if (e.target === full) openFull(false); });
  // the preview is the way in to the full size view; a node in it still goes to its row
  document.getElementById("gbody").addEventListener("click", (e) => { if (!hrefOf(e.target.closest("a"))) openFull(true); });

  function setCur(el, scroll = true) {
    cur?.classList.remove("kcur");
    cur = el ?? null;
    if (cur) { cur.classList.add("kcur"); if (scroll) cur.scrollIntoView({ block: "nearest" }); }
    showGraph();
  }
  function moveCur(delta) {
    const all = [...rowsEl.querySelectorAll(".ticket")], list = all.filter(visible);
    if (!list.length) return;
    let i = list.indexOf(cur);
    if (i < 0 && cur) {
      // the cursor row is folded or filtered away: continue from its place in the page
      const at = all.indexOf(cur);
      i = delta > 0 ? list.findIndex((r) => all.indexOf(r) > at) : list.findLastIndex((r) => all.indexOf(r) < at);
      if (i < 0) i = delta > 0 ? list.length - 1 : 0;
      setCur(list[i]);
      return;
    }
    setCur(list[i < 0 ? (delta > 0 ? 0 : list.length - 1) : Math.min(Math.max(i + delta, 0), list.length - 1)]);
  }
  function jumpGroup(delta) {
    const gs = groups();
    if (!gs.length) return;
    // the group holding the viewport top: the last one at or above where a jump to it would land
    const margin = parseFloat(getComputedStyle(gs[0]).scrollMarginTop) || 0;
    const i = gs.findLastIndex((g) => g.offsetTop <= scrollY + margin + 2);
    gs[Math.min(Math.max(i + delta, 0), gs.length - 1)].scrollIntoView({ block: "start" });
  }

  document.getElementById("treenav").addEventListener("click", (e) => {
    const b = e.target.closest(".treechip"); if (!b) return;
    off.has(b.dataset.tree) ? off.delete(b.dataset.tree) : off.add(b.dataset.tree);
    applyFilters();
  });
  for (const b of document.querySelectorAll("[data-gmode]")) b.addEventListener("click", () => setMode(b.dataset.gmode));
  document.getElementById("sidefold").addEventListener("click", () => side.classList.toggle("folded"));
  search.addEventListener("input", applyFilters);
  // a click on a row's summary moves the cursor there, so the graph follows the mouse too;
  // one on a copy button copies what that button carries, and one on the row's number its path,
  // instead of folding the row or the group
  rowsEl.addEventListener("click", (e) => {
    const copier = e.target.closest("[data-copy]");
    if (copier) { e.preventDefault(); copy(copier.dataset.copy, copier.dataset.copied); return; }
    const t = e.target.closest(".ticket");
    if (!t || !e.target.closest("summary")) return;
    if (e.target.closest(".ticket > summary > .slug")) { e.preventDefault(); copyPath(t); }
    setCur(t, false);
  });

  const toast = document.getElementById("toast");
  let toastTimer = null;
  // data-said counts the toasts shown, so a toast can be told from the one before it with the same words
  function say(words) {
    toast.textContent = words;
    toast.dataset.said = +(toast.dataset.said ?? 0) + 1;
    toast.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("on"), 1500);
  }
  function copy(text, said) {
    if (!text) return;
    // navigator.clipboard is absent outside a secure context
    (navigator.clipboard?.writeText(text) ?? Promise.reject()).then(() => say("copied " + said), () => say("could not copy " + said));
  }
  function copyPath(t) {
    copy(t?.dataset.path, t?.dataset.path);
  }

  const help = document.getElementById("help");
  document.getElementById("helpbtn").addEventListener("click", () => help.classList.toggle("open"));
  help.addEventListener("click", () => help.classList.remove("open"));

  // The scheme the switch lands on is kept, and outlives a re-render; ?theme= overrides it.
  function switchScheme() {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === "night" ? "day" : "night";
    localStorage.setItem("board-theme", root.dataset.theme);
    setupMermaid();
    // a rendered element holds the SVG and its source only in dataset.src; assigning textContent
    // puts the source back and drops the SVG in one step, so the graph returns in the new palette
    for (const el of document.querySelectorAll(".mermaid")) if (el.dataset.src) el.textContent = el.dataset.src;
    renderGraphs();
  }
  document.getElementById("scheme").addEventListener("click", switchScheme);

  // The keys are diffview's where the two pages have the same move (j/k, J/K, gg/G, x/o/Enter,
  // X/O, z, b, /, ?), so one set of habits drives both.
  let gPending = false, gTimer = null;
  document.addEventListener("keydown", (e) => {
    if (inField(e)) {
      if (e.key === "Escape") { search.value = ""; applyFilters(); search.blur(); }
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "g") {
      if (gPending) { clearTimeout(gTimer); gPending = false; scrollTo(0, 0); setCur(rows()[0]); }
      else { gPending = true; gTimer = setTimeout(() => gPending = false, 500); }
      return;
    }
    switch (e.key) {
      case "Escape":
        help.classList.remove("open");
        if (full.classList.contains("open")) openFull(false);
        else if (cur?.open) cur.open = false;
        else setCur(null);
        break;
      case "?": help.classList.toggle("open"); break;
      case "/": e.preventDefault(); search.focus(); search.select(); break;
      case "j": e.preventDefault(); moveCur(1); break;
      case "k": e.preventDefault(); moveCur(-1); break;
      case "J": jumpGroup(1); break;
      case "K": jumpGroup(-1); break;
      case "G": scrollTo(0, document.body.scrollHeight); setCur(rows().at(-1), false); break;
      case "x": case "o": case "Enter": if (cur) { e.preventDefault(); cur.open = !cur.open; } break;
      case "X": case "O": {
        const open = e.key === "O";
        for (const g of rowsEl.querySelectorAll("details.grp[data-state]")) g.open = open;
        break;
      }
      case "z": { const g = cur?.closest("details.grp") ?? groups()[0]; if (g) g.open = !g.open; break; }
      case "d": { const href = cur?.querySelector("a.rp")?.href; if (href) window.open(href, "_blank"); break; }
      case "y": copyPath(cur); break;
      case "a": setMode(mode === "all" ? "tree" : "all"); break;
      case "b": side.classList.toggle("folded"); break;
      case "f": openFull(!full.classList.contains("open")); break;
      case "w": openWindow(); break;
      case "t": switchScheme(); break;
      case "0": off.clear(); applyFilters(); break;
      default:
        if (/^[1-9]$$/.test(e.key)) {  // the doubled dollar is the page template's escape
          const chip = document.querySelectorAll(".treechip")[e.key - 1];
          if (chip) { off.has(chip.dataset.tree) ? off.delete(chip.dataset.tree) : off.add(chip.dataset.tree); applyFilters(); }
        }
    }
  });

  // anchor navigation: open the target ticket, move the cursor to it, flash it.
  // A click on an in-page link (a graph node, a chip) runs it directly, so the
  // flash fires again when the hash is already the target's and hashchange stays silent.
  function openTarget(hash = location.hash) {
    const el = document.getElementById(hash.slice(1));
    if (!el) return;
    for (let d = el; d; d = d.parentElement) if (d.tagName === "DETAILS") d.open = true;
    if (el.classList.contains("ticket")) setCur(el, false);
    el.scrollIntoView({ block: "start" });
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 2000);
  }
  window.addEventListener("hashchange", () => openTarget());
  document.addEventListener("click", (e) => {
    const href = hrefOf(e.target.closest("a"));
    if (href && href.startsWith("#") && href === location.hash) setTimeout(() => openTarget(href));
  });

  function saveState() {
    const state = {
      mode, cur: cur?.id ?? null, folded: side.classList.contains("folded"),
      full: full.classList.contains("open"),
      groups: [...document.querySelectorAll("details.grp[open]")].map((d) => d.id),
      open: [...document.querySelectorAll("details.ticket[open]")].map((d) => d.id).filter(Boolean),
      comments: [...document.querySelectorAll(".ticket details.history[open]")].map((d) => d.closest(".ticket").id),
      scroll: scrollY,
    };
    const svgs = {};
    for (const el of document.querySelectorAll(".mermaid")) {
      if (el.querySelector("svg")) svgs[el.dataset.key + "@" + document.documentElement.dataset.theme] = { src: el.dataset.src, svg: el.innerHTML };
    }
    try {
      sessionStorage.setItem("board-view", JSON.stringify(state));
      sessionStorage.setItem("board-svg", JSON.stringify(svgs));
    } catch {}
    try { window.name = "board:" + JSON.stringify({ saved: state, cache: svgs }); } catch {}
  }

  // opened as a file, the review pages it links cannot save either, which the page says of itself
  const served = location.protocol !== "file:";
  if (!served) document.querySelector("[data-absent=review-page-server]")?.removeAttribute("hidden");
  const gone = document.querySelector("[data-absent=board-server]");
  const stale = document.querySelector("[data-absent=board-stale]");
  let unanswered = 0;

  // Reload only when the renderer wrote different content. fetch() is blocked on
  // file://, but a classic script tag isn't — so poll the sidecar stamp file the
  // renderer writes beside this page.
  function poll() {
    const s = document.createElement("script");
    s.src = document.body.dataset.stampSrc + "?" + Date.now();
    s.onload = () => {
      s.remove();
      unanswered = 0;
      gone.hidden = true;
      stale.textContent = window.__boardStale || "";
      stale.hidden = !window.__boardStale;
      if (window.__boardStamp !== document.body.dataset.stamp) { saveState(); location.reload(); }
      else setTimeout(poll, 5_000);
    };
    // opened as a file, no sidecar: stay current the blunt way. Served, the server is between an exit
    // and the watcher bringing it back on this port, and a reload now would land on an error page;
    // three polls unanswered say so on the page, since a tab left behind shows nothing else.
    s.onerror = () => {
      s.remove();
      if (!served) { saveState(); location.reload(); return; }
      gone.hidden = ++unanswered < 3;
      setTimeout(poll, 5_000);
    };
    document.head.append(s);
  }
  setTimeout(poll, 5_000);

  // the top bar wraps on a narrow window; everything sticky below it follows its measured height
  new ResizeObserver(([e]) => document.documentElement.style.setProperty("--topbar-h", e.target.offsetHeight + "px"))
    .observe(document.querySelector(".top"));
  if (cur) cur.classList.add("kcur");
  applyFilters();
  if (!saved) {
    if (location.hash) openTarget();
    // ?graph opens the overlay on the row the address names, which is what a layout check measures
    if (new URLSearchParams(location.search).has("graph")) openFull(true);
  }
  if (saved?.full) openFull(true);  // the re-render a tracker change triggers puts it back
</script>
</body>
</html>
""")
