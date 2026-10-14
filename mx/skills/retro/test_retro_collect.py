"""Checks for the workflow retro's collect stage, at the seam "The collect script's output"
(retro-semi-automated): given a directory of fixture transcripts and a fixture repo, which sessions
it digests, what each digest keeps, and which commits and tickets it collects for the period.
Run: make test, or pytest on this file with tyro, pyyaml and markdown-it-py.

The transcripts are synthetic, in the shape Claude Code writes, and the oracle is their own
content: the user's messages appear verbatim, tool output does not, and only commits after the
period's start are collected. Nothing lands in a git repository (retro-semi-automated#P2).
"""

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import retro_collect  # noqa: E402

SINCE = datetime(2026, 10, 5, tzinfo=UTC)
UNTIL = datetime(2026, 10, 12, tzinfo=UTC)


class Transcript:
    """One session's transcript under a profile's projects directory, entry by entry."""

    def __init__(self, projects: Path, cwd: str, start: datetime, entrypoint: str = "cli") -> None:
        self.sid, self.cwd, self.at, self.entrypoint = str(uuid.uuid4()), cwd, start, entrypoint
        self.path = projects / re.sub(r"[^A-Za-z0-9]", "-", cwd) / f"{self.sid}.jsonl"  # Claude Code's project name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict] = []
        self.last: str | None = None

    def add(self, entry: dict, parent: str | None = "last") -> "Transcript":
        self.at += timedelta(minutes=1)
        me = str(uuid.uuid4())
        self.entries.append({"parentUuid": self.last if parent == "last" else parent, "isSidechain": False,
                             "uuid": me, "timestamp": self.at.isoformat().replace("+00:00", "Z"),
                             "entrypoint": self.entrypoint, "cwd": self.cwd, "sessionId": self.sid,
                             "version": "2.1.300", **entry})
        self.last = me
        self.path.write_text("".join(json.dumps(e) + "\n" for e in self.entries))
        return self

    def says(self, text: str, parent: str | None = "last") -> "Transcript":
        return self.add({"type": "user", "message": {"role": "user", "content": text}, "origin": {"kind": "human"}}, parent)

    def answers(self, text: str) -> "Transcript":
        return self.add({"type": "assistant", "message": {"model": "claude-opus-5-5", "role": "assistant",
                                                          "content": [{"type": "text", "text": text}]}})

    def calls(self, tool: str, inputs: dict, result: str, error: bool = False, denial: str | None = None) -> "Transcript":
        tid = f"toolu_{uuid.uuid4().hex[:12]}"
        self.add({"type": "assistant", "message": {"model": "claude-opus-5-5", "role": "assistant",
                                                   "content": [{"type": "tool_use", "id": tid, "name": tool, "input": inputs}]}})
        return self.add({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": result, "is_error": error}]},
            **({"toolDenialKind": denial} if denial else {})})


def collect(tmp_path: Path, repos: list[Path] = (), seed: int = 0, since: datetime = SINCE) -> Path:
    run = tmp_path / "data" / "runs" / "1"
    retro_collect.collect_sessions(since, UNTIL, run, tmp_path / "data" / "cache", [tmp_path / ".claude" / "projects"],
                                   list(repos), seed)
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


def test_a_digested_session_is_read_from_the_cache_until_its_transcript_changes(
        tmp_path: Path, projects: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t = Transcript(projects, "/home/u/repos/agents", SINCE + timedelta(days=1)).says("first")
    first = (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text()
    digest = retro_collect.digest
    monkeypatch.setattr(retro_collect, "digest", fail_if_digested)

    assert (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text() == first

    monkeypatch.setattr(retro_collect, "digest", digest)
    t.says("second")
    assert "MAX: second" in (collect(tmp_path) / "sessions" / f"{t.sid}.md").read_text()


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


IDENTITY = {"GIT_AUTHOR_NAME": "max", "GIT_AUTHOR_EMAIL": "max@example.org", "GIT_COMMITTER_NAME": "max",
            "GIT_COMMITTER_EMAIL": "max@example.org", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def git(repo: Path, *args: str, when: datetime | None = None) -> None:
    env = {**os.environ, **IDENTITY, **({"GIT_AUTHOR_DATE": when.isoformat(), "GIT_COMMITTER_DATE": when.isoformat()} if when else {})}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def commit(repo: Path, files: dict[str, str | None], message: str, when: datetime) -> None:
    for name, text in files.items():
        path = repo / name
        if text is None:
            git(repo, "rm", "-q", name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message, when=when)


def ticket(status: str) -> str:
    return f"---\nstatus: {status}\npriority: 2\n---\n\n# A ticket\n"


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


def test_nothing_is_written_inside_a_git_repository(tmp_path: Path, repo: Path) -> None:
    Transcript(tmp_path / ".claude" / "projects", "/home/u/repos/agents", SINCE + timedelta(days=1)).says("hi")
    with pytest.raises(SystemExit):
        retro_collect.collect_sessions(SINCE, UNTIL, repo / "retro-run", tmp_path / "cache",
                                       [tmp_path / ".claude" / "projects"], [repo], 0)
    assert not (repo / "retro-run").exists() and not (tmp_path / "cache").exists()


def test_permissions_hold_each_profiles_rules_its_auto_mode_config_and_its_uncovered_bash_calls_of_the_period(
        tmp_path: Path, projects: Path) -> None:
    profile = projects.parent
    profile.mkdir(parents=True)
    settings = {"permissions": {"allow": ["Bash(make check)"], "deny": ["Bash(git push --force *)"]},
                "autoMode": {"allow": ["Pushing to my own branches"]}, "theme": "dark"}
    (profile / "settings.json").write_text(json.dumps(settings))
    t = Transcript(projects, "/home/u/repos/agents", SINCE - timedelta(hours=1))
    t.calls("Bash", {"command": "npm publish"}, "published")
    t.at = SINCE + timedelta(days=1)
    t.says("check and deploy").calls("Bash", {"command": "make check && make deploy"}, "ok")
    t.calls("Bash", {"command": "cat README.md"}, "readme")

    permissions = collect(tmp_path) / "permissions" / "claude"
    scan = json.loads((permissions / "scan.json").read_text())

    assert [r["example"] for r in scan["would_prompt"]] == ["make deploy"]
    assert [r["example"] for r in scan["auto_approved"]] == ["cat README.md"]
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


def test_proposed_names_the_agent_repos_commit_and_the_tickets_proposed_at_it(tmp_path: Path) -> None:
    agent = tmp_path / "agents" / "agent"
    agent.mkdir(parents=True)
    git(agent, "init", "-q", "-b", "main")
    commit(agent, {"tickets/slow-suite.md": ticket("proposed"), "tickets/board-link.md": ticket("open") + "\nIt moved from status: proposed to open.\n",
                   "tickets/hook-noise.md": ticket("proposed"), "show/hook-noise/report.md": "status: proposed\n"},
           "file tickets", SINCE)
    (agent / "tickets/hook-noise.md").write_text(ticket("open"))  # a session's edit, not yet committed
    run = tmp_path / "data" / "runs" / "1"
    retro_collect.collect_sessions(SINCE, UNTIL, run, tmp_path / "data" / "cache", [tmp_path / ".claude" / "projects"],
                                   [], 0, agent=agent)

    proposed = (run / "proposed.md").read_text()
    head = subprocess.run(["git", "-C", agent, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    assert head in proposed
    assert re.findall(r"^- (.+)$", proposed, re.M) == ["hook-noise", "slow-suite"]
