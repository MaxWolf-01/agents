"""Checks for the retro's collect stage, at the seam "The collect script's output"
(retro-semi-automated): given a directory of fixture transcripts and a fixture repo, which sessions
it digests, what each digest keeps, and which commits and tickets it collects for the period.
Run: make test, or pytest on this file with hypothesis, pyyaml and markdown-it-py[linkify].

The transcripts are synthetic, in the shape Claude Code writes, and the oracle is their own
content: max's messages appear verbatim, tool output does not, and only commits after the
period's start are collected. The older sample's draw is held as a property of any set of digests.
"""

import json
import os
import random
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import retro_collect
from retro_checks import SINCE, Transcript, commit, git, ticket

UNTIL = datetime(2026, 10, 12, tzinfo=UTC)


def collect(tmp_path: Path, repos: list[Path] = (), since: datetime = SINCE) -> Path:
    """What a workflow retro's collect writes of sessions, git and permissions."""
    run = tmp_path / "data" / "runs" / "1"
    projects = [tmp_path / ".claude" / "projects"]
    retro_collect.collect_sessions(since, UNTIL, run, tmp_path / "data" / "cache", projects, list(repos), sample_seed=0)
    retro_collect.collect_permissions(run, projects)
    return run


def everything(run: Path) -> str:
    return "\n".join(p.read_text() for p in sorted(run.rglob("*")) if p.is_file())


@pytest.fixture
def projects(tmp_path: Path) -> Path:
    return tmp_path / ".claude" / "projects"


@pytest.fixture(autouse=True)
def claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `claude` on PATH whose `auto-mode config` prints the profile it was run under, or with
    $CLAUDE_FAILS set fails, so that no test runs the real one."""
    bin = tmp_path / "bin"
    bin.mkdir()
    (bin / "claude").write_text('#!/usr/bin/env bash\n[ -n "${CLAUDE_FAILS:-}" ] && { echo "not logged in" >&2; exit 1; }\n'
                                'echo "{\\"profile\\": \\"$CLAUDE_CONFIG_DIR\\", \\"args\\": \\"$*\\"}"\n')
    (bin / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin}:{os.environ['PATH']}")
    return bin


def test_a_digest_keeps_maxs_messages_verbatim_and_no_tool_output(tmp_path: Path, projects: Path) -> None:
    message = "why did the suite take 20 min?\n\n- `make test` ran *everything*\n- again & again <sigh>"
    long_error = "Traceback (most recent call last):\n" + "  frame\n" * 900 + "AssertionError: boom"
    pasted = "line of a log\n" * 400
    written = "a paragraph of the file\n" * 600
    t = (Transcript(projects, "/home/u/repos/agents", SINCE + timedelta(days=1))
         .says(message)
         .answers("I'll check the suite's timings first.")
         .calls("Bash", {"command": "make test", "description": "run the suite"}, "TOOL-OUTPUT-MARKER 1109 s")
         .calls("Write", {"file_path": "/home/u/repos/agents/big.md", "content": written}, "File created")
         .calls("Bash", {"command": "pytest -x"}, long_error, error=True)
         .calls("Bash", {"command": "rm x"}, "rm: cannot remove 'x': Permission denied", error=True)
         .calls("Bash", {"command": "rm -rf build"}, "Permission to use Bash has been denied.", error=True, denial="user-rejected")
         .says(f"look at this <pasted_content id=\"1\">{pasted}</pasted_content> please"))

    digest = (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text()

    assert f"MAX: {message}" in digest
    assert "I'll check the suite's timings first." in digest
    assert '"command": "make test", "description": "run the suite"' in digest
    assert long_error in digest
    assert json.dumps(written) in digest
    assert "! DENIED Bash" in digest and "Permission to use Bash has been denied." in digest
    assert "! ERROR Bash: rm: cannot remove 'x': Permission denied" in digest
    assert "look at this line of a log" in digest and "chars clipped" in digest and pasted.strip() not in digest
    assert "TOOL-OUTPUT-MARKER" not in digest


def test_a_digest_marks_the_calls_the_auto_mode_classifier_allowed_and_names_the_ones_it_blocked(
        tmp_path: Path, projects: Path) -> None:
    # The permissionDecision shapes Claude Code 2.1.305 writes on a tool result's entry.
    by_classifier = {"decision": "accept", "source": "config", "reasonType": "classifier"}
    by_rule = {"decision": "accept", "source": "config", "reasonType": "rule"}
    blocked = "Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Git Destructive]."
    t = (Transcript(projects, "/home/u/repos/agents", SINCE + timedelta(days=1)).says("clean up the branch")
         .calls("Bash", {"command": "git reset --hard origin/main"}, "HEAD is now at 1a2b3c", decision=by_classifier)
         .calls("Read", {"file_path": "/home/u/repos/agents/README.md"}, "readme", decision=by_rule)
         .calls("Bash", {"command": "git push --force"}, blocked, error=True, denial="automode-blocked",
                decision={"decision": "reject", "source": "config", "reasonType": "classifier"})
         .says("no, that threw away my edits"))

    digest = (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text()

    assert '→ Bash [classifier allowed] {"command": "git reset --hard origin/main"}' in digest
    assert '→ Read {"file_path": "/home/u/repos/agents/README.md"}' in digest
    assert '→ Bash {"command": "git push --force"}' in digest
    assert f"! DENIED Bash (automode-blocked): {blocked}" in digest
    assert digest.count("[classifier allowed]") == 1


def test_a_digest_marks_what_max_did_to_a_turn_and_what_the_harness_did_to_it(tmp_path: Path, projects: Path) -> None:
    t = Transcript(projects, "/home/u/repos/agents", SINCE + timedelta(days=1)).says("hello").answers("Hi.")
    t.says("build the parser")
    before_it = t.entries[-1]["parentUuid"]
    t.answers("Building the lexer first.").says("parse dates too", parent=before_it)
    t.says("[Request interrupted by user]")
    t.add({"type": "attachment", "attachment": {"type": "queued_command", "prompt": "and the docs", "commandMode": "prompt"}})
    t.add({"type": "attachment", "attachment": {"type": "hook_additional_context", "content": ["run make check first"]}})
    t.add({"type": "system", "subtype": "stop_hook_summary", "preventedContinuation": True, "stopReason": "tests fail"})
    t.add({"type": "system", "subtype": "api_error", "error": "overloaded"})
    t.add({"type": "system", "subtype": "compact_boundary"})
    t.add({"type": "system", "subtype": "turn_duration", "durationMs": 252_000})

    digest = (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text()

    assert "MAX: build the parser" in digest
    assert "MAX REWOUND and re-sent (the agent's turn after the first send was abandoned): parse dates too" in digest
    for marker in ("MAX INTERRUPTED", "MAX (queued while the agent worked): and the docs", "! HOOK → agent: run make check first",
                   "! STOP HOOK blocked: tests fail", '! API ERROR "overloaded"', "(context compacted)", "(turn took 4m12s)"):
        assert marker in digest, marker


def test_the_period_holds_its_interactive_sessions_alone(tmp_path: Path, projects: Path) -> None:
    mine = Transcript(projects, "/home/u/repos/agents", SINCE + timedelta(days=2)).says("ship it")
    worker = Transcript(projects, "/home/u/repos/agents", SINCE + timedelta(days=2), entrypoint="sdk-cli").says("WORKER")
    before = Transcript(projects, "/home/u/repos/agents", SINCE - timedelta(days=1)).says("last week")

    run = collect(tmp_path)

    assert {p.stem for p in (run / "sessions").glob("*.md")} == {mine.sid}
    assert not any(s in everything(run) for s in ("WORKER", worker.sid, before.sid))


def test_every_claude_dot_projects_directory_under_the_home_is_a_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for d in (".claude/projects", ".claude-work/projects", ".config/claude/projects"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / ".claude.json").write_text("{}")
    monkeypatch.setenv("HOME", str(tmp_path))

    assert retro_collect.profiles() == [tmp_path / ".claude/projects", tmp_path / ".claude-work/projects"]


def test_a_session_that_started_before_the_period_holds_only_the_periods_days(tmp_path: Path, projects: Path) -> None:
    t = Transcript(projects, "/home/u/repos/agents", SINCE - timedelta(days=3)).says("before")
    t.at = SINCE - timedelta(days=1)
    t.says("the day before\n## 2026-10-06\nlooks like a day")
    t.at = SINCE + timedelta(hours=1)
    t.says("after")

    run = collect(tmp_path)
    digest = (run / "sessions" / f"{t.sid}.md").read_text()

    assert digest.startswith(f"# session {t.sid}")
    assert "left out: 2026-10-02 to 2026-10-04" in digest
    assert "MAX: after" in digest
    assert "MAX: before" not in digest and "the day before" not in digest


def test_the_cache_keeps_a_sessions_earlier_days_for_a_run_with_an_earlier_start(
        tmp_path: Path, projects: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t = Transcript(projects, "/home/u/repos/agents", SINCE - timedelta(days=3)).says("before")
    t.at = SINCE + timedelta(hours=1)
    t.says("after")
    collect(tmp_path)
    monkeypatch.setattr(retro_collect, "digest", fail_if_digested)

    digest = (collect(tmp_path, since=SINCE - timedelta(days=4)) / "sessions" / f"{t.sid}.md").read_text()

    assert "MAX: before" in digest and "MAX: after" in digest


def test_the_versions_are_those_that_ran_in_the_period_alone(tmp_path: Path, projects: Path) -> None:
    t = Transcript(projects, "/home/u/repos/agents", datetime(2026, 8, 15, tzinfo=UTC))
    t.says("in august")  # on 2.1.300, the version the session runs in the period too
    t.add({"type": "assistant", "message": {"model": "claude-fable-5", "role": "assistant",
                                            "content": [{"type": "text", "text": "August."}]}, "version": "2.1.233"})
    t.answers("Still August.")  # on claude-opus-5-5, the model it runs in the period too
    t.at = SINCE + timedelta(days=1)
    t.says("back in october").answers("October.")

    versions = (collect(tmp_path) / "versions.md").read_text()

    assert "2.1.300: first seen 2026-10-06, last seen 2026-10-06, in 1 sessions" in versions
    assert "claude-opus-5-5: first seen 2026-10-06, last seen 2026-10-06, in 1 sessions" in versions
    assert "2.1.233" not in versions and "claude-fable-5" not in versions


def test_a_session_whose_period_entries_draw_no_line_keeps_none_of_its_earlier_days(tmp_path: Path, projects: Path) -> None:
    t = Transcript(projects, "/home/u/repos/agents", SINCE - timedelta(days=1)).says("late on sunday")
    t.at = SINCE - timedelta(minutes=2)
    t.calls("Bash", {"command": "make test"}, "passed")  # the result lands after midnight, and draws no line

    digest = (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text()

    assert digest.startswith(f"# session {t.sid}") and "left out: 2026-10-04 to 2026-10-04" in digest
    assert "late on sunday" not in digest and "make test" not in digest


def fail_if_digested(*_: object) -> None:
    raise AssertionError("digested again, not read from the cache")


def test_a_digested_session_is_read_from_the_cache_until_its_transcript_changes(tmp_path: Path, projects: Path) -> None:
    t = Transcript(projects, "/home/u/repos/agents", SINCE + timedelta(days=1)).says("first")
    collect(tmp_path)
    cached = tmp_path / "data" / "cache" / f".claude-{t.sid}.json"
    entry = json.loads(cached.read_text())
    entry["digest"]["text"] += "CACHED-MARKER\n"
    cached.write_text(json.dumps(entry))

    assert "CACHED-MARKER" in (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text()

    t.says("second")
    again = (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text()
    assert "MAX: second" in again and "CACHED-MARKER" not in again


def test_a_digest_carries_the_session_pages_turn_records(tmp_path: Path, projects: Path) -> None:
    repo = tmp_path / "agents"
    repo.mkdir()
    git(repo, "init", "-q")
    t = Transcript(projects, str(tmp_path / "gone-worktree"), SINCE + timedelta(days=1)).says("grill me")
    turns = repo / "agent" / "sessions" / t.sid / "turns"
    turns.mkdir(parents=True)
    (turns / "01.md").write_text("---\ndate: 2026-10-06\n---\n\n# Round 1: TURN-RECORD-MARKER\n")

    digest = (collect(tmp_path, [repo]) / "sessions" / f"{t.sid}.md").read_text()

    assert "# Round 1: TURN-RECORD-MARKER" in digest


def test_the_older_sample_draws_from_two_to_eight_weeks_back_and_only_sessions_with_maxs_messages(
        tmp_path: Path, projects: Path) -> None:
    inside = {Transcript(projects, "/home/u/repos/agents", UNTIL - timedelta(weeks=w, hours=3)).says("old").sid
              for w in (2, 4, 7)}
    silent = Transcript(projects, "/home/u/repos/agents", UNTIL - timedelta(weeks=3)).answers("nobody spoke")
    too_old = Transcript(projects, "/home/u/repos/agents", UNTIL - timedelta(weeks=9)).says("ancient")
    too_new = Transcript(projects, "/home/u/repos/agents", UNTIL - timedelta(days=10)).says("recent")

    run = collect(tmp_path)

    assert {p.stem for p in (run / "sample").glob("*.md")} == inside
    assert {json.loads(r)["id"] for r in (run / "sessions.jsonl").read_text().splitlines()} >= inside
    assert not {silent.sid, too_old.sid, too_new.sid} & {p.stem for p in run.rglob("*.md")}


def digests_with(messages: list[int]) -> list[retro_collect.Digest]:
    return [retro_collect.Digest(sid=str(i), profile=".claude", cwd="/", start=SINCE, end=SINCE, interactive=True,
                                 messages=n, text="x") for i, n in enumerate(messages)]


@given(st.lists(st.integers(0, 30), max_size=40), st.integers(0, 25), st.integers())
def test_the_older_sample_draws_up_to_its_size_of_distinct_sessions_each_with_a_message_of_maxs(
        messages: list[int], k: int, seed: int) -> None:
    drawn = retro_collect.weighted_sample(digests_with(messages), k, random.Random(seed))

    assert len(drawn) == min(k, sum(n > 0 for n in messages))
    assert len({d.sid for d in drawn}) == len(drawn) and all(d.messages > 0 for d in drawn)


def test_the_older_sample_favours_a_session_with_more_of_maxs_messages() -> None:
    talkative, quiet = digests_with([10, 1])
    wins = sum(retro_collect.weighted_sample([talkative, quiet], 1, random.Random(seed)) == [talkative] for seed in range(2000))

    assert wins > 1600  # 10 to 1 odds draw it about 1818 times in 2000


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A code repo whose agent repo files, rules and drops tickets, either side of the period's start."""
    repo, agent = tmp_path / "proj", tmp_path / "proj" / "agent"
    for r in (repo, agent):
        r.mkdir(parents=True)
        git(r, "init", "-q", "-b", "main")
    commit(repo, {"a.py": "1"}, "BEFORE-THE-PERIOD", SINCE - timedelta(hours=1))
    commit(repo, {"a.py": "2"}, "AFTER-THE-PERIOD\n\nWhy: the suite was slow.", SINCE + timedelta(hours=1))
    commit(repo, {"a.py": "1"}, 'Revert "AFTER-THE-PERIOD"\n\nThis reverts commit abc.', SINCE + timedelta(hours=2))
    commit(agent, {"tickets/old.md": ticket("open")}, "file old", SINCE - timedelta(days=2))
    commit(agent, {"tickets/fast-suite.md": ticket("proposed")}, "file fast-suite", SINCE + timedelta(hours=1))
    commit(agent, {"tickets/fast-suite.md": ticket("review"), "show/fast-suite/report.md": "## Comments\n\nFRICTION: no uv\n"},
           "import fast-suite report", SINCE + timedelta(hours=2))
    commit(agent, {"tickets/old.md": None}, "drop old", SINCE + timedelta(hours=3))
    return repo


def test_git_holds_only_the_periods_commits_and_its_tickets(tmp_path: Path, repo: Path) -> None:
    record = (collect(tmp_path, [repo]) / "git" / "proj.md").read_text()

    assert "AFTER-THE-PERIOD" in record and "Why: the suite was slow." in record
    assert "BEFORE-THE-PERIOD" not in record
    assert "## Reverts (1)" in record
    assert "- fast-suite (" in record.split("### Filed")[1].split("###")[0]
    assert "proposed → review" in record
    assert "- old (" in record.split("### Deleted")[1]
    assert "FRICTION: no uv" in record
    assert "file old" not in record


def test_git_holds_a_commit_of_the_period_beneath_one_dated_before_it(tmp_path: Path) -> None:
    repo = tmp_path / "proj"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, {"a.py": "1"}, "IN-THE-PERIOD", SINCE + timedelta(hours=1))
    commit(repo, {"a.py": "2"}, "DATED-BEFORE-IT", SINCE - timedelta(hours=1))  # another host's clock, a rebase

    record = (collect(tmp_path, [repo]) / "git" / "proj.md").read_text()

    assert "IN-THE-PERIOD" in record
    assert "DATED-BEFORE-IT" not in record


def test_permissions_hold_each_profiles_rules_and_its_auto_mode_config(tmp_path: Path, projects: Path) -> None:
    profile = projects.parent
    profile.mkdir(parents=True)
    settings = {"permissions": {"allow": ["Bash(make check)"], "deny": ["AskUserQuestion"]},
                "autoMode": {"allow": ["Pushing to my own branches"]}, "theme": "dark"}
    (profile / "settings.json").write_text(json.dumps(settings))

    permissions = collect(tmp_path) / "permissions" / "claude"

    assert json.loads((permissions / "rules.json").read_text()) == {
        "settings.json": {"permissions": settings["permissions"], "autoMode": settings["autoMode"]}}
    assert json.loads((permissions / "auto-mode.json").read_text()) == {"profile": str(profile), "args": "auto-mode config"}


def test_an_auto_mode_config_that_could_not_be_read_says_why(
        tmp_path: Path, projects: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_FAILS", "1")

    permissions = collect(tmp_path) / "permissions" / "claude"

    assert not (permissions / "auto-mode.json").exists()
    assert "not logged in" in (permissions / "auto-mode.failed").read_text()


def test_the_ticket_lists_name_the_agent_repos_commit_and_the_tickets_proposed_and_in_flight_at_it(tmp_path: Path) -> None:
    agent = tmp_path / "agents" / "agent"
    agent.mkdir(parents=True)
    git(agent, "init", "-q", "-b", "main")
    commit(agent, {"tickets/slow-suite.md": ticket("proposed"), "tickets/board-link.md": ticket("open") + "\nIt moved from status: proposed to open.\n",
                   "tickets/hook-noise.md": ticket("proposed"), "show/hook-noise/report.md": "status: proposed\n",
                   "tickets/fast-board.md": ticket("review"), "tickets/old-board.md": ticket("done")},
           "file tickets", SINCE)
    (agent / "tickets/hook-noise.md").write_text(ticket("open"))  # a session's edit, not yet committed
    run = tmp_path / "data" / "runs" / "1"
    retro_collect.collect_sessions(SINCE, UNTIL, run, tmp_path / "data" / "cache", [tmp_path / ".claude" / "projects"],
                                   [], sample_seed=0, agent=agent)

    proposed = (run / "proposed.md").read_text()
    head = git(agent, "rev-parse", "HEAD").strip()

    assert head in proposed
    assert re.findall(r"^- (.+)$", proposed, re.M) == ["hook-noise", "slow-suite"]
    assert (run / "proposed/hook-noise.md").read_text() == ticket("proposed"), "each as it stood at the commit, not as a session left it"
    in_flight = (run / "in-flight.md").read_text()
    assert head in in_flight
    assert re.findall(r"^- (.+)$", in_flight, re.M) == ["board-link: open", "fast-board: review"]
    assert (run / "in-flight/board-link.md").read_text().startswith(ticket("open"))


def test_the_versions_name_each_mx_release_of_the_period_with_its_commit(tmp_path: Path) -> None:
    repo = tmp_path / "agents"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, {"mx/.claude-plugin/plugin.json": '{"version": "1.0.0"}'}, "mx v1.0.0", SINCE - timedelta(days=1))
    commit(repo, {"mx/.claude-plugin/plugin.json": '{"version": "1.0.1"}'}, "mx v1.0.1", SINCE + timedelta(days=1))
    sha = git(repo, "rev-parse", "--short=10", "HEAD").strip()

    versions = (collect(tmp_path, [repo]) / "versions.md").read_text()

    assert f"- 1.0.1 {sha} (" in versions and "mx v1.0.1" in versions
    assert "1.0.0" not in versions


def test_touched_names_per_repo_the_files_the_periods_commits_touched_that_it_still_tracks_most_touched_first(
        tmp_path: Path) -> None:
    repo, listed = tmp_path / "proj", tmp_path / "kb"
    for r in (repo, listed):
        r.mkdir()
        git(r, "init", "-q", "-b", "main")
    commit(repo, {"old.py": "1"}, "before the period", SINCE - timedelta(days=1))
    commit(repo, {"a.py": "1", "b.py": "1"}, "one", SINCE + timedelta(days=1))
    commit(repo, {"a.py": "2", "gone.py": "1"}, "two", SINCE + timedelta(days=2))
    commit(repo, {"gone.py": None}, "three", SINCE + timedelta(days=3))
    commit(repo, {"b.py": "2", "late.py": "1"}, "after the period", UNTIL + timedelta(days=1))
    commit(listed, {"note.md": "1"}, "a note", SINCE + timedelta(days=1))
    run = tmp_path / "data" / "runs" / "1"

    retro_collect.collect_touched(SINCE, UNTIL, run, [repo, listed])

    sections = (run / "touched.md").read_text().split("\n## ")[1:]
    assert [(head.splitlines()[0], re.findall(r"^- (.+)$", head, re.M)) for head in sections] == [
        (str(repo), ["2 a.py", "1 b.py"]), (str(listed), ["1 note.md"])]


def test_a_repo_retro_reads_the_sessions_that_worked_in_its_repos_their_removed_sibling_worktrees_included(
        tmp_path: Path, projects: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Helferline's tracker plans a repo outside its project root: a session works on it from the
    project root, from a worktree under the root, or from a worktree beside the repo that dispatch
    removed before the run."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project, api = tmp_path / "helferline", tmp_path / "api"
    for r in (project, project / "agent", api):
        r.mkdir(parents=True, exist_ok=True)
        git(r, "init", "-q", "-b", "main")
    commit(project, {".gitignore": "agent/\n"}, "start", SINCE - timedelta(days=9))
    commit(project / "agent", {"tickets/login.md": ticket("open", ("api",))}, "file login", SINCE - timedelta(days=9))
    commit(api, {"README.md": "1"}, "start", SINCE - timedelta(days=9))
    live, removed, other = tmp_path / "dispatch/api-review", api.parent / "api-login", api.parent / "api-old"
    for worktree in (live, removed):
        git(api, "worktree", "add", "-q", "-b", worktree.name, str(worktree))
    other.mkdir()  # another project that happens to share the prefix
    (tmp_path / "api-link").symlink_to(api)
    day = SINCE + timedelta(days=1)

    def session(cwd: Path, start: datetime = day) -> Transcript:
        return Transcript(projects, str(cwd), start).says("go on")

    root_edits_worktree = session(project).calls("Edit", {"file_path": f"{project}/.worktrees/login/x.py"}, "ok")
    edits_under_the_root = session(tmp_path).calls("Edit", {"file_path": f"{project}/.worktrees/login/y.py"}, "ok")
    edits_live_worktree = session(tmp_path).calls("Edit", {"file_path": f"{live}/login.py", "old_string": "a"}, "ok")
    edits_removed_worktree = session(tmp_path).calls("Write", {"file_path": f"{removed}/login.py", "content": "b"}, "ok")
    from_the_home = session(tmp_path).calls("Bash", {"command": "make -C ~/api-link test"}, "ok")
    a_heredoc = session(tmp_path).calls("Bash", {"command": f"bash <<'EOF'\n{api}/.venv/bin/pytest -q\nEOF"}, "ok")
    only_said = session(tmp_path).says(f"compare it with {api}/login.py").answers(f"I'll read {api}/login.py.")
    a_neighbour = session(tmp_path).calls("Bash", {"command": f"ls {other}/ && cat {api}2/x"}, "ok")
    before_the_period = session(tmp_path, SINCE - timedelta(days=2)).calls("Read", {"file_path": f"{api}/README.md"}, "1")
    before_the_period.at = day
    before_the_period.says("now something else").calls("Read", {"file_path": "/etc/hosts"}, "localhost")
    older_in_api = session(api, UNTIL - timedelta(weeks=4))
    older_elsewhere = session(tmp_path / "elsewhere", UNTIL - timedelta(weeks=4))
    git(api, "worktree", "remove", str(removed))
    run = tmp_path / "data" / "runs" / "1"

    retro_collect.collect_sessions(SINCE, UNTIL, run, tmp_path / "data" / "cache", [projects], [project, api], sample_seed=0,
                                   agent=project / "agent", worked=retro_collect.Worked.of([project, api]))

    worked = {root_edits_worktree.sid, edits_under_the_root.sid, edits_live_worktree.sid, edits_removed_worktree.sid, from_the_home.sid, a_heredoc.sid}
    assert {p.stem for p in (run / "sessions").glob("*.md")} == worked
    assert {p.stem for p in (run / "sample").glob("*.md")} == {older_in_api.sid}
    assert {json.loads(r)["id"] for r in (run / "sessions.jsonl").read_text().splitlines()} == worked | {older_in_api.sid}
    assert not {only_said.sid, a_neighbour.sid, before_the_period.sid, older_elsewhere.sid} & {p.stem for p in run.rglob("*.md")}
