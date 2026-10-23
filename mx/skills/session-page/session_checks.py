"""What the session page's checks share beside their fixtures: the worked example's session,
the markers of a session nobody is sitting at, a turn that wrote no record, a reviewer no check may
reach, the page as the values it formats and its HTML read back by anchor, and the hooks' payloads
and cases.

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

from session_page import Row, View, agent_repo_of, read_session, view

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
    """The project a session's directory belongs to: the repo its agent repo sits in. One the hook
    has not made yet belongs to the check's own project, which sits beside the check's account
    (conftest's `registry`)."""
    agent = agent_repo_of(directory)
    return agent.parent if agent else directory.parents[2]


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
    "a blind question that also offers options": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q7] **What reviews the prose?**\n  - Blind: agent/show/r/blind-q7.html\n"
                 "  - (a) A light review. *my pick*\n  - (b) None.\n", 9),
    "a question an earlier turn asked": (
        "04.md", f"{ROUND_3}## Questions\n\n- [Q1] **One feature or two?**\n  - (a) Two. *my pick*\n  - (b) One.\n", None),
    "a link that climbs out of the repo": ("04.md", f"{ROUND_3}## Links\n\n- [The round](../round.html): it\n", 9),
    "a link item that is no link": ("04.md", f"{ROUND_3}## Links\n\n- the round's page\n", 9),
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
