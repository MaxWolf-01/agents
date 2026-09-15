# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for the chat reviewer's three readings. Run: uv run test_chat_review.py

The seams are the scope selection (catalogue text in, the chat-scoped rule blocks out), the
answer parse (a model's answer in, hits out) and the decision `main` reaches (a hook payload and
an environment in, a log line and the turn's continuation out). The oracle for the selection is
the awk command CATALOGUE.md's header publishes as its format contract: this test runs that
command and demands the same bytes, so the header and the script cannot drift apart, and a
catalogue whose bullets stop matching fails here rather than turning every reply clean. The
answer parse is held to the hook's fail-open rule: drop what cannot be formatted, raise only
where the caller still catches. The decisions are the module docstring's own list, and the log
is where the spec reads them: it defers the residue ruling to a week of that file.
"""

import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import chat_review
from chat_review import CATALOGUE, chat_rules, hits_from

SKIP_MARKERS = ("CHAT_REVIEW_NESTED", "CHAT_REVIEW_OFF", "DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED")

FIXTURE = """# Tells

Prose about the tags.

## Content

- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `51` `artifact` **A rule for files only.** Dropped.

## Style

- `13` `chat` **A rule for replies.** Kept.
"""


def awk_selection() -> str:
    """The header's own command, run on the real catalogue."""
    program = re.search(r"awk '(.+?)' CATALOGUE\.md", CATALOGUE.read_text()).group(1)
    run = subprocess.run(["awk", program, CATALOGUE], capture_output=True, text=True, check=True)
    return run.stdout.rstrip("\n")


def test_selection_is_the_one_the_catalogue_documents() -> None:
    assert chat_rules(CATALOGUE.read_text()) == awk_selection()


def test_selected_blocks_come_whole() -> None:
    assert chat_rules(FIXTURE).splitlines() == [
        "- `3` `both` **A rule.** Its first line.",
        '  Before: "indented continuation". After: "rides with its rule".',
        "",
        "- `13` `chat` **A rule for replies.** Kept.",
    ]


def test_a_catalogue_with_no_chat_rules_raises() -> None:
    with pytest.raises(RuntimeError):
        chat_rules(FIXTURE.replace("`both`", "`artifact`").replace("`chat`", "`artifact`"))


def test_hits_are_read_out_of_surrounding_prose() -> None:
    hit = {"rule": "13", "quote": "a dash", "fix": "a period"}
    assert hits_from('Here you go: {"hits": [%s]}' % str(hit).replace("'", '"')) == [hit]
    assert hits_from('{"hits": []}') == []


def test_hits_shaped_unlike_a_hit_are_dropped() -> None:
    assert hits_from('{"hits": ["Great question!"]}') == []
    assert hits_from('{"hits": 5}') == []


def test_an_answer_with_no_json_raises() -> None:
    with pytest.raises(RuntimeError):
        hits_from("The message reads well.")


@pytest.fixture
def hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Call the hook the way Claude Code does, and hand back the log it wrote."""
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(chat_review, "LOG", log)
    for marker in SKIP_MARKERS:
        monkeypatch.delenv(marker, raising=False)

    def call(payload: dict, reviewer=None, **env: str) -> list[dict]:
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setattr(chat_review, "review", reviewer or unreachable)
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        chat_review.main()
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    return call


def unreachable(message: str) -> list[dict]:
    raise AssertionError("the reviewer was called on a turn that should have returned first")


DRAFT = {"last_assistant_message": "Great question! Here's the thing — it's a game changer."}


@pytest.mark.parametrize(
    "payload, env, decision, why",
    [
        (DRAFT, {"CHAT_REVIEW_NESTED": "1"}, "skip", "nested"),
        (DRAFT, {"CHAT_REVIEW_OFF": "1"}, "skip", "off"),
        (DRAFT, {"DISPATCH_WORKLOG": "/tmp/run.log"}, "skip", "dispatched worker"),
        (DRAFT, {"CLAUDE_CODE_SESSION_ATTENDED": "0"}, "skip", "unattended session"),
        ({**DRAFT, "stop_hook_active": True}, {}, "allow", "re-entry"),
        ({"last_assistant_message": "   "}, {}, "allow", "empty"),
    ],
)
def test_every_turn_the_reviewer_never_sees_says_in_the_log_why(
    hook, capsys, payload: dict, env: dict, decision: str, why: str
) -> None:
    (entry,) = hook(payload, **env)
    assert (entry["decision"], entry["why"]) == (decision, why)
    assert "message" not in entry  # a turn the reviewer never saw has no draft to keep
    assert capsys.readouterr().out == ""  # nothing is fed back, so the turn ends here


def test_an_attended_session_is_reviewed_and_a_clean_reply_says_so(hook, capsys) -> None:
    (entry,) = hook(DRAFT, reviewer=lambda message: [], CLAUDE_CODE_SESSION_ATTENDED="1")
    assert (entry["decision"], entry["why"]) == ("allow", "clean")
    assert entry["message"] == DRAFT["last_assistant_message"]
    assert capsys.readouterr().out == ""


def test_hits_continue_the_turn_as_feedback_naming_the_rule_and_the_quote(hook, capsys) -> None:
    hits = [{"rule": "13", "quote": "game changer", "fix": "say what it changes"}]
    (entry,) = hook(DRAFT, reviewer=lambda message: hits)
    assert (entry["decision"], entry["hits"]) == ("feedback", hits)
    out = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert out["hookEventName"] == "Stop"
    assert "game changer" in out["additionalContext"] and "say what it changes" in out["additionalContext"]


def test_a_reviewer_that_breaks_lets_the_reply_through_and_records_the_failure(hook, capsys) -> None:
    def broken(message: str) -> list[dict]:
        raise RuntimeError("claude exited 1")

    (entry,) = hook(DRAFT, reviewer=broken)
    assert entry["decision"] == "allow" and "claude exited 1" in entry["why"]
    assert capsys.readouterr().out == ""

