"""What a qualified tag names: a tag that reaches a page the user reads outside its own file, named
by the file it lives in. A ticket's `<ticket> D6`, `<ticket> P3`, `<ticket> A21`; a retro entry's
`retro F1`, `retro A3`; a review finding's `review <range> S13`. A bare tag means something only
inside its own file; a page that shows one qualified links it to where it lives, with what it names
as a hover preview, and strikes it through where that no longer exists.

`resolver` reads a ticket's tag from the tracker, `cites` any of the three from the agent repo, and
`link_html` makes every one in a page's HTML a link. The tracker's own citation of a property,
`<ticket>#P3`, is read as the same tag.
"""

import re
import functools
import html
import os
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import tracker

TICKETS = Path(tracker.TICKETS.name)  # in an agent repo: the tracker
RETRO = Path("retro")  # in an agent repo: where its living report is, `report.md` and the page built from it
REVIEWS = Path("reviews")  # in an agent repo: a review's reports, one directory per range, on the machine that ran it
RANGE = r"[0-9a-f]{7,40}\.\.[0-9a-f]{7,40}"  # a review's range, as its reports' directory is named

# A qualified tag in text: `retro` and an entry's id; `review`, the range and a finding's id; or a
# ticket's slug, then a space or `#`, then the tag. Only what the agent repo holds or once held
# makes one a citation (`cites`), so prose that merely looks like it ("step 2 P3") names nothing.
QUALIFIED = re.compile(
    rf"(?<![\w/.-])(?:retro (?P<entry>[FA]\d+)|review (?P<range>{RANGE}) (?P<finding>[A-Z]\d+)"
    rf"|(?P<ticket>{tracker.SLUG.pattern})[ #](?P<tag>[DPA]\d+))\b")


def handle(slug: str, tag: str) -> str:
    """How a page shows a ticket's tag: `<ticket> D6`."""
    return f"{slug} {tag}"


@dataclass(frozen=True)
class Named:
    """What a qualified tag names in its ticket, as the tracker reads it."""

    ticket: str  # the slug
    tag: str  # D6, P3, A21
    kind: Literal["question", "detail", "property", "assumption"]  # a `Dn` is a question or a closing comment's detail entry
    headline: str  # a question's or detail entry's bold headline, a property's or assumption's text
    detail: str = ""  # the rest of a question or detail entry
    ruled: str | None = None  # the date a question was ruled on; None while it is open, and for anything but a question
    answer: str = ""  # a ruled question's answer
    # Whether its ticket is done: a question still open then is a leftover, which the ruling on the
    # build filed as a proposed ticket (the tracker skill), so it waits on nobody.
    done: bool = False

    @property
    def handle(self) -> str:
        return handle(self.ticket, self.tag)

    @property
    def open(self) -> bool:
        """Whether it is a question no `Ruled` line answers yet, on a ticket not done."""
        return self.kind == "question" and self.ruled is None and not self.done

    @property
    def preview(self) -> str:
        """What a hover over its link shows: the text, and a question's ruling where it has one."""
        text = " ".join(part for part in (self.headline, self.detail) if part)
        return f"{self.handle} · {text}" + (f" · Ruled {self.ruled}: {self.answer}" if self.ruled else "")


def resolver(tickets: Path) -> Callable[[str, str], Named | None]:
    """A lookup of `(slug, tag)` in the tracker at `tickets`, each ticket file read once: None where
    the tracker holds no such ticket or the ticket no such tag."""
    read: dict[str, tracker.Ticket | None] = {}

    def ticket(slug: str) -> tracker.Ticket | None:
        if slug not in read:
            path = tickets / f"{slug}.md"
            try:
                read[slug] = tracker.read(path, path.read_text()) if tracker.SLUG.fullmatch(slug) else None
            except OSError:
                read[slug] = None
        return read[slug]

    def resolve(slug: str, tag: str) -> Named | None:
        found = ticket(slug)
        return named(found, tag) if found is not None else None

    return resolve


def named(ticket: tracker.Ticket, tag: str) -> Named | None:
    """What `tag` names in `ticket`, None where it names nothing there."""
    at = dict(ticket=ticket.slug, tag=tag, done=ticket.status == "done")
    for q in ticket.questions:
        if q.tag == tag:
            return Named(**at, kind="question", headline=q.headline, detail=q.detail, ruled=q.ruled, answer=q.answer)
    for p in ticket.properties:
        if p.id == tag:
            return Named(**at, kind="property", headline=p.text)
    for a in ticket.assumptions:
        if f"A{a.id}" == tag:
            return Named(**at, kind="assumption", headline=a.text)
    for section in tracker.section_named(ticket.sections, "comments"):
        for bullet in section.bullets:
            if not bullet.indent and (entry := tracker.ASKED.fullmatch(bullet.head)) and entry.group(1) == tag:
                text = " ".join(entry.group(2).split())
                bold = tracker.HEADLINE.fullmatch(text)
                return Named(**at, kind="detail", headline=bold.group(1) if bold else text, detail=bold.group(2) if bold else "")
    return None


@dataclass(frozen=True)
class Cited:
    """What a qualified tag in text names, as a page links it: the file it lives in, from the agent
    repo's root (absolute where it is in another checkout), the anchor of its place on that file
    where it has one, and its hover preview. `path` is None where it no longer exists: a ticket
    retired, a tag or an entry its file dropped, a review whose reports are not on this machine."""

    preview: str
    path: str | None = None
    anchor: str = ""  # "#f1", with its `#`
    ticket: str = ""  # the slug, for a ticket's tag


def cites(agent: Path) -> Callable[[re.Match], Cited | None]:
    """A lookup of a `QUALIFIED` match in the agent repo at `agent`, each file read once: what it
    names, and None where it never named anything there, which is prose that only looks like a tag
    ("and P3"). A slug is a ticket's while its file is in the tracker or git's history of the
    tracker has it."""
    resolve = resolver(agent / TICKETS)
    report = functools.cache(lambda: retro_entries(agent / RETRO))
    review = functools.cache(lambda span: findings(agent, span))
    retired = functools.cache(lambda: ever_tracked(agent))

    def cite(m: re.Match) -> Cited | None:
        if m["entry"]:
            shown = f"retro {m['entry']}"
            page, anchors, said = report()
            if m["entry"] not in said:
                return Cited(f"{shown} · no longer in the retro's report")
            anchor = f"#{m['entry'].lower()}" if anchors and m["entry"].lower() in anchors else ""
            return Cited(f"{shown} · {said[m['entry']]}", page, anchor)
        if m["range"]:
            shown = f"review {m['range']} {m['finding']}"
            found = review(m["range"]).get(m["finding"])
            if found is None:
                return Cited(f"{shown} · not in a report of that review on this machine")
            return Cited(f"{shown} · {found[1]}", found[0])
        named, shown = resolve(m["ticket"], m["tag"]), handle(m["ticket"], m["tag"])
        if named is not None:
            return Cited(named.preview, str(TICKETS / f"{m['ticket']}.md"), ticket=m["ticket"])
        if (agent / TICKETS / f"{m['ticket']}.md").is_file():
            return Cited(f"{shown} · no longer in its ticket", ticket=m["ticket"])
        if m["ticket"] in retired():
            return Cited(f"{shown} · its ticket is no longer in the tracker", ticket=m["ticket"])
        return None

    return cite


def hrefs(agent: Path, page: Path) -> Callable[[Cited], str]:
    """Where the page at `page` links what `cites(agent)` found: relative, so it opens wherever the
    page is opened, and within the page where it names a place on the page itself."""

    def href(c: Cited) -> str:
        target = (agent / c.path).resolve()
        if target == page.resolve():
            return c.anchor or "#"
        return urllib.parse.quote(os.path.relpath(target, page.parent.resolve())) + c.anchor

    return href


# A retro entry where the report states it: a finding's or candidate's heading, a Dismissed line.
ENTRY = re.compile(r"### ([FA]\d+) (.+)")
DISMISSED = re.compile(r"- \*\*([FA]\d+)\*\*[,:]?\s*(.+)")


def retro_entries(retro: Path) -> tuple[str | None, set[str] | None, dict[str, str]]:
    """The retro's page, from the agent repo's root (the report itself where no page was built), the
    ids its elements carry (None where it is the report), and what each entry says, by id."""
    try:
        lines = (retro / "report.md").read_text().splitlines()
    except OSError:
        return None, None, {}
    said, section = {}, ""
    for line in lines:
        section = line[3:].strip().lower() if line.startswith("## ") else section
        if m := ENTRY.fullmatch(line) or (section == "dismissed" and DISMISSED.fullmatch(line)):
            said.setdefault(m.group(1), m.group(2).strip() if m.re is ENTRY else f"dismissed: {m.group(2).strip()}")
    try:
        page = (retro / "report.html").read_text()
    except OSError:
        return str(RETRO / "report.md"), None, said
    return str(RETRO / "report.html"), set(re.findall(r'\bid="([fa]\d+)"', page)), said


# A review finding's heading in its axis's report: `### S13 <the claim>`.
FINDING = re.compile(r"#{2,4} ([A-Z]\d+)\b[.:]?\s*(.*)")


def findings(agent: Path, span: str) -> dict[str, tuple[str, str]]:
    """Every finding in the reports of the review of `span`, by id: its report, from the agent
    repo's root, and its claim. A review writes its reports in the checkout it ran in, so they are
    looked for in the agent repo of each checkout of the project: a worker's worktree holds them
    until it is removed. Empty where no checkout on this machine holds a report of that range."""
    found: dict[str, tuple[str, str]] = {}
    for checkout in [agent, *(Path(c) / agent.name for c in checkouts(agent.parent))]:
        for report in sorted((checkout / REVIEWS / span).glob("*.md")):
            for line in report.read_text().splitlines():
                if m := FINDING.fullmatch(line):
                    found.setdefault(m.group(1), (str(report.relative_to(agent) if checkout == agent else report), m.group(2)))
    return found


def checkouts(project: Path) -> list[str]:
    """Every work tree of the project's repo; none where `project` is in no repo."""
    done = tracker.tried(project, "worktree", "list", "--porcelain")
    return [line[len("worktree "):] for line in done.stdout.splitlines() if line.startswith("worktree ")] if done.returncode == 0 else []


def ever_tracked(agent: Path) -> set[str]:
    """Every slug git's history of the tracker ever added a file for, retired tickets among them;
    none where the agent repo has no history, whose tracker then never retired a ticket."""
    done = tracker.tried(agent, "log", "--format=", "--name-only", "--diff-filter=A", "--", str(TICKETS))
    return {Path(name).stem for name in done.stdout.split()} if done.returncode == 0 else set()


# What `link_html` reads as one piece and never looks inside, since none of it is the page's prose.
OPAQUE = r"<!--.*?-->|<!\w[^>]*>|<(?:script|style|textarea|title)\b.*?</(?:script|style|textarea|title)\s*>"
PIECE = re.compile(rf"{OPAQUE}|<[^>]*>", re.S | re.I)
TAG = re.compile(r"<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>", re.S)
# Elements whose text stays as it is: a link already, a figure, a code block, a button.
KEEP = {"a", "svg", "pre", "button"}
TAG_AFTER = r"[ #][A-Z]\d+\b"  # a tag written after its slug or id where that alone is code: `` `<ticket>` D6 ``
CODE = re.compile(rf"([^<]*)</code>({TAG_AFTER})?")  # read on from a `<code>`: its text, and a tag after it


def link_html(page: str, cite: Callable[[re.Match], Cited | None], href: Callable[[Cited], str]) -> str:
    """`page` with every qualified tag in its prose made a link to what it names, its preview as the
    link's hover words, or struck through where that no longer exists, saying why on hover. A tag
    may be code (`` `<ticket> D6` ``), or its slug alone may (`` `<ticket>` D6 ``). `href` is where
    the page links what `cite` found (`hrefs`); a link within the page stays in its tab."""

    def wrapped(found: Cited, inner: str) -> str:
        preview = html.escape(found.preview)
        if found.path is None:
            return f'<s class="qualified gone" title="{preview}">{inner}</s>'
        to = href(found)
        away = "" if to.startswith("#") else ' target="_blank" rel="noopener"'
        return f'<a class="qualified" href="{html.escape(to)}"{away} title="{preview}">{inner}</a>'

    def linked(text: str) -> str:
        return QUALIFIED.sub(lambda m: wrapped(found, m.group()) if (found := cite(m)) else m.group(), text)

    out: list[str] = []
    open_: list[str] = []  # each element open where the page has got to
    at = 0
    while (m := PIECE.search(page, at)) is not None:
        kept = not KEEP.isdisjoint(open_)
        out.append(page[at:m.start()] if kept else linked(page[at:m.start()]))
        piece, at = m.group(), m.end()
        tag = TAG.fullmatch(piece)
        if tag is None or tag[4]:  # a piece read whole, or an element closed where it opens
            out.append(piece)
            continue
        name = tag[2].lower()
        if tag[1]:  # an end tag closes its element and whatever was left open inside it
            if name in open_:
                while open_.pop() != name:
                    pass
            out.append(piece)
            continue
        if name == "code" and not kept and (code := CODE.match(page, at)):
            for text, end in ((code[1] + (code[2] or ""), code.end()), (code[1], code.end(1) + len("</code>"))):
                if (q := QUALIFIED.fullmatch(html.unescape(text))) and (found := cite(q)):
                    out.append(wrapped(found, piece + page[at:end]))
                    at = end
                    break
            else:
                open_.append(name)
                out.append(piece)
            continue
        open_.append(name)
        out.append(piece)
    out.append(page[at:] if not KEEP.isdisjoint(open_) else linked(page[at:]))
    return "".join(out)
