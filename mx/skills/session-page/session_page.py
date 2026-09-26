"""The session page: a session's own records and its transcript, rendered as one page.

A session that needs more than a line writes `agent/sessions/<session-id>/session.md` and one
`turns/NN.md` per turn; this turns the two, with the session's transcript, into `index.html`
beside them. The seam is `render_session`: a session directory and a transcript in, the page out.

The reading is stubbed. test_session_page.py holds the properties the page has to satisfy, and
the `session-renderer` slice of agent/tickets/session-page.md fills the stubs in against its
Decisions; the worked example those properties read is `fixtures/session/` beside this file.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PAGE = "index.html"  # the rendered page, in the session's own directory

# The marks the page carries, which a check reads it by.
OPEN_QUESTIONS = "open-questions"  # id of the block at the top: the questions waiting on the user
TURN = "data-turn"  # on a turn's section: the two digits of the record it renders
QUESTION = "data-question"  # on a question, at the top or in its turn: its tag


class RecordError(Exception):
    """A record the renderer cannot read, at the line it gave up on. The Stop hook sends the
    agent back with `str(e)`, which reads `path:line: reason`."""

    def __init__(self, path: Path, line: int, reason: str) -> None:
        super().__init__(f"{path}:{line}: {reason}")
        self.path, self.line, self.reason = path, line, reason


@dataclass(frozen=True)
class Question:
    """One `- [Qn] **headline** detail` item under a turn's `## Questions`: a call only the user
    can make, with its options as sub-items and the agent's pick marked."""

    tag: str  # Q1, Q2, ... the session's running sequence
    headline: str  # the bold sentence the page shows
    detail: str  # the rest of the item, as written
    options: tuple[str, ...] = ()  # the sub-items, in the order the record has them
    picked: str | None = None  # the letter of the option marked as the agent's pick
    answered: str | None = None  # a later turn's answer: the option's letter, or the user's own words
    superseded: str | None = None  # the tag of the question that replaced it


@dataclass(frozen=True)
class Link:
    """One item under a turn's `## Links`: an artefact the turn produced, which opens in a tab of
    its own."""

    text: str
    path: str  # from the repo root, which the renderer resolves
    note: str


@dataclass(frozen=True)
class Turn:
    """One `turns/NN.md`, with the user's message the transcript carries for it."""

    number: int
    headline: str  # the record's H1
    message: str  # the user's message this turn answered, whole, from the transcript
    questions: tuple[Question, ...] = ()
    links: tuple[Link, ...] = ()
    details: str = ""  # the `## Details` section, as markdown


@dataclass(frozen=True)
class Session:
    """A session's directory, read: `session.md` and the turn records in it, oldest first."""

    id: str
    repo: str
    title: str  # session.md's H1
    brief: str  # its `## Brief`
    turns: tuple[Turn, ...] = field(default_factory=tuple)


def read_session(directory: Path, transcript: Path) -> Session:
    """The session `directory` holds, with each turn's message read from `transcript`.

    Raises RecordError where a record does not parse. Lifted by session-renderer.
    """
    raise NotImplementedError


def render_session(directory: Path, transcript: Path, now: datetime | None = None) -> str:
    """The session page for `directory`: its title, brief and resume command, the questions no
    later turn answered or superseded, then the turns newest first.

    `now` is what the page says it was rendered at, the clock by default; a check pins it so that
    two renders of the same records can be compared. Lifted by session-renderer.
    """
    raise NotImplementedError
