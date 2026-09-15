# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for the chat reviewer's four readings. Run: uv run test_chat_review.py

The seams are the scope selection (catalogue text in, the chat-scoped rule blocks out), the
answer parse (a model's answer in, hits out), the log read-back (log lines in, the rule ids a
session was shown out) and the decision `main` reaches (a hook payload and an environment in, a
log line and the turn's continuation out). The oracle for the selection is
the awk command CATALOGUE.md's header publishes as its format contract: this test runs that
command and demands the same bytes, so the header and the script cannot drift apart, and a
catalogue whose bullets stop matching fails here rather than turning every reply clean. The
answer parse is held to the hook's fail-open rule: drop what cannot be formatted, raise only
where the caller still catches. The decisions are the module docstring's own list, and the log
is where the spec reads them: it defers the residue ruling to a week of that file.
"""

import io
import json
import os
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

SELECTED = """- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `13` `chat` **A rule for replies.** Kept."""


def awk_selection() -> str:
    """The header's own command, run on the real catalogue."""
    program = re.search(r"awk '(.+?)' CATALOGUE\.md", CATALOGUE.read_text()).group(1)
    run = subprocess.run(["awk", program, CATALOGUE], capture_output=True, text=True, check=True)
    return run.stdout.rstrip("\n")


def test_selection_is_the_one_the_catalogue_documents() -> None:
    assert chat_rules(CATALOGUE.read_text()) == awk_selection()


def test_selected_blocks_come_whole() -> None:
    assert chat_rules(FIXTURE) == SELECTED


def test_a_catalogue_with_no_chat_rules_raises() -> None:
    with pytest.raises(RuntimeError):
        chat_rules(FIXTURE.replace("`both`", "`artifact`").replace("`chat`", "`artifact`"))


def test_hits_are_read_out_of_surrounding_prose() -> None:
    # the quote a rule-13 hit carries is an em dash, and an apostrophe is the next likeliest
    # thing in it, so the answer goes in as the literal a model would write
    answer = 'Here you go: {"hits": [{"rule": "13", "quote": "it doesn’t — yet", "note": "a dash as a joint"}]}'
    assert hits_from(answer) == [{"rule": "13", "quote": "it doesn’t — yet", "note": "a dash as a joint"}]
    assert hits_from('{"hits": []}') == []


def test_hits_shaped_unlike_a_hit_are_dropped() -> None:
    assert hits_from('{"hits": ["Great question!"]}') == []
    assert hits_from('{"hits": 5}') == []


def test_an_answer_with_no_json_raises() -> None:
    with pytest.raises(RuntimeError):
        hits_from("The message reads well.")


def test_the_reviewer_is_asked_about_the_message_against_the_selected_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    argvs = []

    def claude(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        argvs.append(argv)
        answer = json.dumps({"type": "result", "result": '{"hits": [{"rule": "13", "quote": "the thing"}]}'})
        return subprocess.CompletedProcess(argv, 0, stdout=answer, stderr="")

    monkeypatch.setattr(chat_review.subprocess, "run", claude)
    assert chat_review.review("Here's the thing.", SELECTED) == [{"rule": "13", "quote": "the thing"}]
    (argv,) = argvs
    assert f"# Rules\n\n{SELECTED}\n\n# Message\n\nHere's the thing.\n" in argv[-1]


@pytest.fixture
def hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Call the hook the way Claude Code does, on the fixture catalogue, and hand back the log it wrote."""
    log = tmp_path / "log.jsonl"
    catalogue = tmp_path / "CATALOGUE.md"
    catalogue.write_text(FIXTURE)
    monkeypatch.setattr(chat_review, "LOG", log)
    monkeypatch.setattr(chat_review, "CATALOGUE", catalogue)
    monkeypatch.setattr(chat_review, "MODEL", "haiku")
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


def unreachable(message: str, rules: str) -> list[dict]:
    raise AssertionError("the reviewer was called on a turn that should have returned first")


def context(capsys: pytest.CaptureFixture) -> str:
    out = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert out["hookEventName"] == "Stop"
    return out["additionalContext"]


DRAFT = {"session_id": "s1", "last_assistant_message": "Great question! Here's the thing — it's a game changer."}


@pytest.mark.parametrize(
    "payload, env, decision, why",
    [
        (DRAFT, {"CHAT_REVIEW_NESTED": "1"}, "skip", "nested"),
        (DRAFT, {"CHAT_REVIEW_OFF": "1"}, "skip", "off"),
        (DRAFT, {"DISPATCH_WORKLOG": "/tmp/run.log"}, "skip", "dispatched worker"),
        (DRAFT, {"CLAUDE_CODE_SESSION_ATTENDED": "0"}, "skip", "unattended session"),
        ({"session_id": "s1", "last_assistant_message": "   "}, {}, "allow", "empty"),
    ],
)
def test_every_skipped_or_empty_turn_says_in_the_log_why(
    hook, capsys, payload: dict, env: dict, decision: str, why: str
) -> None:
    (entry,) = hook(payload, **env)
    assert (entry["decision"], entry["why"], entry["session_id"]) == (decision, why, "s1")
    assert "message" not in entry  # no draft was reviewed and no revision follows feedback, so no reply is kept
    assert capsys.readouterr().out == ""  # nothing is fed back, so the turn ends here


def test_the_re_entry_skips_the_reviewer_and_keeps_the_revised_reply(hook, capsys) -> None:
    revised = {"session_id": "s1", "stop_hook_active": True, "last_assistant_message": "It changes how queries compose."}
    (entry,) = hook(revised)
    assert (entry["decision"], entry["why"]) == ("allow", "re-entry")
    # paired by session with the draft's feedback line, it shows which flagged passages survived
    assert (entry["session_id"], entry["message"]) == ("s1", revised["last_assistant_message"])
    assert capsys.readouterr().out == ""


def test_an_attended_session_is_reviewed_and_a_clean_reply_says_so(hook, capsys) -> None:
    given = []

    def clean(message: str, rules: str) -> list[dict]:
        given.append(rules)
        return []

    (entry,) = hook(DRAFT, reviewer=clean, CLAUDE_CODE_SESSION_ATTENDED="1")
    assert given == [SELECTED]
    assert (entry["decision"], entry["why"], entry["session_id"]) == ("allow", "clean", "s1")
    assert entry["message"] == DRAFT["last_assistant_message"]
    assert capsys.readouterr().out == ""


def test_hits_continue_the_turn_as_feedback_carrying_each_cited_rule_once(hook, capsys) -> None:
    hits = [
        {"rule": "3", "quote": "a game changer", "note": "says it matters, not what it does"},
        {"rule": 13, "quote": "Here's the thing", "note": "a setup before the point"},  # an id answered as a number
        {"rule": "`3`", "quote": "Great question!"},  # an id in backticks, and no note
        {"rule": "51", "quote": "it's", "note": "a rule the chat review does not apply"},  # listed, never explained
    ]
    (entry,) = hook(DRAFT, reviewer=lambda message, rules: hits)
    assert (entry["decision"], entry["hits"], entry["session_id"]) == ("feedback", hits, "s1")
    assert entry["explained"] == ["3", "13"]
    assert context(capsys) == """\
An automated review by haiku flagged these passages of your last message against the chat prose rules:
- rule 3: "a game changer" (says it matters, not what it does)
- rule 13: "Here's the thing" (a setup before the point)
- rule 3: "Great question!"
- rule 51: "it's" (a rule the chat review does not apply)

The rules they cite:
- `3` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".
- `13` **A rule for replies.** Kept.

Revise the message where the hits hold."""


def test_a_session_gets_each_rule_text_once(hook, capsys) -> None:
    hook(DRAFT, reviewer=lambda message, rules: [{"rule": "3", "quote": "a game changer"}])
    capsys.readouterr()
    *_, entry = hook(DRAFT, reviewer=lambda message, rules: [{"rule": "3", "quote": "Great question!"}, {"rule": "13", "quote": "Here's the thing"}])
    assert entry["explained"] == ["13"]
    assert context(capsys) == """\
An automated review by haiku flagged these passages of your last message against the chat prose rules:
- rule 3: "Great question!"
- rule 13: "Here's the thing"

The rules they cite:
- `13` **A rule for replies.** Kept.

Revise the message where the hits hold."""
    *_, entry = hook({**DRAFT, "session_id": "s2"}, reviewer=lambda message, rules: [{"rule": "3", "quote": "a game changer"}])
    assert entry["explained"] == ["3"]  # another session has not been shown rule 3


def test_the_rules_a_session_was_shown_are_read_back_from_its_feedback_lines(tmp_path, monkeypatch) -> None:
    log = tmp_path / "log.jsonl"
    lines = [
        json.dumps({"session_id": "s1", "decision": "feedback", "explained": ["3"]}),
        json.dumps({"session_id": "s2", "decision": "feedback", "explained": ["13"]}),
        '{"session_id": "s1", "decision": "feedback", "explained": ["7"',  # cut short by a concurrent write
        json.dumps({"session_id": "s1", "decision": "feedback", "explained": ["22"], "message": "about s2"}),
    ]
    log.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(chat_review, "LOG", log)
    assert chat_review.shown_rules("s1") == {"3", "22"}
    assert chat_review.shown_rules("s2") == {"13"}  # a line that only mentions s2 belongs to s1
    assert chat_review.shown_rules(None) == set()


def test_feedback_citing_no_selected_rule_has_no_rules_section(hook, capsys) -> None:
    (entry,) = hook(DRAFT, reviewer=lambda message, rules: [{"rule": "51", "quote": "it's"}])
    assert entry["explained"] == []
    assert context(capsys) == """\
An automated review by haiku flagged these passages of your last message against the chat prose rules:
- rule 51: "it's"

Revise the message where the hits hold."""


def test_feedback_past_the_hook_output_limit_points_at_the_catalogue_for_the_rules(hook, capsys, monkeypatch) -> None:
    monkeypatch.setattr(chat_review, "FEEDBACK_LIMIT", 200)
    (entry,) = hook(DRAFT, reviewer=lambda message, rules: [{"rule": "3", "quote": "a game changer"}])
    assert entry["explained"] == []  # no text went out, so the session is not counted as shown rule 3
    assert context(capsys) == f"""\
An automated review by haiku flagged these passages of your last message against the chat prose rules:
- rule 3: "a game changer"

The rules they cite, by id, are in {chat_review.CATALOGUE}.

Revise the message where the hits hold."""


def test_a_reviewer_that_breaks_lets_the_reply_through_and_records_the_failure(hook, capsys) -> None:
    def broken(message: str, rules: str) -> list[dict]:
        raise RuntimeError("claude exited 1")

    (entry,) = hook(DRAFT, reviewer=broken)
    assert (entry["decision"], entry["session_id"]) == ("allow", "s1") and "claude exited 1" in entry["why"]
    assert capsys.readouterr().out == ""


def test_the_log_lands_in_the_backed_up_logs_directory_by_default(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k not in SKIP_MARKERS + ("CHAT_REVIEW_LOG",)}
    env.update(HOME=str(tmp_path), CHAT_REVIEW_OFF="1")
    script = Path(chat_review.__file__)
    subprocess.run([sys.executable, script], input=json.dumps(DRAFT), text=True, env=env, check=True)
    (line,) = (tmp_path / "logs/chat-review/log.jsonl").read_text().splitlines()
    assert json.loads(line)["why"] == "off"


def test_a_catalogue_with_no_chat_rules_lets_the_reply_through(hook, capsys) -> None:
    chat_review.CATALOGUE.write_text(FIXTURE.replace("`both`", "`artifact`").replace("`chat`", "`artifact`"))
    (entry,) = hook(DRAFT, reviewer=lambda message, rules: [{"rule": "3", "quote": "a game changer"}])
    assert entry["decision"] == "allow" and "no rule tagged" in entry["why"]
    assert capsys.readouterr().out == ""
