# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""The write hook's properties. Run: uv run test_write_hook.py

The seam is the hook at its input: the PostToolUse JSON of a write and the session directory in,
its decision out, with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/turns-end-on-their-recap.md, its Properties P1 and P2, and session-page's Decisions on
the review, over the worked example in `fixtures/`. The transcript the hook reads lacks the call it
is given, as Claude Code's does while the hook runs. The prose reviewer is stubbed by conftest.py.
"""

import io
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import session_page
import stop_hook
import turn_review
import write_hook
from session_page import PAGE, SESSIONS
from stop_hook import RECAP
from conftest import SPOKEN_AFTER, UNATTENDED, unreachable
from test_stop_hook import LEFT_ALONE, LONG, TURN_STARTS, UNPARSEABLE, appended, logged, with_write
from test_stop_hook import payload as stopped
from test_turn_review import CATALOGUE_FIXTURE, RULES_FIXTURE
from write_hook import decide

# Passages of the worked example's record 4, the one its turn wrote, as a reviewer would quote them.
IN_RECORD = ["The session page only holds things", "There is no markup of its own to learn.",
             "costs seconds", "The chat reply is one line and the link"]
NOT_IN_RECORD = "The session page is a pivotal tapestry of links."
PIVOTAL_05 = "---\ndate: 2026-09-23\n---\n\n# Round 4\n\n## Details\n\nThe second bank is a pivotal addition.\n"


@pytest.fixture
def writing(transcript: Path, tmp_path: Path) -> Path:
    """The worked example's transcript as the write hook reads it while record 04 is being
    written: everything up to that Write call, and not the call."""
    before = tmp_path / "writing-04.jsonl"
    before.write_text("".join(line for line in transcript.read_text().splitlines(keepends=True) if "toolu_fixture_record_04" not in line))
    return before


def wrote(record: Path, transcript: Path, tool: str = "Write") -> dict:
    """The PostToolUse JSON of the turn's `tool` call on `record`, which already holds what the call
    wrote."""
    directory = record.parent.parent if record.parent.name == "turns" else record.parent
    return {
        "session_id": directory.name,
        "cwd": str(directory.parents[len(SESSIONS.parts)]),
        "transcript_path": str(transcript),
        "hook_event_name": "PostToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": str(record), "content": record.read_text()},
        "tool_use_id": f"toolu_{tool}_{record.stem}",
    }


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> Callable[[dict], str]:
    """Call the hook the way Claude Code does, on the payload given, and hand back the context it
    added for the agent, empty where it added none."""

    def call(hook: dict) -> str:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook)))
        write_hook.main()
        out = capsys.readouterr().out
        if not out:
            return ""
        said = json.loads(out)["hookSpecificOutput"]
        assert said["hookEventName"] == "PostToolUse"
        return said["additionalContext"]

    return call


def finding(quote: str, rule: str = "7") -> dict:
    return {"rule": rule, "quote": quote, "note": "a note on it"}


def reviewer(*found: dict) -> Callable[[str, str], list[dict]]:
    return lambda system, prompt: list(found)


# ---- P1: the review runs on the record's Write, before the turn ends --------


def test_a_record_with_findings_goes_back_on_its_write_with_at_most_three(
    worked_example: Path, writing: Path, stale_page: str, run: Callable[[dict], str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """turns-end-on-their-recap#P1 and P5: the findings reach the agent from the Write that wrote
    the record, while the turn runs, asking for the recap once it is revised; the page waits for the
    turn's end. The edit that revises the record is parsed and not reviewed again."""
    record = worked_example / "turns" / "04.md"
    monkeypatch.setattr(turn_review, "review", reviewer(*map(finding, IN_RECORD)))
    (worked_example / PAGE).write_text(stale_page)
    said = run(wrote(record, writing))
    assert str(record) in said
    assert [quote for quote in IN_RECORD if f'"{quote}"' in said] == IN_RECORD[:3]
    assert "**AI vocabulary.**" in said, "a cited rule comes with its text"
    assert RECAP in said
    assert (worked_example / PAGE).read_text() == stale_page

    monkeypatch.setattr(turn_review, "review", unreachable)
    record.write_text(record.read_text().replace("only holds things", "holds things"))
    assert run(wrote(record, writing, "Edit")) == ""


FOUND = {
    "one quote in the record and one not": ([finding(NOT_IN_RECORD), finding(IN_RECORD[0])], [IN_RECORD[0]]),
    "only quotes not in the record": ([finding(NOT_IN_RECORD), finding("")], []),
}


@pytest.mark.parametrize("found, kept", FOUND.values(), ids=FOUND)
def test_a_finding_quoting_text_absent_from_the_record_is_dropped(
    found: list[dict], kept: list[str], worked_example: Path, writing: Path, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dropped finding never reaches the agent, and a record whose findings all drop goes
    through. An empty quote is in every record, and quotes nothing."""
    monkeypatch.setattr(turn_review, "review", reviewer(*found))
    said = run(wrote(worked_example / "turns" / "04.md", writing))
    assert [quote for quote in IN_RECORD if f'"{quote}"' in said] == kept
    assert NOT_IN_RECORD not in said


def broken(system: str, prompt: str) -> list[dict]:
    raise RuntimeError("claude exited 1: overloaded")


def hung(system: str, prompt: str) -> list[dict]:
    raise subprocess.TimeoutExpired(["run-log"], turn_review.WRAPPER_TIMEOUT_S)


@pytest.mark.parametrize("failing", [broken, hung], ids=["a failing reviewer", "a hung run-log"])
def test_a_reviewer_that_fails_lets_the_record_through_and_logs_why(
    failing: Callable[[str, str], list[dict]], worked_example: Path, writing: Path, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """A failed review is the turn's review: a second Write of the record does not call the
    reviewer again."""
    record = worked_example / "turns" / "04.md"
    monkeypatch.setattr(turn_review, "review", failing)
    assert run(wrote(record, writing)) == ""
    (entry,) = logged(attended, "decision")
    assert (entry["session_id"], entry["decision"]) == (worked_example.name, "failed")
    monkeypatch.setattr(turn_review, "review", unreachable)
    assert run(wrote(record, writing)) == ""


@pytest.mark.parametrize("start", [SPOKEN_AFTER, *TURN_STARTS.values()], ids=["the user's prompt", *TURN_STARTS])
def test_a_record_a_later_turn_writes_is_reviewed_though_an_earlier_turns_was(
    start: dict, worked_example: Path, transcript: Path, tmp_path: Path, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The review runs once per turn, not once per session: record 04's review, logged in its own
    turn, leaves the record the next turn writes to be reviewed, whoever started that turn."""
    attended.write_text(json.dumps({"ts": "2026-09-23T01:31:00+00:00", "session_id": worked_example.name, "decision": "clean",
                                    "record": str(worked_example / "turns" / "04.md")}) + "\n")
    record = worked_example / "turns" / "05.md"
    record.write_text(PIVOTAL_05)
    monkeypatch.setattr(turn_review, "review", reviewer(finding("a pivotal addition")))
    assert str(record) in run(wrote(record, appended(transcript, tmp_path / "t.jsonl", start)))


WRITES_IN_A_TURN_WITH_NO_RECORD = {
    "a write of the session record": "session.md",
    "a write of an earlier turn's record": "turns/04.md",
}


@pytest.mark.parametrize("name", WRITES_IN_A_TURN_WITH_NO_RECORD.values(), ids=WRITES_IN_A_TURN_WITH_NO_RECORD)
def test_a_write_in_a_turn_that_has_written_no_record_is_parsed_and_never_reviewed(
    name: str, worked_example: Path, unrecorded: Path, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The session record is reviewed with the turn's record, and record 04, the turn before's,
    was reviewed in that turn: the page keeps a record's earliest write."""
    monkeypatch.setattr(turn_review, "review", unreachable)
    assert run(wrote(worked_example / name, unrecorded)) == ""
    assert [entry["why"] for entry in logged(attended, "verb")] == ["records parse"]


def test_a_record_whose_write_did_not_parse_is_reviewed_once_the_edit_that_fixes_it_lands(
    worked_example: Path, unrecorded: Path, run: Callable[[dict], str], monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """turns-end-on-their-recap#P1 and P2: a parse error on the record's Write only delays its
    review, to the first write after which the records parse, and the edit after the findings is
    not reviewed again."""
    record = worked_example / "turns" / "05.md"
    record.write_text(PIVOTAL_05.replace("date:", "day:"))
    assert run(wrote(record, unrecorded)).startswith(f"{record}")
    with_write(unrecorded, "Write", record)
    record.write_text(PIVOTAL_05)
    monkeypatch.setattr(turn_review, "review", reviewer(finding("a pivotal addition")))
    assert str(record) in run(wrote(record, unrecorded, "Edit"))
    monkeypatch.setattr(turn_review, "review", unreachable)
    record.write_text(PIVOTAL_05.replace("a pivotal addition", "the ledger's overflow"))
    assert run(wrote(record, unrecorded, "Edit")) == ""
    assert [e["decision"] for e in logged(attended, "decision")] == ["feedback"]


def test_a_record_reviewed_on_its_write_renders_as_reviewed_when_the_turn_ends(
    worked_example: Path, unrecorded: Path, capsys: pytest.CaptureFixture, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The record a turn writes is reviewed on its write, and the stop that follows renders it as
    reviewed."""
    record = worked_example / "turns" / "05.md"
    record.write_text(PIVOTAL_05)
    monkeypatch.setattr(turn_review, "review", reviewer(finding("a pivotal addition")))
    assert str(record) in run(wrote(record, unrecorded))
    with_write(unrecorded, "Write", record)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stopped(worked_example, unrecorded, reply=LONG))))
    stop_hook.main()
    assert "systemMessage" in json.loads(capsys.readouterr().out)
    assert logged(attended, "verb")[-1]["why"] == "record reviewed this turn"


TITLE = "Leading words for showing, and the session page"  # the worked example's session.md H1


@pytest.mark.parametrize("rewritten", [True, False], ids=["session.md written this turn", "session.md left as it was"])
def test_a_turn_that_rewrites_the_session_record_has_it_reviewed_with_its_own(
    rewritten: bool, worked_example: Path, unrecorded: Path, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The session's title heads its page, so a turn that wrote session.md before its record has
    it reviewed, fenced before the turn's record, and a finding on its title goes back naming it.
    A turn that leaves it as it was has only its record reviewed, and the same finding drops."""
    if rewritten:
        call = {"type": "tool_use", "id": "toolu_Edit_session", "name": "Edit", "input": {"file_path": str(worked_example / "session.md")}}
        appended(unrecorded, unrecorded, {"type": "assistant", "message": {"role": "assistant", "content": [call]}, "timestamp": "2026-09-23T01:35:30.000Z"})
    record = worked_example / "turns" / "05.md"
    record.write_text(PIVOTAL_05)
    prompts = []
    monkeypatch.setattr(turn_review, "review", lambda system, prompt: prompts.append(prompt) or [finding(TITLE, "54")])
    said = run(wrote(record, unrecorded))
    (prompt,) = prompts
    session_record = f"<record>\n{(worked_example / 'session.md').read_text().strip()}\n</record>"
    assert prompt.endswith(f"{session_record}\n<record>\n{PIVOTAL_05.strip()}\n</record>") == rewritten
    (entry,) = logged(attended, "decision")
    assert ("session_record" in entry) == rewritten
    if rewritten:
        assert str(worked_example / "session.md") in said and f'"{TITLE}"' in said
        assert "**Headline titles.**" in said
    else:
        assert said == "" and entry["dropped"] == [finding(TITLE, "54")]


def test_the_reviewer_reads_what_the_page_shows_and_no_tool_call(
    worked_example: Path, writing: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The reviewer's input carries the earlier turn records and the user's messages, the ones this
    record answers included, though the transcript does not hold its Write yet, and no tool call:
    the transcript's Write calls and the task notifications that name a tool use carry ids starting
    `toolu_`. The record under review comes last, fenced, and the reviewer runs under its own system
    prompt, bound to the schema."""
    claude = fake_claude(tmp_path, monkeypatch, RESULT | {"structured_output": {"findings": [finding(IN_RECORD[0])]}})
    turns = worked_example / "turns"
    decision = decide(wrote(turns / "04.md", writing), worked_example)
    assert decision.verb == "send back" and IN_RECORD[0] in decision.reason
    argv = (claude / "argv").read_text().split("\0")[:-1]
    prompt, system = (claude / "stdin").read_text(), argv[argv.index("--system-prompt") + 1]
    for earlier in ("01.md", "02.md", "03.md"):
        assert (turns / earlier).read_text().strip() in prompt
    assert prompt.endswith(f"<record>\n{(turns / '04.md').read_text().strip()}\n</record>")
    assert "i feel like we need like a leading word" in prompt  # the first prompt
    assert "hey can you please disregard" in prompt  # one the fourth turn answered
    assert "toolu_" not in prompt
    assert "Claude Code" not in system and "**AI vocabulary.**" in system
    assert turn_review.record_shape(turn_review.RULES.read_text()) in system
    assert json.loads(argv[argv.index("--json-schema") + 1])["properties"]["findings"]["maxItems"] == 3
    assert argv[argv.index("--model") + 1] == "claude-opus-5-5" and argv[argv.index("--effort") + 1] == "low"


# ---- P2: a write that breaks the records goes back at once ------------------


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
@pytest.mark.parametrize("name, text, line", UNPARSEABLE.values(), ids=UNPARSEABLE)
def test_a_write_that_leaves_the_records_unparseable_is_answered_with_the_readers_error(
    name: str, text: str, line: int | None, tool: str, worked_example: Path, writing: Path, stale_page: str,
    run: Callable[[dict], str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """turns-end-on-their-recap#P2: the reason names the file and the line the reader gave up on,
    asks for the recap once the record is fixed, and costs no model call."""
    record = worked_example / "turns" / name
    monkeypatch.setattr(turn_review, "review", unreachable)
    record.write_text(text)
    said = run(wrote(record, writing, tool))
    assert said.startswith(f"{record}:{line}: " if line else f"{record}: ")
    assert "carry on" in said and RECAP in said, "the turn goes on, and still ends on its recap"


def test_a_session_record_that_does_not_parse_is_answered_on_its_edit(
    worked_example: Path, writing: Path, run: Callable[[dict], str],
) -> None:
    session = worked_example / "session.md"
    session.write_text(session.read_text().replace("repo:", "repository:"))
    assert run(wrote(session, writing, "Edit")).startswith(f"{session}")


@pytest.mark.parametrize("broken", [False, True], ids=["a session record that parses", "one that does not"])
def test_the_first_paged_turns_session_record_is_parsed_before_any_turn_record_exists(
    broken: bool, worked_example: Path, writing: Path, run: Callable[[dict], str],
) -> None:
    """every-session-gets-a-page#P5: the reader takes a directory with no numbered record, so a
    session.md written before any turn record is parsed and answered for like any other record."""
    for record in (worked_example / "turns").iterdir():
        record.unlink()
    session = worked_example / "session.md"
    if broken:
        session.write_text(session.read_text().replace("repo:", "repository:"))
    said = run(wrote(session, writing))
    assert said.startswith(f"{session}") if broken else said == ""


def test_a_turn_record_pointing_at_another_part_of_the_page_in_words_goes_back_until_it_links_it(
    worked_example: Path, writing: Path, run: Callable[[dict], str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A question at the top sits far from the turn whose Details it means, so a record links the
    part it points at. The send-back names the line and costs no model call; the same words in
    code, or in an older record no turn edits any more, pass."""
    older, record = worked_example / "turns" / "03.md", worked_example / "turns" / "04.md"
    older.write_text(older.read_text().rstrip("\n") + "\n\nThe two commands are listed under Details.\n")
    text = record.read_text().rstrip("\n")
    monkeypatch.setattr(turn_review, "review", unreachable)
    record.write_text(text + "\n\nThe four ways out are under Details.\n")
    said = run(wrote(record, writing))
    assert said.startswith(f"{record}:{text.count(chr(10)) + 3}: 'under Details' ")
    assert "(#t07)" in said and RECAP in said

    monkeypatch.setattr(turn_review, "review", reviewer())
    record.write_text(text + "\n\nThe four ways out are in [turn 03](#t03); `see below` is code.\n")
    assert run(wrote(record, writing, "Edit")) == ""


# ---- what it leaves alone ---------------------------------------------------


def test_a_write_that_is_no_record_of_this_session_is_let_through(
    worked_example: Path, writing: Path, tmp_path: Path, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The hook runs on every file edit of every session: a file elsewhere in the project, a record
    of another session, or a file in this session's directory that is no record of it, is no
    business of this one, broken records or not."""
    (worked_example / "turns" / "04.md").write_text("no frontmatter\n")
    monkeypatch.setattr(turn_review, "review", unreachable)
    code = worked_example.parents[2] / "src" / "ledger.py"
    code.parent.mkdir()
    code.write_text("")
    other = worked_example.parent / "8e0f1c22-0000-0000-0000-000000000000" / "turns" / "01.md"
    other.parent.mkdir(parents=True)
    other.write_text("no frontmatter\n")
    inside = worked_example / "drafts" / "notes.md"
    inside.parent.mkdir()
    inside.write_text("")
    for path in (code, other, inside):
        assert run(wrote(worked_example / "turns" / "04.md", writing) | {"tool_input": {"file_path": str(path)}}) == ""
    assert [entry["why"] for entry in logged(attended, "verb")] == ["no record of this session"], "only the path in its directory is read past the path"


@pytest.mark.parametrize("marker, value", LEFT_ALONE.values(), ids=LEFT_ALONE)
def test_a_session_nobody_reads_the_page_of_is_left_alone(
    marker: str, value: str, worked_example: Path, writing: Path, run: Callable[[dict], str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(marker, value)
    monkeypatch.setattr(turn_review, "review", unreachable)
    record = worked_example / "turns" / "04.md"
    assert run(wrote(record, writing)) == ""
    record.write_text("no frontmatter\n")
    assert run(wrote(record, writing, "Edit")) == ""


# ---- the log ----------------------------------------------------------------


def test_each_decision_on_a_record_is_one_line_in_the_session_pages_log(
    worked_example: Path, writing: Path, run: Callable[[dict], str], monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The review's own line carries the record it read; the hook's line beside it says what came
    of the write, which tool made it and on what."""
    record = worked_example / "turns" / "04.md"
    monkeypatch.setattr(turn_review, "review", reviewer(finding(IN_RECORD[0]), finding(NOT_IN_RECORD)))
    run(wrote(record, writing))
    run(wrote(record, writing, "Edit"))
    (review,) = logged(attended, "decision")
    assert (review["decision"], review["findings"], review["dropped"]) == ("feedback", [finding(IN_RECORD[0])], [finding(NOT_IN_RECORD)])
    assert review["record"] == str(record) and review["text"] == record.read_text()
    assert [(e["verb"], e["why"], e["tool"], e["path"]) for e in logged(attended, "verb")] == [
        ("send back", "review findings", "Write", str(record)), ("allow", "record reviewed this turn", "Edit", str(record))]


# ---- the reviewer's run -----------------------------------------------------

REVIEW = turn_review.review  # the real one, which the autouse stub replaces

# What claude's stream ends with, as ../run-log/test_run_log.py has it.
RESULT = {"type": "result", "subtype": "success", "is_error": False, "session_id": "sess-1", "num_turns": 1,
          "duration_ms": 4200, "duration_api_ms": 3900, "total_cost_usd": 0.0123,
          "usage": {"input_tokens": 22, "output_tokens": 70, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
          "result": ""}


def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: dict | None, then: str = "exit 0") -> Path:
    """The real reviewer, calling a `claude` first on PATH that records its argv and stdin, streams
    `result` as its last line, and does `then`; the run log is the check's own. Returns the
    directory holding the argv, the stdin and `runs.jsonl`."""
    where = tmp_path / "reviewer"
    where.mkdir()
    (where / "claude").write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\0" "$@" > "{where}/argv"\n'
        f'cat > "{where}/stdin"\n'
        + (f"echo {json.dumps(json.dumps(result))}\n" if result else "echo 'API Error: overloaded'\n")
        + f"{then}\n")
    (where / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{where}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("RUN_LOG", str(where / "runs.jsonl"))
    monkeypatch.setattr(turn_review, "review", REVIEW)
    return where


def test_the_review_is_one_line_in_the_run_log_under_its_own_site(
    worked_example: Path, writing: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    claude = fake_claude(tmp_path, monkeypatch, RESULT | {"structured_output": {"findings": []}})
    assert decide(wrote(worked_example / "turns" / "04.md", writing), worked_example).why == "review found nothing"
    (line,) = map(json.loads, (claude / "runs.jsonl").read_text().splitlines())
    assert (line["site"], line["model"], line["effort"], line["cost_usd"], line["end"]) == (
        "turn-review", "claude-opus-5-5", "low", 0.0123, "success")


def test_a_reviewer_run_that_fails_is_still_one_line_in_the_run_log_and_the_record_goes_through(
    worked_example: Path, writing: Path, monkeypatch: pytest.MonkeyPatch, attended: Path, tmp_path: Path,
) -> None:
    claude = fake_claude(tmp_path, monkeypatch, None, then="exit 1")
    assert decide(wrote(worked_example / "turns" / "04.md", writing), worked_example).verb == "allow"
    (line,) = map(json.loads, (claude / "runs.jsonl").read_text().splitlines())
    assert (line["site"], line["exit"], line["end"]) == ("turn-review", 1, "no result")
    (entry,) = logged(attended, "decision")
    assert (entry["decision"], entry["why"]) == ("failed", "claude exited 1: API Error: overloaded")


def test_a_reviewer_past_its_limit_is_ended_with_its_line_written_and_the_record_goes_through(
    worked_example: Path, writing: Path, monkeypatch: pytest.MonkeyPatch, attended: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr(turn_review, "REVIEWER_TIMEOUT_S", 1)
    claude = fake_claude(tmp_path, monkeypatch, None, then="exec sleep 30")
    assert decide(wrote(worked_example / "turns" / "04.md", writing), worked_example).verb == "allow"
    (line,) = map(json.loads, (claude / "runs.jsonl").read_text().splitlines())
    assert (line["site"], line["exit"], line["end"]) == ("turn-review", "timeout", "no result")
    (entry,) = logged(attended, "decision")
    assert entry["decision"] == "failed" and entry["why"].startswith("claude ran past 1s")


def test_the_plugin_runs_the_hook_after_every_tool_that_writes_a_file_and_waits_out_the_review() -> None:
    """The hooks.json entry is what puts P1 and P2 in a session: its matcher takes each tool whose
    call the page counts as a write, and its timeout outlasts the reviewer's own limit, so a slow
    review fails open inside the hook rather than being cut off."""
    hooks = json.loads((Path(__file__).parents[2] / "hooks" / "hooks.json").read_text())["hooks"]["PostToolUse"]
    (entry,) = [e for e in hooks if any(h["command"].endswith("/skills/session-page/write_hook.py") for h in e["hooks"])]
    assert all(re.fullmatch(entry["matcher"], tool) for tool in session_page.WRITES)
    assert entry["hooks"][0]["timeout"] > turn_review.WRAPPER_TIMEOUT_S


def test_the_hook_as_claude_code_runs_it_answers_a_broken_record(worked_example: Path, writing: Path, tmp_path: Path) -> None:
    """The script itself, in a process of its own with the hook JSON on stdin, which is where its
    deferred imports run."""
    record = worked_example / "turns" / "04.md"
    record.write_text("no frontmatter\n")
    hook = Path(__file__).parent / "write_hook.py"
    env = {k: v for k, v in os.environ.items() if k not in UNATTENDED} | {"HOME": str(tmp_path)}
    done = subprocess.run([sys.executable, hook], input=json.dumps(wrote(record, writing)), capture_output=True, text=True, env=env, timeout=60)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"].startswith(f"{record}:")


# ---- a broken source of the review's rules ---------------------------------


def test_a_catalogue_with_no_chat_rules_lets_the_record_through(
    worked_example: Path, writing: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalogue = tmp_path / "CATALOGUE.md"
    catalogue.write_text(CATALOGUE_FIXTURE.replace("`both`", "`artifact`").replace("`chat`", "`artifact`"))
    monkeypatch.setattr(turn_review, "CATALOGUE", catalogue)
    monkeypatch.setattr(turn_review, "review", reviewer(finding(IN_RECORD[0])))
    assert decide(wrote(worked_example / "turns" / "04.md", writing), worked_example).verb == "allow"


def test_rules_with_no_turn_record_section_let_the_record_through(
    worked_example: Path, writing: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    rules = tmp_path / "RULES.md"
    rules.write_text(RULES_FIXTURE.replace("## The turn record", "## Another section"))
    monkeypatch.setattr(turn_review, "RULES", rules)
    monkeypatch.setattr(turn_review, "review", reviewer(finding(IN_RECORD[0])))
    assert decide(wrote(worked_example / "turns" / "04.md", writing), worked_example).verb == "allow"
    (entry,) = logged(attended, "decision")
    assert entry["decision"] == "failed" and "The turn record" in entry["why"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
