# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""The write hook's properties. Run: uv run test_write_hook.py

The seam is the hook at its input: the PostToolUse JSON of a write and the session directory in,
its decision out, with `main` applying that decision the way Claude Code runs it. The oracle is
agent/tickets/turns-end-on-their-recap.md, its Properties P1 and P2, and session-page's Decisions on
the review, over the worked example in `fixtures/`. The transcript the hook reads lacks the call it
is given, as Claude Code's does while the hook runs. The prose reviewer is stubbed as
test_stop_hook.py stubs it.
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
import turn_review
import write_hook
from session_page import PAGE, SESSIONS
from stop_hook import RECAP
from conftest import SPOKEN_AFTER
from test_stop_hook import TURN_STARTS, UNPARSEABLE, appended, logged, with_write
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


def unreachable(system: str, prompt: str) -> list[dict]:
    raise AssertionError("the reviewer was called on a write that should not spend a model call")


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


WRITES_NOT_REVIEWED = {
    "an edit of the record this turn wrote": ("05.md", "Edit"),
    "a write of the session record": ("session.md", "Write"),
    "a write of an earlier turn's record": ("04.md", "Write"),
}


@pytest.mark.parametrize("name, tool", WRITES_NOT_REVIEWED.values(), ids=WRITES_NOT_REVIEWED)
def test_a_write_that_is_not_the_turns_record_on_its_write_is_parsed_and_never_reviewed(
    name: str, tool: str, worked_example: Path, unrecorded: Path, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """turns-end-on-their-recap#P1 names the record's Write: the session record is reviewed with
    the turn's record, and record 04, the turn before's, was reviewed in that turn."""
    record = worked_example / "turns" / "05.md"
    record.write_text(PIVOTAL_05)
    if name == "05.md":
        with_write(unrecorded, "Write", record)
    monkeypatch.setattr(turn_review, "review", unreachable)
    assert run(wrote(worked_example / ("turns" if name != "session.md" else "") / name, unrecorded, tool)) == ""
    assert [entry["why"] for entry in logged(attended, "verb")] == ["records parse"]


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
    assert turn_review.record_shape(turn_review.SHOW.read_text()) in system
    assert json.loads(argv[argv.index("--json-schema") + 1])["properties"]["findings"]["maxItems"] == 3
    assert argv[argv.index("--model") + 1] == "claude-opus-5-5" and argv[argv.index("--effort") + 1] == "low"


# ---- P2: a write that breaks the records goes back at once ------------------


@pytest.mark.parametrize("tool", ["Write", "Edit"])
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
    assert RECAP in said


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
    """The show skill has the first paged turn write session.md before its turn record, so a
    session with no turn record yet is one still being written: only session.md is answered for."""
    for record in (worked_example / "turns").iterdir():
        record.unlink()
    session = worked_example / "session.md"
    if broken:
        session.write_text(session.read_text().replace("repo:", "repository:"))
    said = run(wrote(session, writing))
    assert said.startswith(f"{session}") if broken else said == ""


# ---- what it leaves alone ---------------------------------------------------


def test_a_write_outside_the_sessions_directory_is_let_through_unlogged(
    worked_example: Path, writing: Path, tmp_path: Path, run: Callable[[dict], str],
    monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    """The hook runs on every file edit of every session: a file elsewhere in the project, or a
    record of another session, is no business of this one, broken records or not."""
    (worked_example / "turns" / "04.md").write_text("no frontmatter\n")
    monkeypatch.setattr(turn_review, "review", unreachable)
    code = worked_example.parents[2] / "src" / "ledger.py"
    code.parent.mkdir()
    code.write_text("")
    other = worked_example.parent / "8e0f1c22-0000-0000-0000-000000000000" / "turns" / "01.md"
    other.parent.mkdir(parents=True)
    other.write_text("no frontmatter\n")
    for path in (code, other):
        assert run(wrote(worked_example / "turns" / "04.md", writing) | {"tool_input": {"file_path": str(path)}}) == ""
    assert not attended.exists()


LEFT_ALONE = {"a dispatched worker": ("DISPATCH_WORKLOG", "/w/log"), "a print-mode session": ("CLAUDE_CODE_SESSION_ATTENDED", "0")}


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
        ("send back", "review findings", "Write", str(record)), ("allow", "records parse", "Edit", str(record))]


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


def test_the_hook_as_claude_code_runs_it_answers_a_broken_record(worked_example: Path, writing: Path, tmp_path: Path) -> None:
    """The script itself, in a process of its own with the hook JSON on stdin, which is where its
    deferred imports run."""
    record = worked_example / "turns" / "04.md"
    record.write_text("no frontmatter\n")
    hook = Path(__file__).parent / "write_hook.py"
    env = {k: v for k, v in os.environ.items() if k not in ("DISPATCH_WORKLOG", "CLAUDE_CODE_SESSION_ATTENDED")} | {"HOME": str(tmp_path)}
    done = subprocess.run([sys.executable, hook], input=json.dumps(wrote(record, writing)), capture_output=True, text=True, env=env, timeout=60)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"].startswith(f"{record}:")


# ---- the catalogue's chat rules ---------------------------------------------

CATALOGUE_FIXTURE = """# Tells

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


def test_the_rules_selected_are_the_ones_the_catalogue_documents() -> None:
    """The oracle is the awk command CATALOGUE.md's header publishes as its format contract, run
    on the real catalogue: a catalogue whose bullets stop matching fails here rather than turning
    every record clean."""
    catalogue = turn_review.CATALOGUE
    program = re.search(r"awk '(.+?)' CATALOGUE\.md", catalogue.read_text()).group(1)
    awk = subprocess.run(["awk", program, catalogue], capture_output=True, text=True, check=True)
    assert turn_review.chat_rules(catalogue.read_text()) == awk.stdout.rstrip("\n")


def test_selected_rule_blocks_come_whole() -> None:
    assert turn_review.chat_rules(CATALOGUE_FIXTURE) == SELECTED


def test_a_catalogue_with_no_chat_rules_lets_the_record_through(
    worked_example: Path, writing: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalogue = tmp_path / "CATALOGUE.md"
    catalogue.write_text(CATALOGUE_FIXTURE.replace("`both`", "`artifact`").replace("`chat`", "`artifact`"))
    monkeypatch.setattr(turn_review, "CATALOGUE", catalogue)
    monkeypatch.setattr(turn_review, "review", reviewer(finding(IN_RECORD[0])))
    assert decide(wrote(worked_example / "turns" / "04.md", writing), worked_example).verb == "allow"


SKILL_FIXTURE = """## The session page

Prose before the shape.

### The turn record

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

## Who builds it

After the shape.
"""


def test_the_shape_runs_to_the_next_heading_past_the_example_records_own() -> None:
    shape = turn_review.record_shape(SKILL_FIXTURE)
    assert shape.startswith("The shape's prose.") and shape.endswith("- A rule about the record.")
    assert "# A headline inside the example" in shape and "## Details" in shape
    assert "Prose before" not in shape and "After the shape" not in shape


def test_the_turn_record_the_show_skill_gives_the_agent_parses(tmp_path: Path) -> None:
    """The oracle is the renderer's own reader: the example record the agent is shown is a record
    it accepts, and it uses every part a record can hold, so the skill and the parser cannot drift
    apart unnoticed."""
    shape = turn_review.record_shape(turn_review.SHOW.read_text())
    example = re.search(r"```markdown\n(.*?)```", shape, re.S).group(1)
    record = tmp_path / "07.md"
    record.write_text(example)
    turn = session_page.read_turn(record)
    assert turn.headline and turn.details and turn.links and turn.answered and turn.superseded
    (question,) = turn.questions
    assert len(question.options) >= 2 and sum(o.picked for o in question.options) == 1 and question.why


def test_a_show_skill_with_no_turn_record_section_lets_the_record_through(
    worked_example: Path, writing: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attended: Path,
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(SKILL_FIXTURE.replace("### The turn record", "### Another section"))
    monkeypatch.setattr(turn_review, "SHOW", skill)
    monkeypatch.setattr(turn_review, "review", reviewer(finding(IN_RECORD[0])))
    assert decide(wrote(worked_example / "turns" / "04.md", writing), worked_example).verb == "allow"
    (entry,) = logged(attended, "decision")
    assert entry["decision"] == "failed" and "The turn record" in entry["why"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
