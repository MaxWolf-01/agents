"""What a qualified tag names: `<ticket> D6`, `<ticket> P3`, `<ticket> A21`, a tag that reaches a page
the user reads outside its own file, named by the ticket it lives in. A bare tag means something only
inside that file; a page that shows one qualified links it to its ticket with what it names as a hover
preview. `resolver` reads that from the tracker, and a page builds its own link from it.

The tracker's own citation of a property, `<ticket>#P3`, is read as the same tag.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import tracker

# A qualified tag in text: a ticket's slug, then a space or `#`, then the tag. Only a slug the
# tracker holds makes it one, so prose that merely looks like it ("step 2 P3") names nothing.
QUALIFIED = re.compile(rf"(?<![\w/.-])({tracker.SLUG.pattern})[ #]([DPA]\d+)\b")


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
