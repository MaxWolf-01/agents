#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml"]
# ///
"""Every mechanical operation on a tracker's ticket files, read and write.

A ticket is `agent/tickets/<slug>.md`, flat, with an optional `parent: <slug>`; the slug is its id.
The tracker is the nearest `agent/tickets` above the working directory, so a worktree or a clone
inside a workspace repo both work. The ticket's body stays prose an agent writes in the file, and
`check` is what holds it to the format: it runs over the staged files from the commit hook, and
every read below refuses the same way, naming the file and the line.

Examples:

    tracker check                        # the staged ticket files: what the commit hook runs
    tracker check agent/tickets/one-flow.md
    tracker get map-columns status
    tracker data | jq -r '.tickets[] | select(.status == "open") | .slug'
    tracker context map-columns          # the ticket's body, then every ancestor's
    tracker frontier
    tracker new map-columns --parent csv-import --priority 2 --size M
    tracker set map-columns status=claimed
    tracker rule map-columns D3 "keep it in the fast suite"
    tracker retire csv-import
    tracker hook                         # install the pre-commit hook that runs `check`
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Annotated, Iterable, Literal, Sequence, get_args

import tyro
import yaml
from tyro.extras import SubcommandApp

Status = Literal["proposed", "open", "claimed", "review", "done"]
Size = Literal["XS", "S", "M", "L", "XL"]
Priority = Literal[1, 2, 3, 4, 5]
STATUSES, SIZES, PRIORITIES = get_args(Status), get_args(Size), get_args(Priority)
FIELDS = ("status", "parent", "blocked-by", "needs-user", "priority", "size", "diff", "gh")
LIST_FIELDS = ("blocked-by", "diff", "gh")

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
GH_REF = re.compile(r"[\w.-]+/[\w.-]+#\d+")
RANGE = re.compile(r"[0-9a-f]{7,40}\.\.[0-9a-f]{7,40}")

TICKETS = Path("agent") / "tickets"
LOGS = "logs"  # under the user's home: where an untracked file goes when it leaves the tree


# ---- what a ticket file holds ----------------------------------------------


@dataclass(frozen=True)
class Refusal:
    """One thing a ticket file says that no reader can read, addressed the way an editor jumps to it."""

    path: Path
    line: int
    what: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.what}"


@dataclass
class Bullet:
    """One bullet of a ticket file, read whole: `head` carries the lines the writer wrapped it onto,
    joined, since a reader that took the first line alone would drop the rest."""

    line: int
    indent: int
    head: str
    last: int  # the last line of the item, the lines nested under it included
    under: list["Bullet"] = field(default_factory=list)


@dataclass(frozen=True)
class Section:
    """One `## ` section: where its heading sits, its text, and the bullets under it."""

    heading: str
    line: int
    text: str
    bullets: list[Bullet]


@dataclass(frozen=True)
class Question:
    """One `- [Dn] **headline** detail` item under `## Questions`: a call only the user can make."""

    tag: str
    headline: str
    detail: str
    ruled: str | None
    answer: str
    line: int


@dataclass(frozen=True)
class Assumption:
    """One ``- A<n> `path:line`: text`` bullet: a call the worker made alone, anchored where it landed."""

    id: int
    path: str
    line: int | None
    text: str
    at: int


@dataclass(frozen=True)
class Property:
    """One `- P<n> …` bullet under `## Properties`: what holds for this ticket and its descendants."""

    id: str
    text: str
    line: int


@dataclass(frozen=True)
class Criterion:
    """One `- [ ]` item under `## Acceptance criteria`, and the properties it cites."""

    met: bool
    text: str
    cites: list[str]
    line: int


@dataclass(frozen=True)
class Ticket:
    """A ticket file as every reader gets it: its frontmatter, its body, and the constructs in the
    body that a machine reads. `refusals` is what no reader could read, in file order."""

    slug: str
    path: Path
    meta: dict
    at: dict[str, int]  # the line each frontmatter key sits on
    title: str | None
    brief: str
    body: str
    sections: list[Section]
    questions: list[Question]
    assumptions: list[Assumption]
    resolved: list[str]
    properties: list[Property]
    criteria: list[Criterion]
    cites: list[tuple[str, int]]  # every `<slug>#P<n>` the body carries, with its line
    refusals: list[Refusal]

    @property
    def status(self) -> str:
        return str(self.meta.get("status", ""))

    @property
    def parent(self) -> str | None:
        parent = self.meta.get("parent")
        return str(parent) if parent else None

    @property
    def blocked_by(self) -> list[str]:
        return [str(ref) for ref in self.meta.get("blocked-by") or []]

    @property
    def needs_user(self) -> bool:
        return bool(self.meta.get("needs-user"))


FENCED = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
BULLET = re.compile(r"^(\s*)-\s+(\S.*)$")
HEADING = re.compile(r"^##\s+(.+?)\s*$")
TITLE = re.compile(r"^#\s+(.+?)\s*$")
ASKED = re.compile(r"\[(D\d+)\]\s*(.*)", re.DOTALL)
HEADLINE = re.compile(r"\*\*(.+?)\*\*\s*(.*)", re.DOTALL)
RULED = re.compile(r"Ruled\s+(\d{4}-\d\d-\d\d)\s*:\s*(.*)", re.DOTALL)
SAYS_RULED = re.compile(r"^Ruled\b")
ASSUMED = re.compile(r"A(\d+)\s+`([^:`]+)(?::(\d+))?`:\s*(\S.*)", re.DOTALL)
SAYS_ASSUMED = re.compile(r"^A\d+\b")
ADDRESSED = re.compile(r"^Addressed:\s*(.*)$")
SAYS_ADDRESSED = re.compile(r"^\s*Addressed\b")
PROPERTY = re.compile(r"P(\d+)\s+(\S.*)", re.DOTALL)
CRITERION = re.compile(r"\[([ xX])\]\s*(.*)", re.DOTALL)
CITED = re.compile(r"(?<![\w-])([a-z0-9][a-z0-9-]*)?#P(\d+)\b")
OLD_CLAIM = re.compile(r"^(?:\[[ xX]\]\s*)?\*{0,2}Property\b[ ]*(?:P\d+|,)")


def unfenced(text: str) -> str:
    """The text with its fenced code blanked and every offset kept: a bullet inside a fence is a
    shape the ticket quotes, not one of its own."""
    return FENCED.sub(lambda fence: re.sub(r"[^\n]", " ", fence.group()), text)


def bullets(lines: Sequence[tuple[int, str]]) -> list[Bullet]:
    """The bullet tree of a run of `(line number, text)`, each bullet read whole: a line indented
    under a bullet, and a line lazily continuing one (CommonMark), joins the bullet above it."""
    top: list[Bullet] = []
    stack: list[Bullet] = []
    blank = True
    for number, raw in lines:
        if marker := BULLET.match(raw):
            indent = len(marker.group(1))
            while stack and stack[-1].indent >= indent:
                stack.pop()
            opened = Bullet(line=number, indent=indent, head=marker.group(2).rstrip(), last=number)
            (stack[-1].under if stack else top).append(opened)
            stack.append(opened)
            for holding in stack:
                holding.last = number
            blank = False
            continue
        if not raw.strip():
            blank = True
            continue
        indent = len(raw) - len(raw.lstrip())
        if blank:
            while stack and indent <= stack[-1].indent:
                stack.pop()
        if stack:
            stack[-1].head += " " + raw.strip()
            for holding in stack:
                holding.last = number
        blank = False
    return top


def read(path: Path, text: str) -> Ticket:
    """A ticket file as data, with everything in it no reader could read collected as refusals."""
    refusals: list[Refusal] = []
    meta, at, body_line, body = frontmatter(path, text, refusals)
    lines = [(body_line + n, line) for n, line in enumerate(unfenced(body).splitlines())]

    title = next((TITLE.match(line).group(1) for _, line in lines if TITLE.match(line)), None)
    if title is None:
        refusals.append(Refusal(path, body_line, "no `# ` heading; the H1 is the ticket's short name, which a board row shows"))
    written = sections(lines)
    if not any(section.heading.lower() == "brief" for section in written):
        refusals.append(Refusal(path, body_line, "no `## Brief` section; the brief is what a row tells the user, reading cold"))

    questions = read_questions(path, written, refusals)
    assumptions = read_assumptions(path, lines, refusals)
    resolved = read_addressed(path, lines, refusals)
    properties = read_properties(path, written, refusals)
    criteria = read_criteria(path, written, refusals)
    cites = read_citations(path, lines, refusals)
    duplicates(path, [(q.tag, q.line) for q in questions] + detail_tags(written), "tag", refusals)
    duplicates(path, [(f"A{a.id}", a.at) for a in assumptions], "assumption", refusals)
    duplicates(path, [(p.id, p.line) for p in properties], "property", refusals)

    return Ticket(
        slug=path.stem, path=path, meta=meta, at=at, title=title,
        brief=brief_of(written), body=body, sections=written, questions=questions,
        assumptions=assumptions, resolved=resolved, properties=properties, criteria=criteria,
        cites=cites, refusals=sorted(refusals, key=lambda r: (r.line, r.what)),
    )


def frontmatter(path: Path, text: str, refusals: list[Refusal]) -> tuple[dict, dict[str, int], int, str]:
    """(the frontmatter, the line each of its keys sits on, the line the body opens on, the body)."""
    match = re.match(r"\A---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not match:
        refusals.append(Refusal(path, 1, "no frontmatter; a ticket opens with `---` and declares status, priority and size"))
        return {}, {}, 1, text
    block = match.group(1)
    try:
        meta = yaml.safe_load(block) or {}
    except yaml.YAMLError as broken:
        refusals.append(Refusal(path, 1, f"frontmatter is not YAML: {' '.join(str(broken).split())}"))
        return {}, {}, 1, match.group(2)
    if not isinstance(meta, dict):
        refusals.append(Refusal(path, 1, "frontmatter is not a mapping of fields"))
        return {}, {}, 1, match.group(2)
    at = {}
    for number, line in enumerate(block.splitlines(), start=2):
        if key := re.match(r"([\w-]+):", line):
            at.setdefault(key.group(1), number)
    return meta, at, block.count("\n") + 4, match.group(2)


def sections(lines: Sequence[tuple[int, str]]) -> list[Section]:
    """The `## ` sections in file order; what stands above the first of them is no section's."""
    found: list[Section] = []
    opened: tuple[str, int, list[tuple[int, str]]] | None = None
    for number, line in lines:
        if heading := HEADING.match(line):
            if opened:
                found.append(shut(opened))
            opened = (heading.group(1), number, [])
        elif opened:
            opened[2].append((number, line))
    if opened:
        found.append(shut(opened))
    return found


def shut(opened: tuple[str, int, list[tuple[int, str]]]) -> Section:
    heading, line, lines = opened
    return Section(heading=heading, line=line, text="\n".join(raw for _, raw in lines).strip("\n"), bullets=bullets(lines))


def section_named(written: Sequence[Section], name: str) -> list[Section]:
    return [section for section in written if section.heading.lower() == name]


def brief_of(written: Sequence[Section]) -> str:
    return " ".join(" ".join(section.text.split()) for section in section_named(written, "brief")).strip()


def read_questions(path: Path, written: Sequence[Section], refusals: list[Refusal]) -> list[Question]:
    """Every question the ticket asks: a top-level bullet, as every reader of one looks for. A
    top-level bullet that is not a question is refused, since a reader takes it for the detail of
    the question above it."""
    found = []
    for section in section_named(written, "questions"):
        asking = False
        for bullet in [bullet for bullet in section.bullets if not bullet.indent]:
            item = ASKED.fullmatch(bullet.head)
            if not item:
                if asking:
                    refusals.append(Refusal(path, bullet.line, "this bullet is read as part of the question above it; a question is `- [Dn] **headline** detail`"))
                continue
            asking = True
            found.append(question(path, bullet, item, refusals))
    return found


def question(path: Path, bullet: Bullet, item: re.Match, refusals: list[Refusal]) -> Question:
    ruling = next((RULED.fullmatch(under.head) for under in bullet.under if RULED.fullmatch(under.head)), None)
    for under in bullet.under:
        if SAYS_RULED.match(under.head) and not RULED.fullmatch(under.head):
            refusals.append(Refusal(path, under.line, "this ruling carries no date, so no reader takes the question as answered; a ruling is `Ruled <date>: the answer`"))
    headline = HEADLINE.fullmatch(item.group(2).strip())
    if not headline:
        refusals.append(Refusal(path, bullet.line, f"{item.group(1)} has no bold headline; a question is `- [Dn] **headline** detail`"))
    return Question(
        tag=item.group(1),
        headline=" ".join((headline.group(1) if headline else item.group(2)).split()),
        detail=" ".join((headline.group(2) if headline else "").split()),
        ruled=ruling.group(1) if ruling else None,
        answer=" ".join(ruling.group(2).split()) if ruling else "",
        line=bullet.line,
    )


def detail_tags(written: Sequence[Section]) -> list[tuple[str, int]]:
    """The `[Dn]` tags the closing comment's detail entries carry: one sequence with the questions'."""
    return [
        (tag.group(1), bullet.line)
        for section in section_named(written, "comments")
        for bullet in section.bullets
        if not bullet.indent and (tag := ASKED.fullmatch(bullet.head))
    ]


def read_assumptions(path: Path, lines: Sequence[tuple[int, str]], refusals: list[Refusal]) -> list[Assumption]:
    """Every assumption bullet, wherever the closing comment puts it, read whole."""
    found = []
    for bullet in flat(bullets(lines)):
        if not SAYS_ASSUMED.match(bullet.head):
            continue
        anchored = ASSUMED.fullmatch(bullet.head)
        if not anchored:
            refusals.append(Refusal(path, bullet.line, "this assumption has no anchor, and the review page would drop it; an assumption is ``- A<n> `path:line`: the call and why``"))
            continue
        found.append(Assumption(
            id=int(anchored.group(1)), path=anchored.group(2),
            line=int(anchored.group(3)) if anchored.group(3) else None,
            text=" ".join(anchored.group(4).split()), at=bullet.line,
        ))
    return found


def flat(tree: Iterable[Bullet]) -> Iterable[Bullet]:
    for bullet in tree:
        yield bullet
        yield from flat(bullet.under)


def read_addressed(path: Path, lines: Sequence[tuple[int, str]], refusals: list[Refusal]) -> list[str]:
    """The review comments a round's closing comment resolves: `Addressed: C1, C4`, at a line's start."""
    found = []
    for number, line in lines:
        if not SAYS_ADDRESSED.match(line):
            continue
        listed = ADDRESSED.match(line)
        if not listed:
            refusals.append(Refusal(path, number, "this line resolves nothing; a round opens `Addressed: C1, C4`, at the start of a line"))
            continue
        found += [name for name in (name.strip() for name in listed.group(1).split(",")) if name]
    return found


def read_properties(path: Path, written: Sequence[Section], refusals: list[Refusal]) -> list[Property]:
    found = []
    for section in section_named(written, "properties"):
        for bullet in section.bullets:
            stated = PROPERTY.fullmatch(bullet.head)
            if not stated:
                refusals.append(Refusal(path, bullet.line, "this property has no id to cite it by; a property is `- P<n> what always or never holds`"))
                continue
            found.append(Property(id=f"P{int(stated.group(1))}", text=" ".join(stated.group(2).split()), line=bullet.line))
    return found


def read_criteria(path: Path, written: Sequence[Section], refusals: list[Refusal]) -> list[Criterion]:
    found = []
    for section in section_named(written, "acceptance criteria"):
        for bullet in section.bullets:
            if OLD_CLAIM.match(bullet.head):
                refusals.append(Refusal(path, bullet.line, "a criterion no longer stamps a property of its own spec; a property is stated once and cited `<slug>#P<n>`, read through the ticket's ancestry"))
                continue
            ticked = CRITERION.fullmatch(bullet.head)
            if not ticked:
                continue
            text = " ".join(ticked.group(2).split())
            found.append(Criterion(met=ticked.group(1) in "xX", text=text, cites=[ref for ref, _ in cited(text)], line=bullet.line))
    return found


def cited(text: str) -> list[tuple[str, int]]:
    """The `<slug>#P<n>` citations one line of prose carries. A bare `#P<n>` continues the slug
    cited before it on the same line, which is how a ticket names two properties of one ticket."""
    found, slug = [], None
    for citation in CITED.finditer(text):
        slug = citation.group(1) or slug
        found.append((f"{slug}#P{int(citation.group(2))}" if slug else f"#P{int(citation.group(2))}", citation.start()))
    return found


def read_citations(path: Path, lines: Sequence[tuple[int, str]], refusals: list[Refusal]) -> list[tuple[str, int]]:
    found = []
    for number, line in lines:
        for ref, _ in cited(line):
            if ref.startswith("#"):
                refusals.append(Refusal(path, number, f"`{ref}` names no ticket; a property is cited `<slug>{ref}`"))
                continue
            found.append((ref, number))
    return found


def duplicates(path: Path, ids: Sequence[tuple[str, int]], what: str, refusals: list[Refusal]) -> None:
    seen: dict[str, int] = {}
    for name, line in ids:
        if name in seen:
            refusals.append(Refusal(path, line, f"{what} {name} is already taken, on line {seen[name]}; an id names one thing for good"))
        else:
            seen[name] = line


# ---- the tracker -----------------------------------------------------------


@dataclass(frozen=True)
class Tracker:
    """Every ticket under one `agent/tickets`, by slug."""

    root: Path
    tickets: dict[str, Ticket]

    def ticket(self, slug: str) -> Ticket:
        if slug not in self.tickets:
            raise Refused([f"no ticket {slug} at {self.root / f'{slug}.md'}"])
        return self.tickets[slug]

    def ancestors(self, slug: str) -> list[Ticket]:
        """The ticket's parent, its parent's parent, and so on: the context it is built in."""
        found, seen = [], {slug}
        parent = self.tickets[slug].parent
        while parent and parent not in seen and parent in self.tickets:
            seen.add(parent)
            found.append(self.tickets[parent])
            parent = self.tickets[parent].parent
        return found

    def children(self, slug: str) -> list[Ticket]:
        return [t for t in self.tickets.values() if t.parent == slug]


class Refused(Exception):
    """What the tracker's rules forbid, said with the rule that forbids it."""

    def __init__(self, said: Sequence[object]) -> None:
        super().__init__("\n".join(str(line) for line in said))


def find_tracker(start: Path) -> Path:
    """The nearest `agent/tickets` at or above `start`."""
    for directory in [start, *start.parents]:
        if (directory / TICKETS).is_dir():
            return directory / TICKETS
    raise Refused([f"no tracker at {start / TICKETS} or above it"])


def tracker_of(root: Path, texts: dict[Path, str] | None = None) -> Tracker:
    """Every ticket file in `root`, with `texts` standing in for what is on disk where it has a
    copy: the commit hook reads the staged text, not the worktree's."""
    said = dict(texts or {})
    paths = sorted(set(root.glob("*.md")) | set(said))
    return Tracker(root=root, tickets={
        path.stem: read(path, said[path] if path in said else path.read_text())
        for path in paths
    })


# ---- the check -------------------------------------------------------------
# Every rule the tracker's format holds a ticket to, each refusal naming the rule. A construct the
# one-ticket model dropped is refused with what replaced it, so a file written to the old shape
# says so rather than reading as a ticket with fields missing.


def holds(ticket: Ticket, tracker: Tracker) -> list[Refusal]:
    """What `ticket` says that no reader can read: its own refusals, its frontmatter, its layout,
    and every reference in it that names no ticket or property."""
    found = list(ticket.refusals)
    found += frontmatter_holds(ticket)
    found += layout_holds(ticket)
    found += references_hold(ticket, tracker)
    return sorted(found, key=lambda r: (str(r.path), r.line, r.what))


def at(ticket: Ticket, key: str) -> int:
    return ticket.at.get(key, 1)


def frontmatter_holds(ticket: Ticket) -> list[Refusal]:
    found, meta = [], ticket.meta
    refuse = lambda key, what: found.append(Refusal(ticket.path, at(ticket, key), what))  # noqa: E731

    for key in meta:
        if key == "type":
            refuse(key, "`type` is dropped: a ticket whose deliverable is an answer is a ticket like any other, and `needs-user` says whether the user is in the loop")
        elif key not in FIELDS:
            refuse(key, f"`{key}` is no ticket field; a ticket declares {', '.join(FIELDS)}")

    status = meta.get("status")
    if status in ("draft", "confirmed"):
        refuse("status", f"`status: {status}` was a spec's; a spec is a top-level ticket now, and a ticket's status is one of {', '.join(STATUSES)}")
    elif status is None:
        refuse("status", f"no `status`; a ticket declares one of {', '.join(STATUSES)}")
    elif status not in STATUSES:
        refuse("status", f"`status: {status}` is no ticket status; a ticket declares one of {', '.join(STATUSES)}")

    for key, allowed in (("priority", PRIORITIES), ("size", SIZES)):
        value = meta.get(key)
        if value is None:
            refuse(key, f"no `{key}`; whoever files a ticket fills its priority and its size (the user's time on it)")
        elif value not in allowed:
            refuse(key, f"`{key}: {value}` is none of {', '.join(str(one) for one in allowed)}")

    if "needs-user" in meta and not isinstance(meta["needs-user"], bool):
        refuse("needs-user", "`needs-user` is true or false: whether the ticket is worked with the user rather than by a worker")

    for key in ("parent", "blocked-by"):
        for ref in ([meta["parent"]] if key == "parent" and meta.get("parent") is not None else meta.get(key) or []):
            if what := unreadable_ref(ref):
                refuse(key, f"`{key}: {ref}` {what}")
    if not isinstance(meta.get("blocked-by") or [], list):
        refuse("blocked-by", "`blocked-by` is a list of slugs: `blocked-by: [one-slug, another-slug]`")
    if meta.get("parent") == ticket.slug:
        refuse("parent", "a ticket is not its own parent ticket")

    for ref in meta.get("diff") or []:
        if not RANGE.fullmatch(str(ref)):
            refuse("diff", f"`diff: {ref}` is no commit range; a range is `<sha>..<sha>`, never a branch name, since a ticket branch is deleted once it lands")
    for ref in meta.get("gh") or []:
        if not GH_REF.fullmatch(str(ref)):
            refuse("gh", f"`gh: {ref}` is no reference; a reference is `owner/repo#number`")
    return found


def unreadable_ref(ref: object) -> str | None:
    """Why a `parent` or `blocked-by` entry names no ticket, or None when it names one."""
    if isinstance(ref, int) or str(ref).isdigit():
        return "is a number; `NN` numbering is dropped, and a reference names the blocking ticket's slug"
    if "/" in str(ref):
        return "is `<feature>/NN`; a feature is a ticket now, and a reference names a slug"
    if not SLUG.fullmatch(str(ref)):
        return "is no slug; a slug is lower case words joined by hyphens"
    return None


def layout_holds(ticket: Ticket) -> list[Refusal]:
    """The tracker is flat, and a ticket's file name is its id."""
    name = ticket.path.name
    if name == "spec.md":
        return [Refusal(ticket.path, 1, "a spec is dropped: it becomes a top-level ticket named for the work, with the tickets sliced from it as its child tickets")]
    if re.fullmatch(r"\d\d-.*\.md", name):
        return [Refusal(ticket.path, 1, f"`{name}` carries a number; `NN` numbering is dropped, and the file is `agent/tickets/<slug>.md`")]
    if not SLUG.fullmatch(ticket.slug):
        return [Refusal(ticket.path, 1, f"`{name}` is no slug; a slug is lower case words joined by hyphens, descriptive enough to know the ticket from")]
    return []


def references_hold(ticket: Ticket, tracker: Tracker) -> list[Refusal]:
    """Every reference in the ticket resolves: its parent, what blocks it, and every property it
    cites through its ancestry."""
    found = []
    for key in ("parent", "blocked-by"):
        for ref in ([ticket.parent] if key == "parent" and ticket.parent else ticket.blocked_by):
            if unreadable_ref(ref) is None and ref not in tracker.tickets:
                found.append(Refusal(ticket.path, at(ticket, key), f"`{key}: {ref}` names no ticket at {tracker.root / f'{ref}.md'}"))
    if ticket.parent in tracker.tickets and ticket.slug in {t.slug for t in tracker.ancestors(ticket.parent)}:
        found.append(Refusal(ticket.path, at(ticket, "parent"), f"`parent: {ticket.parent}` closes a cycle; a ticket's ancestry is a line to a top-level ticket"))
    for ref, line in ticket.cites:
        slug, _, number = ref.partition("#")
        if slug not in tracker.tickets:
            found.append(Refusal(ticket.path, line, f"`{ref}` names no ticket at {tracker.root / f'{slug}.md'}"))
        elif number not in {p.id for p in tracker.tickets[slug].properties}:
            found.append(Refusal(ticket.path, line, f"`{ref}` names no property; {slug} states {', '.join(p.id for p in tracker.tickets[slug].properties) or 'none'}"))
    return found


# ---- git -------------------------------------------------------------------


def git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused([f"git {' '.join(args)} failed in {root}: {done.stderr.strip()}"])
    return done.stdout


def toplevel(start: Path) -> Path:
    done = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused([f"{start} is in no git checkout"])
    return Path(done.stdout.strip())


def staged(root: Path) -> Tracker:
    """The tracker as the commit being made will leave it: the staged text of every ticket file it
    touches, the rest as they stand."""
    top = toplevel(root)
    listed = [top / name for name in git(top, "ls-files", "--", str(root.relative_to(top))).splitlines() if name.endswith(".md")]
    changed = {top / name for name in git(top, "diff", "--cached", "--name-only", "--", str(root.relative_to(top))).splitlines()}
    texts = {}
    for path in listed:
        if path in changed or not path.exists():
            texts[path] = git(top, "show", f":{path.relative_to(top)}")
    return tracker_of(root, texts)


def staged_paths(root: Path) -> list[Path]:
    top = toplevel(root)
    listed = git(top, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "--", str(root.relative_to(top)))
    return [top / name for name in listed.splitlines() if name.endswith(".md")]


# ---- the commands ----------------------------------------------------------

app = SubcommandApp()


@app.command(name="check")
def check(paths: Annotated[tuple[str, ...], tyro.conf.Positional] = ()) -> int:
    """Refuse every ticket file that says something no reader can read, one `file:line: message` per
    finding. With no paths, the staged ticket files, which is what the commit hook runs.

    Args:
        paths: the ticket files to check; they are read as the tracker their directory holds.
    """
    if paths:
        files = [Path(name) for name in paths]
        roots = {path.parent.resolve() for path in files}
        if len(roots) > 1:
            raise Refused(["one tracker per run; these files are in " + ", ".join(sorted(str(one) for one in roots))])
        tracker = tracker_of(roots.pop())
    else:
        tracker = staged(find_tracker(Path.cwd()))
        files = staged_paths(tracker.root)
    found = [refusal for path in files for refusal in holds(tracker.ticket(path.stem), tracker)]
    for refusal in found:
        print(refusal)
    if refused := {refusal.path for refusal in found}:
        print(f"{len(refused)} file{'s' if len(refused) > 1 else ''} refused")
    return 1 if found else 0


@app.command(name="get")
def get(slug: Annotated[str, tyro.conf.Positional], field_name: Annotated[str, tyro.conf.Positional]) -> int:
    """Print one frontmatter field of one ticket, a list field one entry per line. Exit 1 when the
    ticket does not declare it.

    Args:
        slug: the ticket.
        field_name: the field, one of status, parent, blocked-by, needs-user, priority, size, diff, gh.
    """
    ticket = here().ticket(slug)
    if field_name not in ticket.meta:
        raise Refused([f"{slug} declares no `{field_name}`"])
    value = ticket.meta[field_name]
    print("\n".join(str(one) for one in value) if isinstance(value, list) else value)
    return 0


@app.command(name="data")
def data(source: Annotated[str, tyro.conf.Positional] = "") -> int:
    """The tracker as JSON: every ticket with its frontmatter, sections, questions, properties,
    acceptance criteria and assumptions. One ticket alone when given a slug, a path or `-`, which
    reads a ticket file from stdin, as a review page does from a ticket branch.

    JSON schema:

        {"root": "str", "tickets": [{"slug": "str", "path": "str", "status": "str",
          "parent": "str|null", "blocked-by": ["str"], "needs-user": bool, "priority": int,
          "size": "str", "diff": ["str"], "gh": ["str"], "title": "str|null", "brief": "str",
          "sections": [{"heading": "str", "line": int, "text": "str"}],
          "questions": [{"tag": "str", "headline": "str", "detail": "str", "ruled": "str|null",
                         "answer": "str", "line": int}],
          "assumptions": [{"id": int, "path": "str", "line": int|null, "text": "str", "at": int}],
          "resolved": ["str"], "properties": [{"id": "str", "text": "str", "line": int}],
          "criteria": [{"met": bool, "text": "str", "cites": ["str"], "line": int}],
          "children": ["str"], "ancestors": ["str"]}]}

    Args:
        source: a slug, a ticket file, or `-` for one on stdin; the whole tracker when absent.
    """
    if source == "-" or (source and source.endswith(".md")):
        path = Path("-.md") if source == "-" else Path(source)
        ticket = read(path, sys.stdin.read() if source == "-" else path.read_text())
        tracker = tracker_of(path.parent, {path: ticket.body})
        refuse(ticket.refusals)
        print(json.dumps({"root": str(tracker.root), "tickets": [as_data(ticket, tracker)]}, indent=2))
        return 0
    tracker = here()
    tickets = [tracker.ticket(source)] if source else list(tracker.tickets.values())
    refuse([refusal for ticket in tickets for refusal in holds(ticket, tracker)])
    print(json.dumps({"root": str(tracker.root), "tickets": [as_data(ticket, tracker) for ticket in tickets]}, indent=2))
    return 0


def as_data(ticket: Ticket, tracker: Tracker) -> dict:
    return {
        "slug": ticket.slug, "path": str(ticket.path), "status": ticket.status,
        "parent": ticket.parent, "blocked-by": ticket.blocked_by, "needs-user": ticket.needs_user,
        "priority": ticket.meta.get("priority"), "size": ticket.meta.get("size"),
        "diff": [str(one) for one in ticket.meta.get("diff") or []],
        "gh": [str(one) for one in ticket.meta.get("gh") or []],
        "title": ticket.title, "brief": ticket.brief,
        "sections": [{"heading": s.heading, "line": s.line, "text": s.text} for s in ticket.sections],
        "questions": [vars(q) for q in ticket.questions],
        "assumptions": [vars(a) for a in ticket.assumptions],
        "resolved": ticket.resolved,
        "properties": [vars(p) for p in ticket.properties],
        "criteria": [vars(c) for c in ticket.criteria],
        "children": [child.slug for child in tracker.children(ticket.slug)],
        "ancestors": [one.slug for one in tracker.ancestors(ticket.slug)] if ticket.slug in tracker.tickets else [],
    }


@app.command(name="context")
def context(slug: Annotated[str, tyro.conf.Positional]) -> int:
    """The context a ticket is built and reviewed in: its own body, then every ancestor's body,
    nearest first. A ticket whose parent names no ticket is refused, as any dangling reference is.

    Args:
        slug: the ticket.
    """
    tracker = here()
    ticket = tracker.ticket(slug)
    refuse([refusal for one in (ticket, *tracker.ancestors(slug)) for refusal in holds(one, tracker)])
    print(assembled(ticket, tracker))
    return 0


def assembled(ticket: Ticket, tracker: Tracker) -> str:
    """The one assembly every reader of a ticket's context gets: the worker's brief, the reviewer's
    spec. The ticket comes first, since it is what is being built; its ancestors follow in the order
    the work widens."""
    written = [f"## {ticket.slug}\n{ticket.body.strip()}"]
    written += [f"## parent ticket: {one.slug}\n{one.body.strip()}" for one in tracker.ancestors(ticket.slug)]
    return "\n\n".join(written) + "\n"


@app.command(name="frontier")
def frontier() -> int:
    """What can be started right now: the unclaimed, unblocked tickets that are open or proposed and
    do not need the user. Everything else not done follows under `waiting`, with what holds it back.
    """
    tracker = here()
    refuse([refusal for ticket in tracker.tickets.values() for refusal in holds(ticket, tracker)])
    ready, waiting = [], []
    for ticket in sorted(tracker.tickets.values(), key=lambda t: (t.meta.get("priority") or 9, t.slug)):
        if ticket.status == "done":
            continue
        (waiting if held(ticket, tracker) else ready).append(ticket)
    for ticket in ready:
        print(line_of(ticket, tracker, f"parent {ticket.parent}" if ticket.parent else ""))
    if waiting:
        print("waiting")
        for ticket in waiting:
            print(line_of(ticket, tracker, held(ticket, tracker) or ""))
    return 0


def held(ticket: Ticket, tracker: Tracker) -> str:
    """What holds a ticket back from being started now, or "" when nothing does."""
    if ticket.status in ("claimed", "review"):
        return f"{ticket.status}, not the frontier's"
    if ticket.needs_user:
        return "on the user, who is in the loop for it"
    blocking = [ref for ref in ticket.blocked_by if tracker.tickets[ref].status != "done"]
    if blocking:
        return "on " + ", ".join(f"{ref} ({tracker.tickets[ref].status})" for ref in blocking)
    return ""


def line_of(ticket: Ticket, tracker: Tracker, said: str) -> str:
    return f"{ticket.slug:<44}{ticket.status:<10}p{ticket.meta.get('priority')}  {str(ticket.meta.get('size')):<4}{said}".rstrip()


@app.command(name="new")
def new(
    slug: Annotated[str, tyro.conf.Positional],
    priority: Priority,
    size: Size,
    parent: str = "",
    blocked_by: tuple[str, ...] = (),
    status: Literal["proposed", "open"] = "proposed",
    needs_user: bool = False,
) -> int:
    """File a ticket: its frontmatter and the skeleton of its body, which the filing agent writes
    into. Prints the path. Refuses a slug the tracker already holds.

    Args:
        slug: the ticket's id, lower case words joined by hyphens, descriptive enough to know it from.
        priority: how soon it matters to the user, 1 now to 5 someday.
        size: the user's time on it: XS, S, M, L or XL.
        parent: the ticket this one is part of; absent on a top-level ticket.
        blocked_by: the tickets that have to be done first, by slug.
        status: proposed for a ticket the agent files on its own reading, open for one already ruled.
        needs_user: the ticket is worked with the user, so no worker is given it.
    """
    tracker = here()
    path = tracker.root / f"{slug}.md"
    if path.exists():
        raise Refused([f"{path} is already a ticket"])
    meta = {"status": status, "parent": parent, "blocked-by": list(blocked_by),
            "needs-user": needs_user, "priority": priority, "size": size}
    written = "---\n" + "".join(f"{key}: {rendered(value)}\n" for key, value in meta.items() if value not in ("", [], False)) + "---\n"
    written += f"\n# {slug.replace('-', ' ').capitalize()}\n\n## Brief\n\n## Acceptance criteria\n\n## Comments\n"
    filed = read(path, written)
    refuse(holds(filed, replace(tracker, tickets={**tracker.tickets, slug: filed})))
    path.write_text(written)
    print(path)
    return 0


def rendered(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(one) for one in value) + "]"
    return "true" if value is True else "false" if value is False else str(value)


# What a status change follows: where it may come from, and the rule that says so. A ticket moves
# along the tracker's transitions and nowhere else, so the rule is enforced where it is written.
INTO = {
    "claimed": (("open", "proposed", "review"), "a claim is taken from the frontier, a proposal like an open ticket, and a build the user sent back is claimed again"),
    "review": (("claimed",), "review is where a finished build waits for the user's ruling, and a build starts from a claim"),
    "done": (("review",), "done is the accept and nothing less, written once the user has ruled on the review page"),
    "open": (("proposed", "review"), "open is a ticket ruled and not yet built: the ruling on a proposal, or the redo ruling that discards a build and keeps the ticket"),
    "proposed": ((), "proposed is where an agent files a ticket the user has not ruled on, and nothing moves back to it"),
}


@app.command(name="set")
def set_fields(
    slug: Annotated[str, tyro.conf.Positional],
    assignments: Annotated[tuple[str, ...], tyro.conf.Positional],
) -> int:
    """Write frontmatter fields, refusing what the tracker's rules forbid and saying which rule.
    `field=value` sets one, `field+=value` appends to a list field.

    Args:
        slug: the ticket.
        assignments: `status=claimed`, `diff+=4f2a91c..8b3ce07`, `blocked-by=[one, another]`.
    """
    tracker = here()
    ticket = tracker.ticket(slug)
    changes, said = {}, []
    for assignment in assignments:
        key, appended, value = assignment.partition("+=")
        if not appended:
            key, _, value = assignment.partition("=")
        if key not in FIELDS:
            raise Refused([f"`{key}` is no ticket field; a ticket declares {', '.join(FIELDS)}"])
        if appended and key not in LIST_FIELDS:
            raise Refused([f"`{key}` holds one value, not a list; `{key}=...` sets it"])
        if key == "status":
            refuse_transition(ticket, value, tracker)
        changes[key] = listed(ticket, key, value) if appended else value
        said.append(f"{key}: {rendered(ticket.meta[key])} → {changes[key]}" if key in ticket.meta else f"{key}: {changes[key]}")
    written = written_with(ticket.path.read_text(), changes)
    after = read(ticket.path, written)
    refuse([r for r in holds(after, replace(tracker, tickets={**tracker.tickets, slug: after})) if r not in holds(ticket, tracker)])
    ticket.path.write_text(written)
    print(f"{slug}: " + "; ".join(said))
    return 0


def listed(ticket: Ticket, key: str, value: str) -> str:
    return rendered([str(one) for one in ticket.meta.get(key) or []] + [value])


def refuse_transition(ticket: Ticket, want: str, tracker: Tracker) -> None:
    if want == ticket.status:
        return
    if want not in INTO:
        raise Refused([f"`status: {want}` is no ticket status; a ticket declares one of {', '.join(STATUSES)}"])
    allowed, rule = INTO[want]
    if ticket.status not in allowed:
        raise Refused([f"{ticket.slug} {ticket.status} → {want}: {rule}"])
    if want == "done" and (why := unlanded(ticket, tracker)):
        raise Refused([f"{ticket.slug} {ticket.status} → done: {why}"])


def unlanded(ticket: Ticket, tracker: Tracker) -> str | None:
    """Why the ticket's work has not landed here, or None once it has: its branch merged into the
    branch ticket branches merge into, or, for a parent ticket, every child ticket done."""
    top = toplevel(tracker.root)
    branch = f"ticket/{ticket.slug}"
    onto = git(top, "rev-parse", "--abbrev-ref", "HEAD").strip()
    tip = subprocess.run(["git", "-C", str(top), "rev-parse", "--verify", "-q", branch], capture_output=True, text=True)
    if tip.returncode != 0:
        children = tracker.children(ticket.slug)
        if children and all(child.status == "done" for child in children):
            return None
        return f"no branch {branch} here; done follows the user's accept and the merge of what it built"
    landed = subprocess.run(["git", "-C", str(top), "merge-base", "--is-ancestor", tip.stdout.strip(), "HEAD"])
    return None if landed.returncode == 0 else f"{branch} is not merged into {onto}; done follows the user's accept and its merge"


def written_with(text: str, changes: dict[str, str | None]) -> str:
    """The file with its frontmatter carrying `changes`, a None dropping a field. A field it does not
    have yet goes in as the last frontmatter line, away from `status`, which a ticket branch writes
    too: adjacent lines would make the merge conflict."""
    opening = re.match(r"\A---\n(.*?\n)---\n", text, re.DOTALL)
    if not opening:
        raise Refused(["no frontmatter to write into"])
    lines, left = [], dict(changes)
    for line in opening.group(1).splitlines():
        key = re.match(r"([\w-]+):", line)
        if key and key.group(1) in left:
            value = left.pop(key.group(1))
            if value is not None:
                lines.append(f"{key.group(1)}: {value}")
        else:
            lines.append(line)
    lines += [f"{key}: {value}" for key, value in left.items() if value is not None]
    return "---\n" + "\n".join(lines) + "\n---\n" + text[opening.end():]


@app.command(name="rule")
def rule(
    slug: Annotated[str, tyro.conf.Positional],
    tag: Annotated[str, tyro.conf.Positional],
    answer: Annotated[str, tyro.conf.Positional],
) -> int:
    """Write the user's answer under the question it answers, in the tracker's own copy of the
    ticket. Refuses a tag the ticket does not ask, and one already ruled.

    Args:
        slug: the ticket.
        tag: the question's tag, D1 onward.
        answer: what the user ruled, in their words.
    """
    tracker = here()
    ticket = tracker.ticket(slug)
    asked = next((question for question in ticket.questions if question.tag == tag), None)
    if not asked:
        raise Refused([f"{slug} asks no {tag}; it asks {', '.join(q.tag for q in ticket.questions) or 'nothing'}"])
    if asked.ruled:
        raise Refused([f"{slug} {tag} was ruled {asked.ruled}: {asked.answer}; a later decision amends that line in place, marked `(amended <date>, was …)`"])
    item = next(bullet for section in ticket.sections for bullet in section.bullets if bullet.line == asked.line)
    today = datetime.date.today().isoformat()
    lines = ticket.path.read_text().splitlines()
    lines.insert(item.last, f"{' ' * (item.indent + 2)}- Ruled {today}: {answer}")
    written = "\n".join(lines) + "\n"
    after = read(ticket.path, written)
    refuse([r for r in holds(after, replace(tracker, tickets={**tracker.tickets, slug: after})) if r not in holds(ticket, tracker)])
    ticket.path.write_text(written)
    print(f"{slug}: {tag} ruled {today}")
    return 0


# ---- retiring --------------------------------------------------------------
# Nothing leaves irrecoverably: a tracked file leaves by `git rm`, so history keeps it; an untracked
# one is moved to ~/logs, unless it is a render whose generating source is tracked, which alone is
# deleted. Every step is printed as it runs, and the commit stays with the caller.

LINKED = re.compile(r"agent/(?:prototypes|research)/[\w./-]*[\w-]")


@app.command(name="retire")
def retire(slug: Annotated[str, tyro.conf.Positional]) -> int:
    """Take a shipped ticket and its descendants out of the live tracker, with the show directories,
    prototypes and research notes they own, and stage the removal. Prints every step it runs.

    Args:
        slug: the ticket; its child tickets are retired with it.
    """
    tracker = here()
    top = toplevel(tracker.root)
    retiring = [tracker.ticket(slug), *descendants(slug, tracker)]
    if standing := [one.slug for one in retiring if one.status != "done"]:
        raise Refused([f"{', '.join(standing)} is not done; a ticket is retired once the user's accept has merged its work"])

    known = {top / name for name in git(top, "ls-files").splitlines()}
    leaving = sorted(owned(retiring, tracker, top))
    tracked = [path for path in leaving if path in known]
    if dirty := [path for path in tracked if git(top, "status", "--porcelain", "--", str(path.relative_to(top))).strip()]:
        raise Refused([f"{', '.join(str(path.relative_to(top)) for path in dirty)} has changes no commit holds; git history is what keeps a retired file, so commit them first"])
    if tracked:
        run(top, "git", "rm", "-q", *[str(path.relative_to(top)) for path in tracked])
    for path in [path for path in leaving if path not in known and path.exists()]:
        if renders(path, known):
            run(top, "rm", str(path.relative_to(top)))
        else:
            kept = Path.home() / LOGS / "agent" / top.name / path.relative_to(top)
            kept.parent.mkdir(parents=True, exist_ok=True)
            run(top, "mv", str(path.relative_to(top)), str(kept))
    for directory in sorted({path.parent for path in leaving if path.parent != tracker.root}, reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            run(top, "rmdir", str(directory.relative_to(top)))
    unblock([one.slug for one in retiring], tracker, top)
    others = len(retiring) - 1
    print(f"retired {slug}" + (f" and {others} child ticket{'s' if others > 1 else ''}" if others else "") + "; staged, not committed")
    return 0


def descendants(slug: str, tracker: Tracker) -> list[Ticket]:
    found = []
    for child in tracker.children(slug):
        found += [child, *descendants(child.slug, tracker)]
    return found


def owned(retiring: Sequence[Ticket], tracker: Tracker, top: Path) -> set[Path]:
    """Every file the retired tickets take with them: their own, their show directories, and the
    prototypes and research notes they link that no surviving ticket links too."""
    leaving = {one.path for one in retiring}
    for one in retiring:
        show = top / "agent" / "show" / one.slug
        leaving |= {path for path in show.rglob("*") if path.is_file()} if show.is_dir() else set()
    kept = "\n".join(one.body for one in tracker.tickets.values() if one not in retiring)
    for one in retiring:
        for link in LINKED.findall(one.body):
            if (top / link).is_file() and link not in kept:
                leaving.add(top / link)
    return leaving


def renders(path: Path, known: set[Path]) -> bool:
    """Whether an untracked file is a render its tracked source regenerates: the SVG beside its
    `.mmd`, the PNG beside the page that draws it, what a tracked `demo` wrote into `out/`."""
    if path.parent.name == "out":
        return any(source.parent == path.parent.parent for source in known)
    return any(source.parent == path.parent and source.stem == path.stem for source in known)


def unblock(retired: Sequence[str], tracker: Tracker, top: Path) -> None:
    """The blocking edges onto the retired tickets, dropped from the tickets that stay: a retired
    ticket has shipped, and an edge naming no ticket is refused by every reader."""
    for ticket in tracker.tickets.values():
        if ticket.slug in retired or not set(ticket.blocked_by) & set(retired):
            continue
        left = [ref for ref in ticket.blocked_by if ref not in retired]
        ticket.path.write_text(written_with(ticket.path.read_text(), {"blocked-by": rendered(left) if left else None}))
        print(f"+ drop {', '.join(sorted(set(ticket.blocked_by) & set(retired)))} from {ticket.slug}'s blocked-by")
        run(top, "git", "add", str(ticket.path.relative_to(top)))


def run(cwd: Path, *args: str) -> None:
    print("+ " + " ".join(args), flush=True)
    done = subprocess.run(args, cwd=cwd)
    if done.returncode != 0:
        raise Refused([f"{' '.join(args)} failed"])


# ---- the commit hook -------------------------------------------------------

HOOK = """#!/bin/sh
# Installed by `tracker hook`: a ticket file no reader can read is refused where it was written.
if ! command -v tracker >/dev/null 2>&1; then
    echo "pre-commit: no tracker on PATH, so the staged ticket files went unchecked" >&2
    exit 0
fi
exec tracker check
"""


@app.command(name="hook")
def hook() -> int:
    """Install the pre-commit hook that runs `tracker check` over the staged ticket files. Prints
    the path it wrote. Leaves a pre-commit hook this did not write standing, and says so."""
    top = toplevel(Path.cwd())
    into = Path(git(top, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()) / "hooks" / "pre-commit"
    if into.exists() and into.read_text() != HOOK:
        raise Refused([f"{into} is a pre-commit hook this did not write; add `tracker check` to it by hand"])
    into.parent.mkdir(parents=True, exist_ok=True)
    into.write_text(HOOK)
    into.chmod(0o755)
    print(into)
    return 0


# ---- the command line ------------------------------------------------------


def here() -> Tracker:
    return tracker_of(find_tracker(Path.cwd()))


def refuse(found: Sequence[object]) -> None:
    if found:
        raise Refused(found)


def cli(argv: Sequence[str]) -> int:
    """The command line as a call: what `main` runs, answering with the code it would exit on."""
    try:
        return app.cli(args=list(argv), description=__doc__, config=(tyro.conf.OmitArgPrefixes,)) or 0
    except Refused as no:
        said = str(no)
        print(f"tracker: refused:\n{said}" if "\n" in said else f"tracker: refused: {said}", file=sys.stderr)
        return 1


def main() -> None:
    sys.exit(cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
