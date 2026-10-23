#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""Render a session directory and its transcript into the session page, `index.html` in that directory.

The directory is `agent/sessions/<session-id>/`: `session.md`, one `turns/NN.md` per turn the agent
recorded and one `turns/chat-<time>.md` per turn the Stop hook recorded from a chat reply, in the
shape RULES.md gives them, and `previous`, which the handoff skill's `pickup.py` writes where the
session picked up another's continuation handoff. Any of them may be missing: a session's first
turns are often chat turns alone, and `session.md` comes with the first record. The page shows the
title, links to the pages of the sessions before and after it across a handoff, the resume
command, the questions no later turn answered or superseded and the tickets' questions a turn put
to the user that their tickets hold open, then the turns newest first,
each with the user's messages it answered and what other sessions sent meanwhile, read from the
transcript.
The page is laid out in panes that each scroll on their own: the title and the questions above
the turns, and beside them the timeline, every numbered turn newest first with the artefacts it
links; a ticket file is no artefact there. Each turn's record, and the whole session's, copies as
the markdown it was written in.

Run as a command, it prints where a session's directory is.
"""

import html
import itertools
import json
import os
import re
import shlex
import sys
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeVar

import yaml
from markdown_it import MarkdownIt
from markdown_it.common.normalize_url import validateLink
from markdown_it.rules_core import linkify
from markdown_it.rules_inline import linkify as linkify_inline
from markdown_it.token import Token

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tracker"))
import tracker  # noqa: E402  finds the agent repo a session's directory is in, as `tracker root` does
import qualified  # noqa: E402  what a ticket's qualified tag names, which the page shows its questions by and links

PAGE = "index.html"  # the rendered page, in the session's own directory
# In a session's directory, the id of the session whose continuation handoff it picked up, which the
# handoff skill's `pickup.py` writes once. The link forward from that session's page is read from
# it, not written.
PREVIOUS = "previous"
SESSIONS = Path("agent/sessions")  # where a session's directory sits, from the repo root

QUESTIONS = "open-questions"  # the id of the block at the top: the questions waiting on the user
# The timeline beside the turns, which lists every artefact of the session under its turn, and the
# attribute each link to an artefact carries, wherever on the page it sits: the file it resolves to
# on this machine, or its URL. The dotfiles' container hub finds the links it marks by these two names.
COLUMN = "artefacts"
ARTEFACT = "data-artefact"

HERE = Path(__file__).resolve().parent
TOKENS = HERE.parent / "house-style" / "tokens.css"


CLI = """Print the directory this session's records go in: `sessions/<session-id>` in the agent repo
of the project the working directory is in, the same directory from every worktree of that
project, the id being $CLAUDE_CODE_SESSION_ID. It need not exist yet.

Exits 1, saying why, outside a project with an agent repo or outside a Claude Code session.

Examples:

    session-page
"""


def main() -> None:
    import tyro

    tyro.cli(lambda: None, description=CLI)
    if not (session := os.environ.get("CLAUDE_CODE_SESSION_ID", "")):
        sys.exit("no session id: run it inside a Claude Code session")
    if (directory := session_directory(Path.cwd(), session)) is None:
        sys.exit(f"{Path.cwd()} is in no project with an agent repo")
    print(directory)


def session_directory(cwd: Path, session: str) -> Path | None:
    """Where the session's records and page live, whether or not they exist yet. None outside a
    project with an agent repo."""
    sessions = sessions_directory(cwd)
    return sessions / session if sessions else None


def sessions_directory(cwd: Path) -> Path | None:
    """`sessions/` in the agent repo of the project `cwd` is in, found the way `tracker root` finds
    the tracker, so every worktree of the project names the same one. None outside a project with an
    agent repo."""
    try:
        return tracker.tracker_root(cwd).parent / SESSIONS.name
    except tracker.Refused:
        return None


def render_session(directory: Path, transcript: Path, now: datetime | None = None) -> str:
    """The session page for `directory`: its title and resume command, the questions waiting on
    the user (`open_questions`), then the turns newest first.

    `now` is the clock the page is rendered against, the machine's by default; a check pins it so
    that two renders of the same records compare.
    """
    return page(read_session(directory, transcript), now or datetime.now())


def read_session(directory: Path, transcript: Path, pending: tuple[dict, ...] = ()) -> "Session":
    """The session `directory` holds, with each turn's messages read from `transcript`. `pending`
    is entries the transcript does not hold yet, read as though it ended on them: Claude Code writes
    a tool call there only after the call's PostToolUse hooks have run.

    Where there is no `session.md` yet, the title is the one Claude Code keeps for the session
    (`claude_title`), and the resume command changes to the directory the session started in.

    Raises RecordError where a record does not parse.
    """
    # an older session.md may carry a `## Brief`, which parses and stays off the page
    front, title, _ = read_record(
        directory / "session.md", required={"session", "repo"}, allowed={"session", "repo"}, sections={"Brief"},
    ) if (directory / "session.md").exists() else ({}, "", {})
    root = directory.parents[len(SESSIONS.parts)]
    turns = read_turns(directory / "turns")
    chats = read_chats(directory / "turns")
    settled = settle(turns)
    turns = held_in_tickets(turns, root / tracker.TICKETS)
    entries = read_transcript(transcript) + list(pending)
    written = written_at(entries, directory, turns)
    turns = [replace(t, written=written.get(t.number)) for t in turns]
    spoken = said(entries)
    timeline = in_order(turns, chats)
    times = [t.written for t in timeline]
    messages, peers = pair(spoken, times), bucket(sent(entries), times)
    paired = {t.path: replace(t, messages=tuple(said_before), sent=tuple(sent_before))
              for t, said_before, sent_before in zip(timeline, messages, peers)}
    session = str(front.get("session", directory.name))
    previous = predecessor(directory)
    return Session(
        id=session,
        name=registered_name(session),
        repo=Path(str(front["repo"])) if "repo" in front else started_in(entries) or root,
        title=title or claude_title(entries) or f"session {session[:8]}",
        turns=tuple(paired[t.path] for t in turns),
        chats=tuple(paired[c.path] for c in chats),
        settled=settled,
        began=turn_start(entries),
        spoke=spoke_in(entries),
        described=max((at for at, path in writes(entries) if path.parts[-2:] == (directory.name, "session.md")), default=None),
        root=root,
        directory=directory,
        previous=previous if previous and (directory.parent / previous / PAGE).exists() else "",
        following=successors(directory),
        titles={other: title_of(directory.parent / other) for other in (previous, *successors(directory)) if other},
    )


def held_in_tickets(turns: list[Turn], tickets: Path) -> list[Turn]:
    """Each turn with what the tracker at `tickets` holds under every ticket's question it asks: a
    tag that names no question there, a retired ticket's or a closing comment's detail entry, is
    held as none."""
    resolve = qualified.resolver(tickets)

    def held(q: Question | Cited) -> Question | Cited:
        if not isinstance(q, Cited):
            return q
        named = resolve(q.ticket, q.tag)
        return replace(q, named=named if named and named.kind == "question" else None)

    return [replace(t, questions=tuple(map(held, t.questions))) for t in turns]


def title_of(directory: Path) -> str:
    """The H1 of another session's `session.md`, which names its subject; empty where it has none."""
    try:
        heading = re.search(r"^# (.+)$", (directory / "session.md").read_text(), re.M)
    except OSError:
        return ""
    return heading[1].strip() if heading else ""


def predecessor(directory: Path) -> str:
    """The session `directory`'s `previous` names; empty where it names none."""
    try:
        return (directory / PREVIOUS).read_text().strip()
    except OSError:
        return ""


def successors(directory: Path) -> tuple[str, ...]:
    """The sessions beside `directory` whose `previous` names it, by id: one handoff split into
    several has several."""
    return tuple(sorted(
        d.name for d in directory.parent.iterdir() if d != directory and d.is_dir() and predecessor(d) == directory.name
    )) if directory.parent.is_dir() else ()


def registered_name(session: str) -> str:
    """The session's short name (the `agents-46` kind Claude Code shows), from its entry in Claude
    Code's session registry, one `sessions/<pid>.json` per running process under the config
    directory. A session resumed in two processes has two entries; the one updated last names it.
    Empty where no entry is the session's."""
    registry = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "sessions"
    named = []
    for path in registry.glob("*.json"):
        try:
            entry = json.loads(path.read_text())
        except (OSError, ValueError):
            continue  # an entry half written, or gone between the glob and the read
        if isinstance(entry, dict) and entry.get("sessionId") == session and entry.get("name"):
            named.append((entry.get("updatedAt") or 0, str(entry["name"])))
    return max(named)[1] if named else ""


def left_alone() -> str:
    """Why nobody reads this session's page, where nobody does: a dispatched worker or a print-mode
    session. Empty for a session someone is sitting at."""
    if os.environ.get("DISPATCH_WORKLOG"):
        return "dispatched worker"
    if os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return "print-mode session"
    return ""


def written_this_turn(session: "Session") -> "Turn | None":
    """The newest record the transcript writes after this turn began, by the write time the page
    pairs messages by. With no turn begun yet, the newest record the transcript writes."""
    written = [t for t in session.turns if t.written and (session.began is None or t.written > session.began)]
    return written[-1] if written else None


class RecordError(Exception):
    """A record the renderer cannot read, at the line it gave up on where the reason has one. The
    hooks send the agent back with `str(e)`."""

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
    # A blind question's test page (`blind-test`), from the repo root or absolute: the page holds its
    # options and the agent's pick, if any, so the question carries neither.
    blind: str = ""

    @property
    def handle(self) -> str:
        return self.tag


@dataclass(frozen=True)
class Cited:
    """One `- [<ticket> Dn]` item under a turn's `## Questions`: a question of a ticket's, put to the
    user. Its words and its ruling live in the ticket, so it waits at the top while the ticket holds
    it open and clears once the ticket records the ruling."""

    ticket: str  # the slug
    tag: str  # D1, D2, ... the ticket's own sequence
    # the question as the ticket held it when the session was read; None where the ticket, or the
    # question, is no longer there
    named: qualified.Named | None = None

    @property
    def handle(self) -> str:
        return f"{self.ticket} {self.tag}"

    @property
    def headline(self) -> str:
        return self.named.headline if self.named else self.handle

    @property
    def open(self) -> bool:
        return self.named is not None and self.named.open


@dataclass(frozen=True)
class Link:
    """One item under a turn's `## Links`: an artefact the turn produced, or a ticket file, which
    the artefact column leaves out. Either opens from the page in a tab of its own; the Stop hook
    hands the artefacts to the container hub, where one runs (stop_hook.py)."""

    text: str
    path: str  # from the repo root, which the renderer resolves, or absolute for one outside the repo
    note: str

    @property
    def ticket(self) -> bool:
        """Whether it points at a ticket file, in this repo or another: a markdown file directly
        in an `agent/tickets/`."""
        target = Path(file_part(self.path))
        return target.suffix == ".md" and target.parent.parts[-2:] == tracker.TICKETS.parts


@dataclass(frozen=True)
class Sent:
    """A message another Claude session sent into this one."""

    name: str  # the sender's `from-name`, as Claude Code labels it
    text: str


@dataclass(frozen=True)
class Turn:
    """One `turns/NN.md`, with the user's messages the transcript carries for it."""

    number: int
    path: Path
    date: str
    headline: str  # the record's H1
    written: datetime | None = None  # when the transcript shows the record written, where it shows it
    messages: tuple[str, ...] = ()  # what the user said that this turn answered, whole, oldest first
    sent: tuple[Sent, ...] = ()  # what other sessions sent in the same stretch, oldest first
    questions: tuple[Question | Cited, ...] = ()  # in the order the record asks them
    links: tuple[Link, ...] = ()
    details: str = ""  # the `## Details` section, as markdown
    # the record's frontmatter: the tag of a question this turn cleared, to the option's letter or
    # the user's own words, and to the tag of the question that replaced it
    answered: dict[str, str] = field(default_factory=dict)
    superseded: dict[str, str] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.number:02d}"

    @property
    def artefacts(self) -> tuple[Link, ...]:
        return tuple(link for link in self.links if not link.ticket)


@dataclass(frozen=True)
class Chat:
    """One `turns/chat-<time>.md`: a chat turn, the reply a turn ended on in the chat where the
    turn wrote no record, which the Stop hook recorded. It takes no number of the agent's records,
    and sits among them by its time."""

    path: Path
    date: str
    reply: str  # as markdown, as it stood
    written: datetime  # when the Stop hook wrote it, which pairs the user's messages with it
    messages: tuple[str, ...] = ()
    sent: tuple[Sent, ...] = ()

    @property
    def key(self) -> str:
        return self.path.stem


@dataclass(frozen=True)
class Settled:
    """How a question left the top: answered with `value`, or superseded by the question `value`
    names, in turn `turn`."""

    how: Literal["answered", "superseded"]
    value: str
    turn: int


@dataclass(frozen=True)
class Session:
    """A session's directory, read: `session.md` where there is one, and the records in it, oldest first."""

    id: str
    repo: Path  # where the resume command changes to
    title: str  # session.md's H1, or Claude Code's title for the session where there is no session.md
    root: Path  # the repo root the directory sits under, which a record's paths are from
    directory: Path  # the session's own, which holds its records
    name: str = ""  # its short name in Claude Code's session registry; empty where it has no entry
    turns: tuple[Turn, ...] = ()
    chats: tuple[Chat, ...] = ()  # oldest first
    settled: dict[str, Settled] = field(default_factory=dict)  # by question tag; the rest are open
    began: datetime | None = None  # when the newest turn began, as the transcript has it (turn_start)
    spoke: datetime | None = None  # when the turn holding the user's last message began (spoke_in)
    described: datetime | None = None  # when the transcript last shows session.md written
    previous: str = ""  # the session whose continuation handoff this one picked up, where that one has a page
    following: tuple[str, ...] = ()  # the sessions that picked up a continuation handoff of this one
    titles: dict[str, str] = field(default_factory=dict)  # those sessions' titles, by id, where their session.md has one


# ---- reading the records ----------------------------------------------------

TAG = re.compile(r"Q\d+")


def read_turns(turns: Path) -> list[Turn]:
    records = sorted((p for p in turns.glob("*.md") if re.fullmatch(r"\d+\.md", p.name)), key=lambda p: int(p.stem))
    return [read_turn(path) for path in records]


def read_turn(path: Path) -> Turn:
    front, body, offset = read_frontmatter(path, required={"date"}, allowed={"date", "answered", "superseded"})
    headline, sections = split_sections(path, body, offset, {"Questions", "Links", "Details"})
    tables = {}
    for name in ("answered", "superseded"):
        table = front.get(name) or {}
        if not isinstance(table, dict):
            raise RecordError(path, line_of(path, name), f"{name}: a mapping of question tags, like `Q1: a`")
        tables[name] = {str(tag): str(value) for tag, value in table.items()}
        for tag in tables[name]:
            if CITED_ITEM.fullmatch(f"- [{tag}]"):
                raise RecordError(path, line_of(path, tag), f"{name}: {tag} is a ticket's question, which clears once its ticket "
                                                            "records the ruling (`tracker rule`), never here")
            if not TAG.fullmatch(tag):
                raise RecordError(path, line_of(path, tag), f"{name}: {tag!r} is not a question tag like Q7")
    for old, new in tables["superseded"].items():
        if not TAG.fullmatch(new):
            raise RecordError(path, line_of(path, old), f"superseded: {old} names {new!r}, not a question tag like Q7")
    return Turn(
        number=int(path.stem),
        path=path,
        date=str(front["date"]),
        headline=headline,
        questions=read_questions(path, *sections["Questions"]) if "Questions" in sections else (),
        links=read_links(path, *sections["Links"]) if "Links" in sections else (),
        details=sections.get("Details", (0, ""))[1],
        **tables,
    )


# A chat turn's record, which the Stop hook writes for a turn that ended on a chat reply and wrote
# no record of its own: `turns/chat-<time>.md`, the time in UTC so that names sort as times do. Its
# frontmatter's `chat` is when the hook wrote it, which pairs the user's messages with it as a
# Write call's time does for a record the agent wrote; its body is the reply as it stood.
CHAT = "chat"
CHAT_NAME = "chat-%Y%m%dT%H%M%SZ.md"


def chat_path(turns: Path, at: datetime) -> Path:
    """Where the chat turn written at `at`, a time with its zone, goes in the `turns/` directory."""
    return turns / at.astimezone(UTC).strftime(CHAT_NAME)


def chat_record(reply: str, at: datetime) -> str:
    """A chat turn's record of `reply`, written at `at`, a time with its zone."""
    return f"---\ndate: {at.astimezone():%Y-%m-%d}\n{CHAT}: {at.isoformat()}\n---\n\n{reply.strip()}\n"


def read_chats(turns: Path) -> list[Chat]:
    return [read_chat(path) for path in sorted(turns.glob("chat-*.md")) if re.fullmatch(r"chat-\d{8}T\d{6}Z\.md", path.name)]


def read_chat(path: Path) -> Chat:
    """A chat turn's record. The body is never split into sections, so a heading in the reply
    stays the reply's own."""
    front, body, _ = read_frontmatter(path, required={"date", CHAT}, allowed={"date", CHAT})
    try:
        at = datetime.fromisoformat(str(front[CHAT]))
    except ValueError:
        at = None
    if at is None or at.tzinfo is None:
        raise RecordError(path, line_of(path, CHAT), f"{CHAT}: {front[CHAT]!r} is not a time with its zone, like 2026-10-05T14:02:00+00:00")
    return Chat(path=path, date=str(front["date"]), reply=body.strip(), written=at)


def in_order(turns: list[Turn], chats: list[Chat]) -> list[Turn | Chat]:
    """The turn records and chat turns as they happened: each chat turn before the first record
    written after it. A record the transcript shows no write for has no time, and holds its place
    in the numbered order."""
    timeline: list[Turn | Chat] = []
    waiting = sorted(chats, key=lambda c: c.written)
    for turn in turns:
        while waiting and turn.written is not None and waiting[0].written < turn.written:
            timeline.append(waiting.pop(0))
        timeline.append(turn)
    return timeline + waiting


# A pointer at another part of the page in words: a question at the top sits far from the turn
# whose Details it means, so the reader needs a link there.
CROSS_REFERENCE = re.compile(r"\b(?:see|under|in) (?:the )?(?:Details|Links|Questions)\b|\bsee (?:below|above)\b")


def check_references(path: Path) -> None:
    """A record's prose points at another part of the page by linking it; code and the
    frontmatter, which holds the user's own words, are not prose. Checked as a record is written,
    never as the page renders, since a record is never edited and older ones predate the check."""
    lines = path.read_text().split("\n")
    body = lines.index("---", 1) + 1 if "---" in lines[1:] else 0
    fence = False
    for n, line in enumerate(lines[body:], start=body + 1):
        if line.startswith("```"):
            fence = not fence
        elif not fence and (m := CROSS_REFERENCE.search(re.sub(r"`[^`]*`", "", line))):
            raise RecordError(path, n, f"{m.group()!r} points at another part of the page in words; link it instead: "
                                       "[text](#t07) opens turn 07, [text](#q3) shows question Q3")


def check_cited(session: "Session", path: Path) -> None:
    """Every ticket's question the record at `path` puts to the user is one its ticket holds open.
    Checked as a record is written, never as the page renders, since a ticket's question is ruled
    and its ticket retired long after the record that asked it."""
    turn = next((t for t in session.turns if t.path.resolve() == path.resolve()), None)
    lines = path.read_text().split("\n")
    for c in (q for q in (turn.questions if turn else ()) if isinstance(q, Cited) and not q.open):
        n = next((n for n, line in enumerate(lines, start=1) if line.startswith(f"- [{c.handle}]")), None)
        if not (session.root / ticket_path(c.ticket)).is_file():
            raise RecordError(path, n, f"{c.handle}: the tracker holds no ticket {c.ticket}")
        if c.named is None:
            raise RecordError(path, n, f"{c.handle}: {c.ticket} asks no question {c.tag} under its ## Questions")
        raise RecordError(path, n, f"{c.handle} was ruled {c.named.ruled} ({c.named.answer}), so it waits on nobody")


def read_record(
    path: Path, required: set[str], allowed: set[str], sections: set[str]
) -> tuple[dict, str, dict[str, tuple[int, str]]]:
    """A record's frontmatter as data, its H1, and each of its `##` sections as (first line, text)."""
    front, body, offset = read_frontmatter(path, required, allowed)
    h1, parts = split_sections(path, body, offset, sections)
    return front, h1, parts


def read_frontmatter(path: Path, required: set[str], allowed: set[str]) -> tuple[dict, str, int]:
    """A record's frontmatter as data, the text after it, and the line that text starts on."""
    if not path.is_file():
        raise RecordError(path, None, "no such file")
    text = path.read_text()
    m = re.match(r"---\n(.*?\n)?---\n", text, re.S)
    if not m:
        raise RecordError(path, 1, "no frontmatter: the file opens with --- and a YAML block closed by ---")
    try:
        front = yaml.load(m.group(1) or "", Loader=yaml.BaseLoader) or {}  # every scalar as written: `no` stays "no"
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        raise RecordError(path, mark.line + 2 if mark else 2, f"frontmatter is not YAML: {getattr(e, 'problem', None) or e}") from None
    if not isinstance(front, dict):
        raise RecordError(path, 2, "frontmatter is not a mapping")
    if unknown := sorted(set(front) - allowed):
        raise RecordError(path, line_of(path, unknown[0]), f"unknown frontmatter field {unknown[0]!r}; the fields are {', '.join(sorted(allowed))}")
    if missing := sorted(required - set(front)):
        raise RecordError(path, 2, f"frontmatter lacks {missing[0]!r}")
    return front, text[m.end():], m.group(0).count("\n") + 1


def line_of(path: Path, key: str) -> int:
    """The frontmatter line `key` is set on, the first line of the frontmatter where none is."""
    lines = path.read_text().split("\n")
    end = lines.index("---", 1) if "---" in lines[1:] else len(lines)
    return next((n for n, line in enumerate(lines[:end], start=1) if re.match(rf"\s*{re.escape(key)}\s*:", line)), 2)


def split_sections(path: Path, body: str, offset: int, allowed: set[str]) -> tuple[str, dict[str, tuple[int, str]]]:
    """The H1 and each `##` section as (first line number, text); fenced code is not split."""
    h1: str | None = None
    sections: dict[str, tuple[int, list[str]]] = {}
    current: str | None = None
    fence = False
    for i, line in enumerate(body.split("\n")):
        n = offset + i
        if line.startswith("```"):
            fence = not fence
        heading = None if fence else re.match(r"(#{1,2})(?!#)\s+(.+?)\s*$", line)
        if heading and heading.group(1) == "#":
            if h1 is not None:
                raise RecordError(path, n, "a second H1; a record has one H1, its headline")
            if current is not None:
                raise RecordError(path, n, "the H1 comes before the first section")
            h1 = heading.group(2)
        elif heading:
            name = heading.group(2)
            if name not in allowed:
                raise RecordError(path, n, f"unknown section {name!r}; the sections are {', '.join('## ' + a for a in sorted(allowed))}")
            if name in sections:
                raise RecordError(path, n, f"a second ## {name}")
            if h1 is None:
                raise RecordError(path, None, "no H1 before the first section; a record's headline is its H1")
            current = name
            sections[name] = (n + 1, [])
        elif current is not None:
            sections[current][1].append(line)
        elif line.strip():
            where = "before the H1" if h1 is None else "between the H1 and the first section"
            raise RecordError(path, n, f"text {where}; it belongs in a section")
    if h1 is None:
        raise RecordError(path, None, "no H1; a record's headline is its H1")
    out = {}
    for name, (start, lines) in sections.items():
        while lines and not lines[0].strip():
            lines, start = lines[1:], start + 1
        out[name] = (start, "\n".join(lines).rstrip())
    return h1, out


QUESTION_ITEM = re.compile(r"- \[(Q\d+)\] \*\*(.+?)\*\*(?:\s+(.*))?")
CITED_ITEM = re.compile(rf"- \[({tracker.SLUG.pattern}) (D\d+)\](.*)")
SUB_ITEM = re.compile(r"\s{2,}- (.*)")
OPTION = re.compile(r"\(([a-z])\)\s+(.*)")
PICK = re.compile(r"\s*\*my pick\*\s*")
WHY = re.compile(r"Why:\s*(.*)")
BLIND = re.compile(r"Blind:\s*(\S+)")


def read_questions(path: Path, start: int, text: str) -> tuple[Question | Cited, ...]:
    """`- [Q7] **headline** detail` items, each with `(a) text` options, at least two and one marked `*my pick*`,
    and at most one `Why: text`, as sub-items; a line indented under an item continues it. A blind
    question carries one `Blind: path` sub-item, its test page, and nothing else. A ticket's question
    is `- [<ticket> D3]` alone, since its words live in its ticket; what the ticket holds under it is
    read by `read_session`."""
    items: list[dict | Cited] = []
    part: dict | None = None  # the item or sub-item a continuation line extends
    for n, line in enumerate(text.split("\n"), start=start):
        if not line.strip():
            continue
        if m := CITED_ITEM.fullmatch(line):
            if m.group(3).strip():
                raise RecordError(path, n, f"{m.group(1)} {m.group(2)} is a ticket's question, whose words live in its ticket: "
                                           f"the item is `- [{m.group(1)} {m.group(2)}]` alone")
            items.append(Cited(m.group(1), m.group(2)))
            part = None
        elif items and isinstance(items[-1], Cited) and line.startswith(" "):
            raise RecordError(path, n, f"{items[-1].handle} is a ticket's question: its options and detail live in its ticket, not here")
        elif m := QUESTION_ITEM.fullmatch(line):
            part = {"tag": m.group(1), "headline": m.group(2), "text": m.group(3) or "", "options": [], "why": None,
                    "blind": None, "line": n}
            items.append(part)
        elif line.startswith("- "):
            raise RecordError(path, n, "a question is `- [Q7] **headline** detail`, or `- [<ticket> D3]` for a ticket's question")
        elif not items:
            raise RecordError(path, n, "text before the first question")
        elif m := SUB_ITEM.fullmatch(line):
            item = items[-1]
            if o := OPTION.fullmatch(m.group(1)):
                part = {"letter": o.group(1), "text": o.group(2)}
                item["options"].append(part)
            elif w := WHY.fullmatch(m.group(1)):
                if item["why"] is not None:
                    raise RecordError(path, n, f"a second Why: under {item['tag']}")
                part = item["why"] = {"text": w.group(1)}
            elif b := BLIND.fullmatch(m.group(1)):
                if item["blind"] is not None:
                    raise RecordError(path, n, f"a second Blind: under {item['tag']}")
                if b.group(1).startswith("../"):
                    raise RecordError(path, n, f"{b.group(1)} is neither a path from the repo root nor an absolute one")
                item["blind"], part = b.group(1), None
            else:
                raise RecordError(path, n, "a question's sub-item is an option `(a) text`, `Why: text` or `Blind: path`")
        elif line.startswith(" ") and part is not None:
            part["text"] = f"{part['text']} {line.strip()}".strip()
        else:
            raise RecordError(path, n, "unexpected text in ## Questions")
    questions: list[Question | Cited] = []
    for item in items:
        if isinstance(item, Cited):
            questions.append(item)
            continue
        if item["blind"] is not None:
            if item["options"] or item["why"] is not None:
                raise RecordError(path, item["line"], f"{item['tag']} is blind: its options, pick and why live in its test page, not here")
            questions.append(Question(item["tag"], item["headline"], item["text"], blind=item["blind"]))
            continue
        letters = [o["letter"] for o in item["options"]]
        if len(set(letters)) != len(letters):
            raise RecordError(path, item["line"], f"{item['tag']} repeats an option letter")
        options = tuple(Option(o["letter"], PICK.sub(" ", o["text"]).strip(), bool(PICK.search(o["text"]))) for o in item["options"])
        if len(options) < 2:
            raise RecordError(path, item["line"], f"{item['tag']} offers {len(options)} option{'s' * (len(options) != 1)}; a question offers at least two, `(a) text` sub-items")
        if sum(o.picked for o in options) != 1:
            raise RecordError(path, item["line"], f"{item['tag']} marks {'no option' if not any(o.picked for o in options) else 'more than one option'} *my pick*; it marks one")
        why = item["why"]["text"] if item["why"] else ""
        questions.append(Question(item["tag"], item["headline"], item["text"], options, why))
    return tuple(questions)


LINK_ITEM = re.compile(r"- \[(.+?)\]\(([^()\s]+)\)(?::\s*(.*))?\s*")


def read_links(path: Path, start: int, text: str) -> tuple[Link, ...]:
    """`- [text](path): note` items, the path from the repo root or absolute; an indented line
    continues the note."""
    links: list[list[str]] = []
    for n, line in enumerate(text.split("\n"), start=start):
        if not line.strip():
            continue
        if m := LINK_ITEM.fullmatch(line):
            if m.group(2).startswith("../"):
                raise RecordError(path, n, f"{m.group(2)} is neither a path from the repo root, like agent/show/<work>/page.html, nor an absolute one")
            links.append([m.group(1), m.group(2), m.group(3) or ""])
        elif line.startswith(" ") and links:
            links[-1][2] = f"{links[-1][2]} {line.strip()}".strip()
        else:
            raise RecordError(path, n, "a link is `- [text](path from the repo root, or absolute): note`")
    return tuple(Link(*link) for link in links)


def settle(turns: list[Turn]) -> dict[str, Settled]:
    """How each question that left the top left it, from later turns' frontmatter. A tag no
    earlier turn asked, or one already settled, does not parse."""
    asked: dict[str, int] = {}
    settled: dict[str, Settled] = {}
    for turn in turns:
        for how, table in (("answered", turn.answered), ("superseded", turn.superseded)):
            for tag, value in table.items():
                if tag not in asked:
                    raise RecordError(turn.path, line_of(turn.path, tag), f"{how}: {tag} is not a question of an earlier turn")
                if tag in settled:
                    raise RecordError(turn.path, line_of(turn.path, tag), f"{how}: {tag} was already {settled[tag].how} in turn {settled[tag].turn:02d}")
                settled[tag] = Settled(how, value, turn.number)
        for question in turn.questions:
            if question.handle in asked:
                raise RecordError(turn.path, None, f"{question.handle} was already asked in turn {asked[question.handle]:02d}")
            asked[question.handle] = turn.number
    for turn in turns:
        for old, new in turn.superseded.items():
            if new not in asked:
                raise RecordError(turn.path, line_of(turn.path, old), f"superseded: {old} names {new}, which no turn asks")
    return settled


# ---- reading the transcript -------------------------------------------------

# What Claude Code writes as a user entry or a queued command that the user never typed.
NOT_SAID = re.compile(r"\s*(<(task-notification|agent-message|cross-session-message|local-command-\w+|system-reminder|bash-input|bash-stdout|bash-stderr)\b|\[Request interrupted by user)")


# How a prompt another session sent opens: the line Claude Code heads one with where it starts a
# turn, none where it was queued mid-turn.
SENT = re.compile(r"\s*(?:Another Claude session sent a message:\s*)?<cross-session-message\b")

# How Claude Code wraps a message another session sent into this one: its attributes, its text.
# One prompt can carry several.
PEER = re.compile(r"<cross-session-message\b([^>]*)>\n?(.*?)(?:\n?</cross-session-message>|$)", re.S)


def read_transcript(transcript: Path) -> list[dict]:
    """The transcript's entries; a line that is not JSON, as the one being written can be, is skipped."""
    entries = []
    for line in transcript.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def claude_title(entries: list[dict]) -> str:
    """The title Claude Code keeps for the session: the last one a `/rename` gave it, else the last
    one it generated. Empty where it has neither yet. The dotfiles' container hub reads the same
    two, for its rail."""
    for kind, key in (("custom-title", "customTitle"), ("ai-title", "aiTitle")):
        if titles := [str(e[key]) for e in entries if e.get("type") == kind and e.get(key)]:
            return titles[-1]
    return ""


def started_in(entries: list[dict]) -> Path | None:
    """The directory the session started in, as its first entry that carries one has it."""
    return next((Path(e["cwd"]) for e in entries if isinstance(e.get("cwd"), str) and e["cwd"]), None)


def said(entries: list[dict]) -> list[tuple[datetime, str]]:
    """What the user said, with when, oldest first: their own prompts and the ones they queued
    mid-turn, and none of what Claude Code writes as the user (images, task notifications, other
    sessions' hand-backs and messages)."""
    return sorted(((when, text) for when, origin, content in prompts(entries)
                   if origin == "human" and (text := message_text(content))), key=lambda m: m[0])


def sent(entries: list[dict]) -> list[tuple[datetime, Sent]]:
    """What other sessions sent into this one, with when, oldest first."""
    return sorted(((when, Sent(name(m.group(1)), m.group(2))) for when, _, content in prompts(entries)
                   if SENT.match(text := flat(content)) for m in PEER.finditer(text)),
                  key=lambda s: s[0])


def prompted(entry: dict) -> bool:
    """Whether a user entry is one Claude Code wrote as a prompt: not a subagent's own transcript or
    a compaction's summary, and no meta line (a skill's body, an image) unless it has an origin. A
    message from another session or a subagent's hand-back is a meta line with an origin."""
    return entry.get("type") == "user" and not (entry.get("isSidechain") or entry.get("isCompactSummary")) and (
        not entry.get("isMeta") or bool(entry.get("origin")))


def local_commands(entries: list[dict]) -> set[str]:
    """The user entries of the slash commands Claude Code ran itself, which reach no model:
    /reload-plugins, /model, /status. Their output is a `local_command` entry under the command's
    own; a command that prompts the model (a skill) has the prompt there instead."""
    return {str(e["parentUuid"]) for e in entries
            if e.get("type") == "system" and e.get("subtype") == "local_command" and e.get("parentUuid")}


def prompts(entries: list[dict]) -> list[tuple[datetime, str, object]]:
    """Each user entry and queued prompt, with when, the kind of its origin and its content."""
    out, local = [], local_commands(entries)
    for entry in entries:
        if prompted(entry) and entry.get("uuid") not in local:
            content = entry.get("message", {}).get("content")
        elif entry.get("type") == "attachment" and entry.get("attachment", {}).get("type") == "queued_command":
            if entry["attachment"].get("commandMode", "prompt") != "prompt":
                continue
            content = entry["attachment"].get("prompt")
        else:
            continue
        if "timestamp" in entry:
            out.append((datetime.fromisoformat(entry["timestamp"]), entry.get("origin", {}).get("kind", "human"), content))
    return out


def turn_start(entries: list[dict]) -> datetime | None:
    """When the newest turn began: the last prompt Claude Code answered with a turn of its own,
    whoever sent it, the user, a finished task or another session, or else the end of the turn
    before it, where a prompt the transcript marks as none (a scheduled wakeup) started this one.
    Claude Code marks a turn's end with a `turn_duration` line once its Stop hooks let it end, so a
    Stop hook's send-back ends no turn. A message queued mid-turn joins the turn it arrived in, a
    tool result is part of the turn that called the tool, and a local command starts no turn."""
    return max(turn_starts(entries), default=None)


def spoke_in(entries: list[dict]) -> datetime | None:
    """When the turn that holds the user's last message began, read as `turn_start` reads the
    newest: a message queued mid-turn belongs to the turn it arrived in. None where the user has
    said nothing yet."""
    spoken = said(entries)
    if not spoken:
        return None
    return max((at for at in turn_starts(entries) if at <= spoken[-1][0]), default=spoken[-1][0])


def turn_starts(entries: list[dict]) -> list[datetime]:
    """When each turn began, as `turn_start` reads the newest."""
    local = local_commands(entries)
    started = (entry for entry in entries
               if prompted(entry) and entry.get("uuid") not in local and flat(entry.get("message", {}).get("content")))
    ended = (entry for entry in entries if entry.get("type") == "system" and entry.get("subtype") == "turn_duration")
    return [datetime.fromisoformat(entry["timestamp"]) for entry in (*started, *ended) if "timestamp" in entry]


def flat(content: object) -> str:
    """A prompt's text; none for a tool result."""
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return ""
        content = "\n\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return content if isinstance(content, str) else ""


def message_text(content: object) -> str:
    """A prompt as the user typed it: a slash command as `/name args`, pasted text unwrapped."""
    content = flat(content)
    if NOT_SAID.match(content):
        return ""
    if name := re.search(r"<command-name>(.*?)</command-name>", content, re.S):
        args = re.search(r"<command-args>(.*?)</command-args>", content, re.S)
        content = f"{name.group(1)} {args.group(1) if args else ''}"
    return re.sub(r"</?pasted_content\b[^>]*>", "", content).strip()


def name(attributes: str) -> str:
    """Who sent a cross-session message: its `from-name`, which the sender may leave out."""
    m = re.search(r'\bfrom-name="([^"]+)"', attributes)
    return m.group(1) if m else "another session"


WRITES = {"Write", "Edit", "MultiEdit"}  # the tools whose call on a path writes it


def written_at(entries: list[dict], directory: Path, turns: list[Turn]) -> dict[int, datetime]:
    """When each record the transcript shows a write for was written: the earliest tool call that
    wrote its path. A later edit, as a send-back asks for, or a read leaves the time where it was."""
    written: dict[int, datetime] = {}
    names = {t.path.name: t.number for t in turns}
    for at, target in writes(entries):
        if target.parts[-3:-1] == (directory.name, "turns") and target.name in names:
            number = names[target.name]
            written[number] = min(at, written.get(number, at))
    return written


def writes(entries: list[dict]) -> Iterator[tuple[datetime, Path]]:
    """Each tool call in the transcript that writes a file, with when, and the path it wrote."""
    for entry in entries:
        if entry.get("type") != "assistant" or "timestamp" not in entry:
            continue
        for block in entry.get("message", {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in WRITES:
                target = (block.get("input") or {}).get("file_path")
                if isinstance(target, str):
                    yield datetime.fromisoformat(entry["timestamp"]), Path(target)


def pair(messages: list[tuple[datetime, str]], written: list[datetime | None]) -> list[list[str]]:
    """Each record's messages, as `bucket` pairs them. Within a turn, a prompt the next one repeats
    whole and extends past the end of a word, as a resubmission does, is shown as the next
    one; `a` then `also, …` are two messages."""
    return [[m for m, later in zip(turn, turn[1:] + [""]) if not resubmitted(m, later)] for turn in bucket(messages, written)]


def resubmitted(message: str, later: str) -> bool:
    return later.startswith(message) and (len(later) == len(message) or not later[len(message)].isalnum())


T = TypeVar("T")


def bucket(messages: list[tuple[datetime, T]], written: list[datetime | None]) -> list[list[T]]:
    """Each record's messages: the ones said before it was written and after the written record
    before it was. A record with no write time pairs none. A message said after the newest record
    is on no turn until a later record is written."""
    out: list[list[T]] = [[] for _ in written]
    for when, message in messages:
        for i, at in enumerate(written):
            if at is not None and when <= at:
                out[i].append(message)
                break
    return out


# ---- the page ---------------------------------------------------------------

UP = "../" * (len(SESSIONS.parts) + 1)  # from the page to the repo root
ROOT: ContextVar[Path | None] = ContextVar("ROOT", default=None)  # the repo root of the page being rendered
# what a ticket's qualified tag names, in the tracker of the page being rendered (`qualified.resolver`)
NAMES: ContextVar[Callable[[str, str], qualified.Named | None] | None] = ContextVar("NAMES", default=None)

KEYS = [
    ("j k", "next, previous turn"),
    ("o Enter", "open or close the turn"),
    ("O", "open or close every turn"),
    ("g g", "top"),
    ("G", "last turn"),
    ("n", "the newest turn"),
    ("t 0 7", "turn 07, by the number it shows"),
    ("[ ]", "previous, next question"),
    ("q", "show or fold the questions"),
    ("1 to 9", "open the turn's nth artefact"),
    ("y", "copy the turn's markdown, the newest turn's where none is picked"),
    ("Y", "copy the whole session's markdown"),
    ("R", "copy the resume command"),
    ("c", "copy the path under the pointer"),
    ("?", "this list"),
]


def open_questions(session: Session) -> list[tuple[Turn, Question | Cited]]:
    """The questions waiting on the user, with the turn that asked each, oldest first: the session's
    own that no later turn answered or superseded, and each ticket's question its ticket holds open."""
    return [(t, q) for t in session.turns for q in t.questions
            if (q.open if isinstance(q, Cited) else q.tag not in session.settled)]


def page(session: Session, now: datetime) -> str:
    """The session page, with every path a record writes resolved from the session's repo root."""
    root, names = ROOT.set(session.root), NAMES.set(qualified.resolver(session.root / tracker.TICKETS))
    try:
        return assemble(view(session), now)
    finally:
        ROOT.reset(root)
        NAMES.reset(names)


# ---- the page, as values ----------------------------------------------------


@dataclass(frozen=True)
class Shown:
    """A link from a turn's Links as the page shows it."""

    link: Link
    href: str  # where it opens from the page
    artefact: str  # the file or URL it resolves to on this machine, which the hub finds it by; empty for a ticket file
    key: int | None  # the key that opens it among its turn's artefacts, 1 to 9; None for a ticket file and past the ninth


@dataclass(frozen=True)
class Row:
    """A turn as the page shows it, a numbered one or a chat turn."""

    turn: Turn | Chat
    when: str  # its date, with its time to the minute where the transcript has the turn
    open: bool  # the newest numbered turn, the one the page opens
    # What the page says where it shows no message of the user's: that it pairs none, since the
    # transcript shows no write of the record; or, from the newest of a run of turns with none
    # before them, that there was none.
    silence: Literal["", "unwritten", "unanswered"]
    links: tuple[Shown, ...]

    @property
    def key(self) -> str:
        return self.turn.key

    @property
    def artefacts(self) -> tuple[Shown, ...]:
        return tuple(s for s in self.links if s.artefact)


@dataclass(frozen=True)
class View:
    """A session as its page shows it."""

    session: Session
    rows: tuple[Row, ...]  # newest first, each chat turn among the numbered ones by its time
    waiting: tuple[tuple[Turn, Question | Cited], ...]  # open_questions
    span: str  # the dates the turns fall on: one, or the first and the last; empty with no turn
    resume: str  # the command that resumes the session

    @property
    def column(self) -> tuple[Row, ...]:
        """The timeline's rows: the numbered turns, newest first."""
        return tuple(r for r in self.rows if isinstance(r.turn, Turn))


def view(session: Session) -> View:
    timeline = in_order(list(session.turns), list(session.chats))
    shown = list(reversed(timeline))
    newest = max(session.turns, key=lambda t: t.number, default=None)
    hinted = [unanswered(t) and not (newer is not None and unanswered(newer)) for newer, t in zip([None, *shown], shown)]
    rows = tuple(
        Row(t, when(t), t is newest, "unwritten" if t.written is None else "unanswered" if hint else "",
            shown_links(t, session.root) if isinstance(t, Turn) else ())
        for t, hint in zip(shown, hinted))
    dates = sorted({r.when[:10] for r in rows})
    return View(
        session=session,
        rows=rows,
        waiting=tuple(open_questions(session)),
        span="" if not dates else dates[0] if len(dates) == 1 else f"{dates[0]} to {dates[-1]}",
        resume=f"cd {shlex.quote(str(session.repo))} && claude --resume {session.id}",
    )


def shown_links(turn: Turn, root: Path) -> tuple[Shown, ...]:
    """A turn's links, the artefacts among them keyed in order and resolved from `root`."""
    shown, keys = [], itertools.count(1)
    for link in turn.links:
        key = None if link.ticket else next(keys)
        shown.append(Shown(link, href(link.path), "" if link.ticket else resolved(link.path, root),
                           key if key is not None and key <= 9 else None))
    return tuple(shown)


def unanswered(t: Turn | Chat) -> bool:
    """Whether the transcript shows the turn and no message of the user's before it."""
    return t.written is not None and not t.messages


def when(t: Turn | Chat) -> str:
    """The turn's date and time to the minute, from the transcript where it has the turn, which
    keeps the two on one clock; the record's own date where it hasn't."""
    return f"{t.written.astimezone():%Y-%m-%d %H:%M}" if t.written else t.date


# ---- the page, as HTML ------------------------------------------------------


def assemble(v: View, now: datetime) -> str:
    session = v.session
    top = f"""
    <section class="waiting" id="{QUESTIONS}" aria-labelledby="waiting">
      <div class="divider"><h2 class="v-meta" id="waiting">waiting on you · {len(v.waiting)} question{'s' * (len(v.waiting) != 1)}</h2><button class="fold-band v-meta" id="fold-band" aria-expanded="true" aria-keyshortcuts="q">fold <kbd>q</kbd></button></div>
      {''.join((open_cited if isinstance(q, Cited) else open_question)(t, q, folded=i > 0) for i, (t, q) in enumerate(v.waiting))}
    </section>""" if v.waiting else ""
    body = "".join(chat_row(r) if isinstance(r.turn, Chat) else turn_section(r, session.settled) for r in v.rows)
    title = inline(session.title)
    name = (f'<span class="sep">·</span><span class="name" id="session-name" title="the session\'s short name">{esc(session.name)}</span>'
            if session.name else "")
    turns = len(v.rows)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(strip_tags(title))} · session page</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400;1,6..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{TOKENS.read_text()}{(HERE / "page.css").read_text()}</style>
<script>{THEME}</script>
</head>
<body>
<header class="bar">
  <span class="v-meta where"><span title="the repo the session runs in">{esc(session.repo.name)}</span><span class="sep">/</span><button class="id" id="session-id" data-copy="{esc(session.id)}" title="copy the session id: {esc(session.id)}">{esc(session.id[:8])}</button>{name}</span>{newest_control(v.rows)}
  <button class="button sheet-toggle" id="sheet-toggle" aria-controls="{COLUMN}" aria-expanded="false">artefacts · {sum(len(r.artefacts) for r in v.column)}</button>
  <button class="icon" id="keys" aria-label="keyboard shortcuts" aria-keyshortcuts="?"><kbd>?</kbd></button>
  <button class="icon" id="scheme" aria-label="switch to night">
    <svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
  </button>
</header>
<main class="panes">
  <div class="left">
    <section class="intro">
      <h1 class="v-title">{title}</h1>{handoffs(session)}
      <p class="v-meta">{turns} turn{'s' * (turns != 1)} · {f"{esc(v.span)} · " if v.span else ""}<span class="nowrap">rendered {f"{now:%H:%M}" if v.span.endswith(f"{now:%Y-%m-%d}") else f"{now:%Y-%m-%d %H:%M}"}</span> · <button class="resume" id="resume" data-cmd="{esc(v.resume)}" title="copy: {esc(v.resume)}">copy resume command <kbd>R</kbd></button></p>
    </section>{top}
    <div class="pane" id="turns-pane">
      <section class="turns" aria-label="turns">
        {body}
      </section>
    </div>
  </div>{column(v.rows, session)}
</main>
{help_dialog()}
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script type="application/json" id="sources">{sources(v)}</script>
<script>{(HERE / "page.js").read_text()}</script>
</body>
</html>
"""


def sources(v: View) -> str:
    """What the copy keys and buttons copy, as JSON: each turn's record as written, by the id of its block, and under
    `session` its session.md and every record, oldest first. Every `<` is escaped, so nothing a record quotes ends the
    script element the JSON sits in, `</script>` or a comment's opening before a `<script>`."""
    turns = {(f"t{r.key}" if isinstance(r.turn, Turn) else r.key): r.turn.path.read_text() for r in reversed(v.rows)}
    described = v.session.directory / "session.md"
    whole = ([described.read_text()] if described.is_file() else []) + list(turns.values())
    return json.dumps({**turns, "session": "\n\n".join(t.strip() for t in whole) + "\n"}).replace("<", "\\u003c")


def handoffs(session: Session) -> str:
    """The links to the page of the session this one continued from and to each that continued
    from it, as paths from this page to theirs, which resolve on disk and wherever the hub serves the
    sessions directory: a line each under the title, by the session's title where it has one.
    Nothing where neither is there."""
    def line(label: str, other: str) -> str:
        text = inline(session.titles[other], paths=False) if session.titles.get(other) else esc(other[:8])
        return (f'<span class="handoff"><span class="v-meta">{label}</span> '
                f'<a href="../{esc(other)}/{PAGE}" title="{esc(strip_tags(text))} · {esc(other)}">{text}</a></span>')
    lines = ([line("previous", session.previous)] if session.previous else []) + [line("next", s) for s in session.following]
    return f'\n      <p class="handoffs" id="handoffs">{"".join(lines)}</p>' if lines else ""


def column(rows: tuple[Row, ...], session: Session) -> str:
    """The timeline: every turn in the order of the turns beside it. A numbered turn sits under its
    number with its headline, and under that the artefacts it linked; a chat turn is a quiet row of
    its reply's first line. The session that continued this one is at its top, the one it continued
    at its bottom, each a link to that session's page."""
    groups = "".join(chat_group(r) if isinstance(r.turn, Chat) else f"""
    <section class="group{'' if r.artefacts else ' bare'}" id="a{r.key}">
      <a class="v-num turn-ref" href="#t{r.key}">{r.key}</a><div class="tl">{timeline_row(r)}</div>
    </section>""" for r in rows)
    later = "".join(timeline_end(session, "next", s) for s in session.following)
    earlier = timeline_end(session, "previous", session.previous) if session.previous else ""
    return f"""
  <aside class="column" id="{COLUMN}" aria-labelledby="column-title">
    <div class="column-head"><h2 class="v-meta" id="column-title">timeline</h2>{newest_control(rows)}</div>{later}{groups or '<p class="v-meta">no turn yet</p>'}{earlier}
  </aside>"""


CHEVRONS = {"next": "M3 8.5 7 4.5l4 4", "previous": "M3 5.5l4 4 4-4"}


def timeline_end(session: Session, label: str, other: str) -> str:
    """A link at an end of the timeline to the page of a session this one continued or was continued in."""
    title = session.titles.get(other) or other[:8]
    return (f'\n    <a class="tl-end {label}" href="../{esc(other)}/{PAGE}" title="{esc(strip_tags(inline(title)))} · {esc(other)}">'
            f'<svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true"><path d="{CHEVRONS[label]}"/></svg>'
            f'<span class="v-meta">{label}</span> <span class="title">{esc(strip_tags(inline(title)))}</span></a>')


def chat_group(r: Row) -> str:
    """A chat turn in the timeline: its reply's first line, quiet, with no number."""
    first = next((line for line in r.turn.reply.splitlines() if line.strip()), "")
    text = esc(strip_tags(inline(first.strip().lstrip("#-*> ").strip())))
    return f"""
    <section class="group chat" id="a-{r.key}">
      <span class="turn-ref"></span><div class="tl"><a class="hl" href="#{r.key}" tabindex="-1" title="{text}">{text}</a></div>
    </section>"""


def timeline_row(r: Row) -> str:
    """What follows a turn's number in the timeline: its headline, then its artefacts."""
    headline = esc(strip_tags(inline(r.turn.headline)))
    items = "".join(f"<li>{opening_key(s)}{artefact(s, 'artefact')}</li>" for s in r.artefacts)
    return f'<a class="hl" href="#t{r.key}" tabindex="-1" title="{headline}">{headline}</a>' + (f"<ol>{items}</ol>" if items else "")


def newest_control(rows: tuple[Row, ...]) -> str:
    """The control that takes the reader to the newest turn, showing its number, or `chat` for a
    chat turn, which the page marks while a turn has arrived that the reader has not reached. It
    sits in the timeline's head, and in the bar where the timeline is a sheet; nothing where there
    is no turn."""
    if not rows:
        return ""
    label = rows[0].key if isinstance(rows[0].turn, Turn) else "chat"
    return (f'<button class="newest" data-newest aria-keyshortcuts="n" title="the newest turn">'
            f'<span class="dot" aria-hidden="true"></span>newest <span class="v-num">{label}</span><kbd>n</kbd></button>')


def opening_key(s: Shown) -> str:
    """The key that opens a link, where one does."""
    return f'<kbd class="n">{s.key}</kbd>' if s.key else '<span class="n"></span>'


def artefact(s: Shown, cls: str) -> str:
    """A link from a turn's Links, an artefact carrying the path the hub finds it by; a ticket file
    carries none, since the hub marks no ticket."""
    link = s.link
    title = strip_tags(inline(link.text, paths=False)) + (f": {strip_tags(inline(link.note))}" if link.note else "")
    marked = f' {ARTEFACT}="{esc(s.artefact)}"' if s.artefact else ""
    return (f'<a class="{cls}" href="{esc(s.href)}"{marked} target="_blank" '
            f'rel="noopener" title="{esc(title)}">{inline(link.text, paths=False)}</a>')


def open_question(turn: Turn, q: Question, folded: bool) -> str:
    """A question waiting on the user, as a row of the accordion: folded to its headline and the
    words of the option recommended, or open in full, its body scrolling on its own."""
    detail = f'<p class="q-detail">{inline(q.detail)}</p>' if q.detail else ""
    why = f'<p class="why v-small"><span class="v-meta">why</span> {inline(q.why)}</p>' if q.why else ""
    pick = next((o for o in q.options if o.picked), None)
    pickline = f'<p class="pickline"><span class="v-num">{pick.letter}</span> · {esc(strip_tags(inline(pick.text)))}</p>' if pick else ""
    if q.blind:
        # The pick line's place on a folded question, so the test is one click from the band.
        test = Shown(Link("open the blind test", q.blind, ""), href(q.blind), resolved(q.blind, ROOT.get() or Path.cwd()), None)
        pickline = f'<p class="pickline blind">blind · {artefact(test, "link")}</p>'
    return f"""
<article class="q{' folded' if folded else ''}" id="{q.tag.lower()}" tabindex="-1">
  <span class="rail v-num">{q.tag}</span>
  <div class="q-main">
    <h3 class="v-h3">{inline(q.headline)}</h3>{pickline}
    <div class="q-body">
      {detail}{options(q)}{why}
      <p class="v-meta asked-in">asked in <a href="#t{turn.key}">turn {turn.key}</a></p>
    </div>
  </div>
</article>"""


def open_cited(turn: Turn, c: Cited, folded: bool) -> str:
    """A ticket's question waiting on the user, as a row of the same accordion: its headline and
    detail as its ticket words them, and under the headline its handle, a link to the ticket."""
    detail = f'<p class="q-detail">{inline(c.named.detail)}</p>' if c.named and c.named.detail else ""
    return f"""
<article class="q{' folded' if folded else ''}" id="{cited_anchor(c)}" tabindex="-1">
  <span class="rail v-num">{c.tag}</span>
  <div class="q-main">
    <h3 class="v-h3">{inline(c.headline)}</h3><p class="pickline ticket">{ticket_link(c)}</p>
    <div class="q-body">
      {detail}
      <p class="v-meta asked-in">asked in <a href="#t{turn.key}">turn {turn.key}</a> · it clears once its ticket records the ruling</p>
    </div>
  </div>
</article>"""


def cited_anchor(c: Cited) -> str:
    return f"{c.ticket}-{c.tag.lower()}"


def ticket_link(c: Cited) -> str:
    """The question's handle, a link to its ticket with the question as its hover preview; the
    handle alone where the ticket holds the question no longer."""
    if c.named is None:
        return esc(c.handle)
    return qualified_link(esc(c.handle), ticket_path(c.ticket), c.named.preview)


def ticket_path(slug: str) -> str:
    """A ticket file's path from the repo root, which a page's links are written from."""
    return str(tracker.TICKETS / f"{slug}.md")


def qualified_link(text: str, path: str, preview: str) -> str:
    """A qualified tag as a link: to `path`, from the repo root, with what it names as its hover preview."""
    return f'<a class="qualified" href="{esc(href(path))}" target="_blank" rel="noopener" title="{esc(preview)}">{text}</a>'


def options(q: Question, answer: str | None = None) -> str:
    if not q.options:
        return ""
    items = []
    for o in q.options:
        state = "chosen" if answer == o.letter else "passed" if answer else ""
        tags = ('<span class="tag you">your answer</span>' if answer == o.letter else "") + (
            '<span class="tag">my pick</span>' if o.picked else "")
        items.append(f'<li class="{" ".join(c for c in ("pick" if o.picked else "", state) if c)}">'
                     f'<span class="k v-num">{o.letter}</span><span>{inline(o.text)}{tags}</span></li>')
    return f'<ol class="opts">{"".join(items)}</ol>'


def turn_section(r: Row, settled: dict[str, Settled]) -> str:
    t = r.turn
    details = f'<div class="prose details">{block(t.details)}</div>' if t.details else ""
    asked = "".join(asked_cited(q) if isinstance(q, Cited) else asked_question(q, settled[q.tag])
                    for q in t.questions if (not q.open if isinstance(q, Cited) else q.tag in settled))
    asked = f'<div class="asked">{asked}</div>' if asked else ""
    return f"""
<details class="turn blk" id="t{r.key}" data-block{ended(r)}{' open' if r.open else ''}>
  <summary class="head">
    <span class="rail v-num">{r.key}{COPY_TURN}</span>
    <span class="hl v-h3">{inline(t.headline)}</span>
    <span class="v-meta date">{esc(r.when)}</span>{chips(r)}
  </summary>
  <div class="turn-body">
    {you(r)}{"".join(map(peer, t.sent))}{answers(t)}{details}{links(r.links)}{asked}
  </div>
</details>"""


def chat_row(r: Row) -> str:
    """A chat turn: one compact row with no number, the user's messages behind a click and the
    reply as it was, with nothing to open or close."""
    return f"""
<article class="turn chat blk" id="{r.key}" tabindex="-1" data-block{ended(r)}>
  <span class="rail">{COPY_TURN}</span>
  <div class="chat-body">
    {you(r)}{"".join(map(peer, r.turn.sent))}
    <div class="reply"><span class="v-meta who">chat</span><div class="prose">{block(r.turn.reply)}</div></div>
  </div>
  <span class="v-meta date">{esc(r.when)}</span>
</article>"""


def ended(r: Row) -> str:
    """When the turn ended, to the second, as the transcript has it: the hub reads it to tell that a message it typed
    into the session was taken up by a turn the page shows. Nothing where the transcript has no time for the turn."""
    return f' data-at="{r.turn.written.astimezone().isoformat(timespec="seconds")}"' if r.turn.written else ""


def chips(r: Row) -> str:
    """The turn's artefacts on its summary line, which is what shows of a collapsed turn."""
    if not r.artefacts:
        return ""
    return ('<span class="chips">' + "".join(
        f'<span class="chip">{opening_key(s)}{artefact(s, "chip-link")}</span>' for s in r.artefacts) + "</span>")


SILENCES = {
    "unwritten": "no message of yours paired, since the transcript shows no Write call for this turn's record",
    "unanswered": "no message of yours in the transcript before this turn",
}


def you(r: Row) -> str:
    """The user's messages, under "you", or what the page says where it shows none."""
    if r.silence:
        return f'<p class="v-meta you-none">{SILENCES[r.silence]}</p>'
    messages = r.turn.messages
    if not messages:
        return ""
    lead = f"{len(messages)} messages · " if len(messages) > 1 else ""
    return message_block("said you", "you", messages, lead)


def peer(s: Sent) -> str:
    """A message another session sent, behind one click, under that session's name."""
    return message_block("said peer", s.name, (s.text,), "another session · ")


def message_block(cls: str, who: str, messages: tuple[str, ...], lead: str) -> str:
    """Messages behind one click, each whole, its paragraphs and line breaks kept."""
    words = sum(len(m.split()) for m in messages)
    parts = "".join(
        '<div class="msg">' + "".join(f"<p>{esc(p.strip()).replace(chr(10), '<br>')}</p>"
                                      for p in re.split(r"\n[ \t]*\n+", m) if p.strip()) + "</div>"
        for m in messages)
    return f"""
<details class="{cls}">
  <summary><span class="v-meta who">{esc(who)}</span><span class="preview">{esc(" ".join(messages[0].split()))}</span><span class="v-meta count">{lead}{words:,} words</span></summary>
  <div class="said-text">{parts}</div>
</details>"""


def answers(t: Turn) -> str:
    """What this turn settled: the user's answers, then the questions it replaced."""
    answered = ", ".join(f'<a href="#{tag.lower()}">{tag}</a> {esc(value)}' for tag, value in t.answered.items())
    replaced = [f'<a href="#{old.lower()}">{old}</a> replaced by <a href="#{new.lower()}">{new}</a>' for old, new in t.superseded.items()]
    bits = ([f"your answers {answered}"] if answered else []) + replaced
    return f'<p class="v-meta answers">{" · ".join(bits)}</p>' if bits else ""


def links(items: tuple[Shown, ...]) -> str:
    if not items:
        return ""
    rows = []
    for s in items:
        note = f'<span class="desc v-small">{inline(s.link.note)}</span>' if s.link.note else ""
        rows.append(f'<li>{opening_key(s)}<span class="link-main">{artefact(s, "link")}{note}</span></li>')
    return f'<ol class="links">{"".join(rows)}</ol>'


def asked_question(q: Question, how: Settled) -> str:
    anchor = f'id="{q.tag.lower()}"'
    if how.how == "superseded":
        return (f'<div class="aq superseded" {anchor}><span class="k v-num">{q.tag}</span><div><p class="aq-h">{inline(q.headline)}</p>'
                f'<p class="v-meta">replaced by <a href="#{how.value.lower()}">{how.value}</a> in turn {how.turn:02d}</p></div></div>')
    letter = how.value if any(o.letter == how.value for o in q.options) else None
    free = "" if letter else f'<p class="v-small free"><span class="v-meta">your answer</span> {esc(how.value)}</p>'
    return f"""
<div class="aq answered" {anchor}>
  <span class="k v-num">{q.tag}</span>
  <div>
    <p class="aq-h">{inline(q.headline)}</p>
    {options(q, letter)}{free}
    <p class="v-meta">answered in <a href="#t{how.turn:02d}">turn {how.turn:02d}</a></p>
  </div>
</div>"""


def asked_cited(c: Cited) -> str:
    """A ticket's question this turn put to the user that waits no longer: its ruling, as the ticket
    records it, or that the ticket holds it no more."""
    if c.named is None:
        said = f'<p class="v-meta">{esc(c.handle)} is no longer a question of its ticket</p>'
    else:
        said = (f'<p class="v-small free"><span class="v-meta">ruling</span> {inline(c.named.answer)}</p>'
                f'<p class="v-meta">ruled {esc(c.named.ruled)} in {ticket_link(c)}</p>')
    return f"""
<div class="aq answered" id="{cited_anchor(c)}">
  <span class="k v-num">{c.tag}</span>
  <div>
    <p class="aq-h">{inline(c.headline)}</p>
    {said}
  </div>
</div>"""


def help_dialog() -> str:
    key = lambda k: '<span class="v-meta">to</span>' if k == "to" else f"<kbd>{esc(k)}</kbd>"
    rows = "".join(f"<tr><td>{' '.join(map(key, combo.split()))}</td><td>{esc(what)}</td></tr>" for combo, what in KEYS)
    return f"""<div class="help" id="help" role="dialog" aria-modal="true" aria-labelledby="help-title" hidden>
  <div class="card">
    <p class="v-h3" id="help-title">Keys</p>
    <table>{rows}</table>
    <p class="v-meta">the same keys as diffview, where diffview has one</p>
  </div>
</div>"""


THEME = """
(() => {
  const t = new URLSearchParams(location.search).get("theme")
  const night = t ? t === "night" : matchMedia("(prefers-color-scheme: dark)").matches
  document.documentElement.dataset.theme = night ? "night" : "day"
})()
"""


# ---- markdown ---------------------------------------------------------------


def block(text: str) -> str:
    """A record's markdown as HTML: CommonMark with tables, raw HTML shown as text, links resolved
    from the repo root and opening in a tab of their own, and a code span naming a path on this machine
    made a link to it."""
    return MARKDOWN.render(text)


def inline(text: str, paths: bool = True) -> str:
    """Markdown as one line of HTML: a headline carries code and emphasis, never a block. Text
    that will sit inside a link of its own passes `paths=False`, since a link cannot hold one."""
    return MARKDOWN.renderInline(text, {"paths": paths})


def link_open(self, tokens, idx, options, env) -> str:
    token = tokens[idx]
    target = token.attrGet("href") or ""
    if not target.startswith("#"):
        token.attrSet("href", href(target))
        token.attrSet("target", "_blank")
        token.attrSet("rel", "noopener")
    return self.renderToken(tokens, idx, options, env)


def code_inline(self, tokens, idx, options, env) -> str:
    code = CODE_INLINE(tokens, idx, options, env)
    in_link = sum((t.type == "link_open") - (t.type == "link_close") for t in tokens[:idx]) > 0
    target = None if in_link or not env.get("paths", True) else path_target(tokens[idx].content)
    return f'<a class="path" href="{esc(target)}" target="_blank" rel="noopener">{code}</a>' if target else code


COPY_ICON = (
    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" '
    'stroke-linejoin="round" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
    '<path d="M10.5 5.5V3.5a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2"/></svg>'
)
COPY_CODE = f'<button class="copy-code" type="button" aria-label="copy the code" title="copy">{COPY_ICON}</button>'
# Under a turn's number: copies the turn's record, as `y` does with the cursor on the turn. Out of the Tab order,
# which goes from turn to turn.
COPY_TURN = (f'<button class="copy-turn" type="button" tabindex="-1" aria-label="copy the turn\'s markdown" '
             f'title="copy the turn\'s markdown (y)">{COPY_ICON}</button>')


def with_copy(rule: Callable):
    """A code block's render rule, its block in a box that also holds the button copying it."""
    return lambda self, tokens, idx, options, env: f'<div class="code">{rule(tokens, idx, options, env)}{COPY_CODE}</div>\n'


def links_in_text(state) -> None:
    """A bare URL in the text made a link, short of text that sits inside a link of its own. Only
    a URL with its scheme: fuzzy matching would take `session_page.py` for a domain in Paraguay.
    markdown-it finds them twice, while it parses a line and after, so both of its rules ask."""
    if state.env.get("paths", True):
        linkify(state)


def links_in_line(state, silent: bool) -> bool:
    return state.env.get("paths", True) and linkify_inline(state, silent)


# Another session's question, qualified by the first eight characters of that session's id, as its
# page's bar shows them: `e5ca76dc Q3`.
SESSION_QUESTION = re.compile(r"(?<![\w/.-])([0-9a-f]{8}) (Q\d+)\b")
TAGGED = re.compile(f"{qualified.QUALIFIED.pattern}|{SESSION_QUESTION.pattern}")
# What follows a ticket's slug, or a session's id, written as code: `` `<ticket>` D6 ``.
TAG_AFTER = re.compile(r"[ #][DPAQ]\d+\b")


def qualified_tags(state) -> None:
    """Each qualified tag in a record's text made a link to what it names, with that as its hover
    preview: a ticket's `<ticket> D6` (a question or a detail entry), `P3` or `A21`, and another
    session's `<session> Q3`. The ticket's slug may be code. Text that names nothing stays text, and
    so does text that sits inside a link."""
    if state.env.get("paths", True) and ROOT.get() is not None:
        for token in state.tokens:
            if token.type == "inline" and token.children:
                token.children = tagged(token.children)


def tagged(children: list[Token]) -> list[Token]:
    out: list[Token] = []
    depth = 0
    for i, token in enumerate(children):
        depth += (token.type == "link_open") - (token.type == "link_close")
        after = children[i + 1] if i + 1 < len(children) else None
        if depth or token.type not in ("text", "code_inline"):
            out.append(token)
        elif token.type == "text":
            out += split_tags(token.content)
        elif (whole := named_by(TAGGED.fullmatch(token.content))) is not None:
            out += linked(whole, [token])
        elif (after is not None and after.type == "text" and (tail := TAG_AFTER.match(after.content))
              and (found := named_by(TAGGED.fullmatch(token.content + tail.group()))) is not None):
            out += linked(found, [token, Token("text", "", 0, content=tail.group())])
            after.content = after.content[tail.end():]
        else:
            out.append(token)
    return out


def split_tags(text: str) -> list[Token]:
    out, at = [], 0
    for m in TAGGED.finditer(text):
        if (found := named_by(m)) is not None:
            out += [Token("text", "", 0, content=text[at:m.start()])] + linked(found, [Token("text", "", 0, content=m.group())])
            at = m.end()
    return out + [Token("text", "", 0, content=text[at:])]


def linked(found: tuple[str, str], inner: list[Token]) -> list[Token]:
    path, preview = found
    return [Token("link_open", "a", 1, attrs={"href": path, "title": preview, "class": "qualified"}),
            *inner, Token("link_close", "a", -1)]


def named_by(m: re.Match | None) -> tuple[str, str] | None:
    """Where a qualified tag's link goes, from the repo root, and its hover preview; None where it
    names nothing."""
    if m is None:
        return None
    if m.group(1):
        found = (NAMES.get() or (lambda slug, tag: None))(m.group(1), m.group(2))
        return (ticket_path(found.ticket), found.preview) if found else None
    return session_question(m.group(3), m.group(4))


def session_question(prefix: str, tag: str) -> tuple[str, str] | None:
    """Another session's question by the first eight characters of its id: the link to it on that
    session's page, and its headline with how it left the top, where it did. None where no one
    session with a page has that prefix, or that session asked no such question."""
    root = ROOT.get()
    found = [d for d in (root / SESSIONS).glob(f"{prefix}*") if (d / PAGE).is_file()] if root else []
    if len(found) != 1:
        return None
    try:
        turns = read_turns(found[0] / "turns")
        settled = settle(turns)
    except RecordError:
        return None
    asked = next((q for t in turns for q in t.questions if q.handle == tag), None)
    if asked is None:
        return None
    how = settled.get(tag)
    state = "" if how is None else f" · answered {how.value}" if how.how == "answered" else f" · replaced by {how.value}"
    return f"{SESSIONS / found[0].name / PAGE}#{tag.lower()}", f"{prefix} {tag} · {asked.headline}{state}"


def file_links_too(url: str) -> bool:
    """markdown-it's check of a link's target, short of its ban on `file:`: a reply links a file on
    this machine that way, the PDF in `~/Downloads` say, and the page is the reader's own."""
    return url.strip().lower().startswith("file:") or validateLink(url)


MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": True}).enable(["table", "linkify", "strikethrough"])
MARKDOWN.linkify.set({"fuzzy_link": False, "fuzzy_email": False})
MARKDOWN.core.ruler.at("linkify", links_in_text)
MARKDOWN.inline.ruler.at("linkify", links_in_line)
MARKDOWN.core.ruler.push("qualified_tags", qualified_tags)
MARKDOWN.validateLink = file_links_too
CODE_INLINE = MARKDOWN.renderer.rules["code_inline"]
MARKDOWN.add_render_rule("link_open", link_open)
MARKDOWN.add_render_rule("code_inline", code_inline)
for rule in ("fence", "code_block"):
    MARKDOWN.add_render_rule(rule, with_copy(MARKDOWN.renderer.rules[rule]))


URL = re.compile(r"[a-z][a-z0-9+.-]*:", re.I)


def href(path: str) -> str:
    """A link from the page: a path from the repo root climbs to it, an absolute or `~` path is
    its file URL, and a URL stays as it is."""
    if URL.match(path):
        return path
    local = expanded(path)
    return local.as_uri() if local.is_absolute() else UP + path


def resolved(path: str, root: Path) -> str:
    """The file a link opens on this machine, a fragment or query dropped: a path from the repo root
    joined to `root`, an absolute or `~` path as it is; a URL as it is."""
    if URL.match(path):
        return path
    local = expanded(file_part(path))
    return os.path.normpath(local if local.is_absolute() else root / local)


def file_part(path: str) -> str:
    """A link's path short of its fragment or query: the file it points at."""
    return re.split(r"[#?]", path)[0]


def expanded(path: str) -> Path:
    """`path` with a leading `~` made the home directory. `~name` stays as written: in a record it
    is more often text such as a package version (`~ubuntu.26.04~resolute`) than another user's
    home, and pathlib raises on a user it cannot find."""
    return Path(path).expanduser() if re.match(r"~(/|$)", path) else Path(path)


def path_target(text: str) -> str | None:
    """The link for a code span whose text is a path that exists on this machine: absolute, under
    `~`, or from the repo root, a trailing `:line` or `:line:column` dropped. None for anything
    else, so a command, a name or a path on another host stays code. A bare word is never a path,
    even where the repo root holds a directory of that name."""
    root = ROOT.get()
    path = re.sub(r":\d+(?::\d+)?$", "", text.strip())
    if root is None or re.search(r"\s", path) or not ("/" in path or Path(path).suffix):
        return None
    local = expanded(path)
    try:
        found = (local if local.is_absolute() else root / local).exists()
    except OSError:  # a name too long for the filesystem
        return None
    return href(path) if found else None


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s))


if __name__ == "__main__":
    main()
