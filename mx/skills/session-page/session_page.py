"""The session page: a session's own records and its transcript, rendered as one page.

A session that needs more than a line writes `agent/sessions/<session-id>/session.md` and one
`turns/NN.md` per turn; this turns the two, with the session's transcript, into `index.html`
beside them. The seam is `render_session`: a session directory and a transcript in, the page out.

The reading is stubbed. test_session_page.py holds the properties the page has to satisfy, and
agent/tickets/session-renderer.md fills the stubs in against the Decisions of its parent,
agent/tickets/session-page.md; the worked example those properties read is `fixtures/session/`
beside this file.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PAGE = "index.html"  # the rendered page, in the session's own directory

# What the page carries so a check can find its parts, each once on the thing it names. The
# prototype has no counterpart for any of the three, and test_session_page.py pins their values.
QUESTIONS = "open-questions"  # the id of the block at the top: the questions waiting on the user
RECORD = "data-record"  # the attribute on a turn's section: the two digits of the record it renders
QUESTION = "data-question"  # the attribute on a question, at the top and in its turn: its tag


def render_session(directory: Path, transcript: Path, now: datetime | None = None) -> str:
    """The session page for `directory`: its title, brief and resume command, the questions no
    later turn answered or superseded, then the turns newest first.

    `now` is the clock the page is rendered against, the machine's by default; a check pins it so
    that two renders of the same records compare. Lifted by session-renderer.
    """
    raise NotImplementedError


def read_session(directory: Path, transcript: Path) -> "Session":
    """The session `directory` holds, with each turn's message read from `transcript`.

    Raises RecordError where a record does not parse. Lifted by session-renderer.
    """
    raise NotImplementedError


class RecordError(Exception):
    """A record the renderer cannot read, at the line it gave up on where the reason has one. The
    Stop hook sends the agent back with `str(e)`."""

    def __init__(self, path: Path, line: int | None, reason: str) -> None:
        super().__init__(f"{path}{f':{line}' if line is not None else ''}: {reason}")


# ---- what a session's directory holds ---------------------------------------


@dataclass(frozen=True)
class Option:
    """One answer a question offers, as a sub-item under it."""

    letter: str
    text: str
    picked: bool  # the agent's own pick, which the record marks


@dataclass(frozen=True)
class Question:
    """One `- [Qn] **headline** detail` item under a turn's `## Questions`: a call only the user
    can make. It clears through the frontmatter of the turn that received the answer."""

    tag: str  # Q1, Q2, ... the session's running sequence
    headline: str  # the bold sentence the page shows
    detail: str  # the rest of the item, as written
    options: tuple[Option, ...] = ()
    why: str = ""  # the `- Why:` sub-item under the options, where the question carries one


@dataclass(frozen=True)
class Link:
    """One item under a turn's `## Links`: an artefact the turn produced, which opens in a tab of
    its own."""

    text: str
    path: Path  # from the repo root, which the renderer resolves
    note: str


@dataclass(frozen=True)
class Turn:
    """One `turns/NN.md`, with the user's message the transcript carries for it."""

    number: int
    path: Path
    date: str
    headline: str  # the record's H1
    message: str  # the user's message this turn answered, whole, from the transcript
    questions: tuple[Question, ...] = ()
    links: tuple[Link, ...] = ()
    details: str = ""  # the `## Details` section, as markdown
    # the record's frontmatter: the tag of a question this turn cleared, to the option's letter or
    # the user's own words, and to the tag of the question that replaced it
    answered: dict[str, str] = field(default_factory=dict)
    superseded: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Session:
    """A session's directory, read: `session.md` and the turn records in it, oldest first."""

    id: str
    repo: Path
    title: str  # session.md's H1
    brief: str  # its `## Brief`
    turns: tuple[Turn, ...] = ()
