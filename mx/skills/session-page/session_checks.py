"""What the session page's checks share beside their fixtures: the worked example's session,
the markers of a session nobody is sitting at, a turn that wrote no record, a reviewer no check may
reach, sessions drawn as data with the records they are written as, the page as the values it
formats and its HTML read back by anchor, and the hooks' payloads and cases.

They live here rather than in `conftest.py` because a check that imports from `conftest` gets
whichever conftest Python loaded last under that name, and the tracker's checks keep one too."""

import html
import itertools
import json
import re
import urllib.parse
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
from hypothesis import strategies as st

from session_page import Row, View, account, agent_repo_of, read_session, view

SESSION = "e5ca76dc-3093-419b-aa93-b8eb8f35811f"  # the session the worked example is of
# the sessions the hooks leave alone are marked in the environment, and the suite runs in one of
# them whenever a dispatched worker verifies its branch
UNATTENDED = ("DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED")

# The worked example's transcript ends with record 4's Write call, after the last prompt: that
# turn wrote its record. A prompt after it, with the records last touched before it, is a turn
# that wrote none.
SPOKEN_AFTER = {"type": "user", "message": {"role": "user", "content": "And the ledger's second bank?"},
                "timestamp": "2026-09-23T01:35:00.000Z"}
BEFORE_IT = datetime(2026, 9, 23, 1, 31, tzinfo=UTC).timestamp()


def unreachable(system: str, prompt: str) -> list[dict]:
    """A reviewer stand-in for a check where no model call may be made. It fails the check through
    `pytest.fail`, which the review's fail-open handler does not catch."""
    pytest.fail("the reviewer was called where no model call may be made")


# ---- sessions drawn as data ------------------------------------------------


DRAWN = "00000000-0000-0000-0000-000000000000"  # the session id a drawn session carries
# The tickets whose questions a drawn session puts to the user. Each numbers its own from D1, so a
# session that asks of both holds two questions tagged alike, told apart by their ticket alone.
DRAWN_TICKETS = ("drawn-ticket", "other-ticket")


@st.composite
def sessions(draw: st.DrawFn) -> tuple[list[dict], set[str]]:
    """A session's turns as data, and the questions open at the end of it, by the handle the page
    shows each by: `Q3` for the session's own, `drawn-ticket D2` for a ticket's.

    Each turn draws a fate for every question still open before it (left alone, answered with an
    option's letter or with the user's own words, or superseded by one this turn asks) and then
    asks questions of its own, and may put one of a ticket's to the user, which its ticket has
    ruled on by the session's end or not (`write_tickets`).
    """
    turns: list[dict] = []
    open_tags: list[str] = []
    open_in_ticket: list[str] = []  # which clear through their ticket, never through a turn
    tags = itertools.count(1)
    ticket_tags = {slug: itertools.count(1) for slug in DRAWN_TICKETS}
    for _ in range(draw(st.integers(min_value=1, max_value=5))):
        turn: dict = {"asks": [], "answered": {}, "superseded": {}, "cites": {}}
        for tag in list(open_tags):
            fate = draw(st.sampled_from(["open", "answered", "superseded"]))
            if fate == "answered":
                turn["answered"][tag] = draw(st.sampled_from(["a", "b", "neither: split it in two"]))
                open_tags.remove(tag)
            elif fate == "superseded":
                replacement = f"Q{next(tags)}"
                turn["superseded"][tag] = replacement
                turn["asks"].append(replacement)
                open_tags[open_tags.index(tag)] = replacement
        for _ in range(draw(st.integers(min_value=0, max_value=2))):
            tag = f"Q{next(tags)}"
            turn["asks"].append(tag)
            open_tags.append(tag)
        for slug in draw(st.lists(st.sampled_from(DRAWN_TICKETS), max_size=2, unique=True)):
            handle = f"{slug} D{next(ticket_tags[slug])}"
            turn["cites"][handle] = ruled = draw(st.booleans())
            if not ruled:
                open_in_ticket.append(handle)
        turns.append(turn)
    return turns, {*open_tags, *open_in_ticket}


def asked_in_order(turns: list[dict]) -> list[str]:
    """Every question a drawn session asks, by its handle, in the order its records ask them."""
    return [handle for turn in turns for handle in [*turn["asks"], *turn.get("cites", {})]]


def write_tickets(root: Path, turns: list[dict]) -> None:
    """The tickets holding every question the drawn session's turns put to the user, in the tracker
    of the project at `root`, a `Ruled` line under each the draw ruled on."""
    (root / "agent" / "tickets").mkdir(parents=True, exist_ok=True)
    for slug in DRAWN_TICKETS:
        asked = []
        for handle, ruled in (item for turn in turns for item in turn.get("cites", {}).items()):
            if handle.split()[0] == slug:
                asked.append(f"- [{handle.split()[1]}] **What about {handle}?** What hangs on it.")
                asked += ["  - Ruled 2026-09-30: one way."] if ruled else []
        (root / "agent" / "tickets" / f"{slug}.md").write_text(
            f"---\nstatus: open\n---\n\n# {slug}\n\n## Brief\n\nWhat a drawn session puts to the user.\n\n"
            "## Acceptance criteria\n\n- [ ] It asks.\n\n## Questions\n\n" + "\n".join(asked) + "\n")


def record(number: int, turn: dict, headline: str = "", details: str = "") -> str:
    """One `turns/NN.md` in the shape the Decisions give it: frontmatter for what the renderer
    reads as data, an H1, and the sections the turn has."""
    front = [f"date: 2026-09-{20 + number:02d}"]
    for name in ("answered", "superseded"):
        if turn[name]:
            front.append(f"{name}:")
            front += [f"  {tag}: {json.dumps(value)}" for tag, value in turn[name].items()]
    body = [f"# {headline or f'Round {number}'}"]
    if turn["asks"] or turn.get("cites"):
        body += ["", "## Questions", ""]
        for tag in turn["asks"]:
            body += [
                f"- [{tag}] **What about {tag}?** What hangs on it.",
                "  - (a) One way. *my pick*",
                "  - (b) The other way.",
            ]
        body += [f"- [{handle}]" for handle in turn.get("cites", {})]
    body += ["", "## Details", "", details or f"What turn {number} settled."]
    return "---\n" + "\n".join(front) + "\n---\n\n" + "\n".join(body) + "\n"


# ---- the page, read back ----------------------------------------------------


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def elements(page: str, pattern: str) -> dict[str, str]:
    """Each element of the page whose id `pattern` matches, whole, keyed by that id: a block is
    read by the anchor that names it, not by where the next one starts, so anything nested inside
    it stays part of it."""
    starts = list(itertools.accumulate((len(line) for line in page.splitlines(keepends=True)), initial=0))
    found: dict[str, str] = {}
    open_tags: list[tuple[str, str | None, int]] = []

    class Reader(HTMLParser):
        def at(self) -> int:
            line, column = self.getpos()
            return starts[line - 1] + column

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in VOID:
                return
            value = dict(attrs).get("id")
            open_tags.append((tag, value if value and re.fullmatch(pattern, value) else None, self.at()))

        def handle_endtag(self, tag: str) -> None:
            while open_tags:
                name, value, start = open_tags.pop()
                if name == tag:
                    if value:
                        found[value] = page[start : self.at() + len(f"</{tag}>")]
                    return

    Reader().feed(page)
    return found


def anchors(fragment: str) -> list[tuple[dict[str, str], str]]:
    """Every link in a fragment of the page: its attributes, in whatever order the page writes
    them, and its text, both unescaped."""
    found: list[tuple[dict[str, str], list[str]]] = []

    class Reader(HTMLParser):
        depth = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "a":
                found.append(({k: v or "" for k, v in attrs}, []))
                self.depth += 1

        def handle_endtag(self, tag: str) -> None:
            self.depth -= tag == "a"

        def handle_data(self, data: str) -> None:
            if self.depth:
                found[-1][1].append(data)

    Reader().feed(fragment)
    return [(attrs, "".join(text)) for attrs, text in found]


def sections_of(page: str) -> dict[str, str]:
    """Each turn's section, keyed by the two digits of its record."""
    return {anchor[1:]: section for anchor, section in elements(page, r"t\d+").items()}


def text_of(fragment: str) -> str:
    """A fragment of the page as its reader reads it: the text, tags dropped, entities read and
    whitespace run together."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


TURN_ANCHOR = r"t\d+|chat-\d{8}T\d{6}Z"  # the anchor a turn is reached by: `t04`, or a chat turn's name


def turns_on(page: str) -> dict[str, str]:
    """Each turn on the page as text, by its TURN_ANCHOR."""
    return {anchor: text_of(turn) for anchor, turn in elements(page, TURN_ANCHOR).items()}


def view_of(directory: Path, transcript: Path) -> View:
    """The page `render_session` renders for the session, as the values it formats."""
    return view(read_session(directory, transcript))


def rows_of(page: View) -> dict[str, Row]:
    """Each turn the page shows, by the two digits of its record or a chat turn's name."""
    return {row.key: row for row in page.rows}


def messages_of(page: View) -> dict[str, list[str]]:
    """Each turn's messages from the user, by the two digits of its record or a chat turn's name."""
    return {row.key: list(row.turn.messages) for row in page.rows}


# ---- the hooks' payloads and cases ---------------------------------------------


def followed(href: str) -> Path:
    """The file a link on the page opens, from its file URL."""
    parts = urllib.parse.urlsplit(href)
    assert parts.scheme == "file", f"{href} is no file URL"
    return Path(urllib.parse.unquote(parts.path))


def project_of(directory: Path) -> Path:
    """The project a session's directory belongs to, as a hook payload's working directory: the repo
    its agent repo sits in. One the hook has not made yet belongs to the check's own project, which
    holds the check's account (conftest's `registry`)."""
    agent = agent_repo_of(directory)
    return agent.parent if agent else account().parent


def payload(directory: Path, transcript: Path, reply: str = "", **rest: object) -> dict:
    """The Stop hook JSON for a turn of the session whose directory is `directory`."""
    return {
        "session_id": directory.name,
        "cwd": str(project_of(directory)),
        "transcript_path": str(transcript),
        "stop_hook_active": False,
        "last_assistant_message": reply,
        **rest,
    }


# A clause asking the recap to name or list questions, as the recap rule once did: "each open
# question named by what it decides". A send-back's own wording is its last line, under the
# reader's error or the review's findings it carries.
LISTS_A_QUESTION = re.compile(r"\b(?:each|every|name|names|named|list|lists)\b[^;]*\bquestions?\b")


def logged(log: Path, key: str) -> list[dict]:
    """The log's lines that carry `key`: `decision` the review's, `verb` the hook's."""
    lines = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return [entry for entry in lines if key in entry]


# A reply of several lines, an answer that would fill a turn record.
LONG = "\n".join(f"Line {n} of an answer that belongs on the page." for n in range(1, 6))

LEFT_ALONE = {"a dispatched worker": ("DISPATCH_WORKLOG", "/w/log"), "a print-mode session": ("CLAUDE_CODE_SESSION_ATTENDED", "0")}

# The record the turn just wrote is 04.md, the one the Decisions have the hook validate; 03.md is
# two rounds back, and a hook that read only the newest record would let it through. Each case is
# what the record says and the line the hook names, None where the shape says only that something
# is missing and not where.
ROUND_3 = "---\ndate: 2026-09-23\n---\n\n# Round 3\n\n"  # lines 1 to 6; the section's first item is line 9

UNPARSEABLE = {
    "frontmatter that is not YAML": (
        "04.md", "---\ndate: 2026-09-23\nanswered: Q1: a\n---\n\n# Round 3\n\n## Details\n\nThe round.\n", 3),
    "frontmatter that is not a mapping": (
        "04.md", "---\n- a\n- b\n---\n\n# Round 3\n\n## Details\n\nThe round.\n", 2),
    "a question that is not a question item": (
        "04.md", "---\ndate: 2026-09-23\n---\n\n# Round 3\n\n## Questions\n\n- Q7: what reviews the prose?\n", 9),
    "a section the record's shape does not have": (
        "04.md", "---\ndate: 2026-09-23\n---\n\n# Round 3\n\n## Notes\n\nA fourth section.\n", 7),
    "no headline": ("04.md", "---\ndate: 2026-09-23\n---\n\n## Details\n\nThe round.\n", None),
    "a record from an earlier turn": (
        "03.md", "---\ndate: 2026-09-23\n---\n\n# Round 2\n\n## Notes\n\nA fourth section.\n", 7),
    "a question with one option": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review. *my pick*\n", 9),
    "a question with no pick": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review.\n  - (b) None.\n", 9),
    "a question with two picks": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review. *my pick*\n"
                 "  - (b) None. *my pick*\n", 9),
    "an option letter twice": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review. *my pick*\n  - (a) None.\n", 9),
    "a second Why": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - (a) A light review. *my pick*\n  - (b) None.\n"
                 "  - Why: seconds.\n  - Why: again.\n", 13),
    "a block at the question's indent after its options": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **Post this reply?**\n  - (a) As written below. *my pick*\n  - (b) With your changes.\n"
                 "\n  > Done across the stack.\n", 13),
    "a blind question that also offers options": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - Blind: agent/show/r/blind-q7.html\n"
                 "  - (a) A light review. *my pick*\n  - (b) None.\n", 9),
    "a question an earlier turn asked": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q1] **One feature or two?**\n  - (a) Two. *my pick*\n  - (b) One.\n", None),
    "a link that climbs out of the repo": ("04.md", f"{ROUND_3}## Links\n\n- [The round](../round.html): it\n", 9),
    "a link item that is no link": ("04.md", f"{ROUND_3}## Links\n\n- the round's page\n", 9),
}


# A ticket's question written the way only the session's own are, each with the line the reader
# names and the words that tell the agent the question lives in its ticket.
TICKET_QUESTION_UNPARSEABLE = {
    "a ticket's question with words of its own": (
        f"{ROUND_3}## Questions\n\n- [two-main-checkouts D5] **Sync on every commit?**\n", 9, "whose words live in its ticket"),
    "a ticket's question with options": (
        f"{ROUND_3}## Questions\n\n- [two-main-checkouts D5]\n  - (a) On every commit. *my pick*\n", 10, "live in its ticket, not here"),
    "a ticket's question cleared by a turn": (
        "---\ndate: 2026-09-23\nanswered:\n  two-main-checkouts D5: a\n---\n\n# Round 3\n\n## Details\n\nThe round.\n", 4,
        "once its ticket records the ruling (`tracker rule`)"),
}


def with_write(transcript: Path, tool: str, record: Path) -> None:
    """Append to the transcript the turn's `tool` call on `record`, a minute after SPOKEN_AFTER."""
    call = {"type": "tool_use", "id": f"toolu_{tool}_{record.stem}", "name": tool, "input": {"file_path": str(record)}}
    entry = {"type": "assistant", "message": {"role": "assistant", "content": [call]}, "timestamp": "2026-09-23T01:36:00.000Z"}
    transcript.write_text(transcript.read_text() + json.dumps(entry) + "\n")


# Prompts Claude Code starts a turn on without the user typing, at SPOKEN_AFTER's time, shaped as
# Claude Code writes them: a background task finishing; a subagent handing its report back and
# another session's message, both meta lines; and a scheduled prompt (a /loop or cron wakeup), a
# meta line with no origin, which only the end of the turn before it marks as a turn of its own.
TASK_DONE = {"type": "user", "origin": {"kind": "task-notification"}, "timestamp": SPOKEN_AFTER["timestamp"],
             "message": {"role": "user", "content": "<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>\n</task-notification>"}}

HANDED_BACK = {"type": "user", "isMeta": True, "origin": {"kind": "peer", "from": "a1", "handback": True},
               "timestamp": SPOKEN_AFTER["timestamp"],
               "message": {"role": "user", "content": 'Another Claude session sent a message:\n<agent-message from="a1">\n'
                                                      "[Subagent hand-back] The figure is built.\n</agent-message>"}}

PEER_SENT = {"type": "user", "isMeta": True, "origin": {"kind": "peer", "from": "uds:/run/user/1000/cc-socks/77.sock", "name": "agents-d2"},
             "timestamp": SPOKEN_AFTER["timestamp"],
             "message": {"role": "user", "content": 'Another Claude session sent a message:\n<cross-session-message '
                                                    'from="uds:/run/user/1000/cc-socks/77.sock" from-name="agents-d2" from-mode="prompting">\n'
                                                    "Is fix-381 the right base?\n</cross-session-message>"}}

TURN_ENDED = {"type": "system", "subtype": "turn_duration", "isMeta": False, "durationMs": 1000, "timestamp": "2026-09-23T01:34:00.000Z"}
WOKEN = {"type": "user", "isMeta": True, "timestamp": SPOKEN_AFTER["timestamp"],
         "message": {"role": "user", "content": "Check the run and report."}}

TURN_STARTS = {"a finished task": (TASK_DONE,), "a subagent's hand-back": (HANDED_BACK,),
               "another session's message": (PEER_SENT,), "a scheduled prompt": (TURN_ENDED, WOKEN)}


def appended(transcript: Path, out: Path, *entries: dict) -> Path:
    out.write_text(transcript.read_text() + "".join(json.dumps(e) + "\n" for e in entries))
    return out


CATALOGUE_FIXTURE = """# Tells

Prose about the tags.

## Content

- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `51` `artifact` **A rule for files only.** Dropped.

## Style

- `13` `chat` **A rule for replies.** Kept.
"""

RULES_FIXTURE = """# The session page

Prose before the shape.

## The turn record

The shape's prose.

```markdown
---
date: 2026-09-28
---

# A headline inside the example

## Details

The example's own section.
```

- A rule about the record.

## Another section

After the shape.
"""
