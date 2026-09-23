# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown"]
# ///
"""Checks for the tracker command. Run: uv run test_tracker.py

One seam: the command line, driven in process, with a fixture tracker in a git repo on disk. The
oracle is `/mx:tracker` (MARKDOWN.md: the ticket file, ticket state, the frontier, retiring) and the
worker contract (`mx/skills/dispatch/worker-prompt.md`: the questions, the assumptions, `Addressed`),
transcribed here rather than imported, so a rule the command reads differently fails.

Under "properties" at the end sit the executable Properties of
`agent/tickets/ticket-file-contract.md`, P1 to P4 and P6; that ticket is their oracle. The corpus
beside this file is the board-orients feature converted to the one-ticket model by hand: real ticket
files, the shapes their writers actually wrote.
"""

import io
import json
import os
import re
import subprocess
import sys
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).parent))

import tracker as tr

CORPUS = Path(__file__).parent / "corpus"

# The transitions /mx:tracker's Ticket state defines: claim takes an open, proposed or review
# ticket; the worker flips its claim to review; the accept writes done; a ruling before the build
# and the redo ruling write open.
DEFINED = {
    ("proposed", "claimed"), ("open", "claimed"), ("review", "claimed"),
    ("claimed", "review"), ("review", "done"), ("proposed", "open"), ("review", "open"),
}
# the frontmatter's vocabularies as MARKDOWN.md's The ticket file writes them
STATUSES = ("proposed", "open", "claimed", "review", "done")
SIZES = ("XS", "S", "M", "L", "XL")
PRIORITIES = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Run:
    """One run of the command line: what it exited on, and what it said where."""

    code: int
    out: str
    err: str

    @property
    def said(self) -> str:
        return self.out + self.err


def run(at: Path, *argv: str, given: str = "") -> Run:
    """The command line, run in `at`: the tracker is found from the working directory, as it is for
    an agent typing this in the repo."""
    out, err, before, stdin = io.StringIO(), io.StringIO(), Path.cwd(), sys.stdin
    os.chdir(at)
    sys.stdin = io.StringIO(given)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = tr.cli(argv)
    finally:
        os.chdir(before)
        sys.stdin = stdin
    return Run(code, out.getvalue(), err.getvalue())


def ticket(tickets: Path, slug: str, body: str = "", **meta: object) -> Path:
    """A ticket file the tracker's rules accept, with `meta` on its frontmatter and `body` under its
    brief. The frontmatter is written the way MARKDOWN.md writes one, not the way the command does."""
    declared = {"status": "open", "priority": 1, "size": "M", **meta}
    written = "---\n" + "".join(f"{key}: {value}\n" for key, value in declared.items() if value is not None) + "---\n"
    written += f"\n# {slug.replace('-', ' ').capitalize()}\n\n## Brief\n\nWhat {slug} is, cold.\n"
    path = tickets / f"{slug}.md"
    path.write_text(written + (f"\n{body.strip()}\n" if body.strip() else ""))
    return path


def line_of(path: Path, words: str) -> int:
    """The line `words` sits on, as an editor counts: what a refusal has to name."""
    return next(n for n, line in enumerate(path.read_text().splitlines(), start=1) if words in line)


def git(at: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(at), *args], capture_output=True, text=True)
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
    return done.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An empty repo with a tracker in it, one commit deep."""
    git(tmp_path, "init", "-q", "-b", "main", ".")
    git(tmp_path, "config", "user.email", "checks@example.com")
    git(tmp_path, "config", "user.name", "checks")
    (tmp_path / "agent" / "tickets").mkdir(parents=True)
    (tmp_path / "README.md").write_text("the repo\n")
    git(tmp_path, "add", "README.md")
    git(tmp_path, "commit", "-q", "-m", "first")
    return tmp_path


@pytest.fixture
def tickets(repo: Path) -> Path:
    return repo / "agent" / "tickets"


def fresh(tickets: Path) -> Path:
    """The tracker emptied: a property's fixtures are function-scoped, so one run of it would
    otherwise file every example's tickets into the same tracker."""
    for path in tickets.glob("*.md"):
        path.unlink()
    return tickets


@pytest.fixture
def corpus(repo: Path, tickets: Path) -> Path:
    """The corpus as a tracker of its own: the reads below walk a tree, which needs a tracker root."""
    for path in corpus_tickets():
        (tickets / path.name).write_text(path.read_text())
    return repo


def corpus_tickets() -> list[Path]:
    return sorted(path for path in CORPUS.glob("*.md") if path.name != "README.md")


def without_tracker(repo: Path) -> Path:
    """A PATH holding git and nothing else, so the hook genuinely finds no tracker. The board's
    `path_with` cuts the running process's PATH down; what the hook runs in is git's own child, so
    this hands back the directory to give that child instead."""
    bin_dir = repo / "bare-path"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "git").symlink_to(subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip())
    return bin_dir


# ---- the check -------------------------------------------------------------


def test_a_ticket_the_rules_accept_is_refused_nothing(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow")
    assert run(repo, "check", "agent/tickets/one-flow.md") == Run(0, "", "")


@pytest.mark.parametrize("dropped, written, replacement", [
    ("the spec's status", {"status": "confirmed"}, "a ticket's status is one of"),
    ("a decision ticket's type", {"type": "grilling"}, "`needs-user` says whether the user is in the loop"),
    ("NN numbering", {"blocked-by": "[01]"}, "a reference names the blocking ticket's slug"),
    ("a feature/NN reference", {"blocked-by": "[csv-import/03]"}, "a feature is a ticket now, and a reference names a slug"),
])
def test_a_construct_the_one_ticket_model_drops_is_refused_with_what_replaced_it(
    tickets: Path, repo: Path, dropped: str, written: dict, replacement: str
) -> None:
    ticket(tickets, "one-flow", **written)
    said = run(repo, "check", "agent/tickets/one-flow.md")
    assert said.code == 1, dropped
    assert replacement in said.out, said.said


def test_a_ticket_numbered_the_old_way_is_refused_for_its_name(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow")
    path.rename(tickets / "01-one-flow.md")
    said = run(repo, "check", "agent/tickets/01-one-flow.md")
    assert said.code == 1
    assert "the file is `agent/tickets/<slug>.md`" in said.out


def test_a_spec_is_refused_as_the_top_level_ticket_it_becomes(tickets: Path, repo: Path) -> None:
    (tickets / "csv-import").mkdir()
    ticket(tickets / "csv-import", "spec")
    said = run(repo, "check", "agent/tickets/csv-import/spec.md")
    assert said.code == 1
    assert "becomes a top-level ticket" in said.out


def test_a_ruling_with_no_date_is_refused_rather_than_leaving_the_question_open(tickets: Path, repo: Path) -> None:
    """No reader takes an undated line as a ruling, so the question stays on the board for good."""
    path = ticket(tickets, "one-flow", "## Questions\n\n- [D1] **Ask?** Its detail.\n  - Ruled: yesterday.\n")
    said = run(repo, "check", str(path))
    assert said.code == 1
    assert f"{path}:{line_of(path, 'Ruled: yesterday')}: " in said.out
    assert "a ruling is `Ruled <date>: the answer`" in said.out


def test_a_stray_bullet_under_questions_is_refused_rather_than_swallowed(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow", "## Questions\n\n- [D1] **Ask?** Its detail.\n- A note, not a question.\n")
    said = run(repo, "check", str(path))
    assert said.code == 1
    assert f"{path}:{line_of(path, 'A note, not')}: this bullet is read as part of the question above it" in said.out


def test_a_tag_runs_as_one_sequence_across_the_questions_and_the_closing_comments_details(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow", "## Questions\n\n- [D1] **Ask?** Its detail.\n\n## Comments\n\n- [D1] Assumptions\n")
    said = run(repo, "check", str(path))
    assert said.code == 1
    assert f"tag D1 is already taken, on line {line_of(path, 'Ask?')}" in said.out


@pytest.mark.parametrize("written, refused", [
    ({"kind": "build"}, "`kind` is no ticket field"),
    ({"needs-user": "maybe"}, "`needs-user` is true or false"),
    ({"parent": "one-flow"}, "a ticket is not its own parent ticket"),
    ({"gh": "[acme/backend]"}, "a reference is `owner/repo#number`"),
    ({"diff": "[main..feature]"}, "a range is `<sha>..<sha>`"),
])
def test_a_frontmatter_field_no_reader_can_read_is_refused(tickets: Path, repo: Path, written: dict, refused: str) -> None:
    path = ticket(tickets, "one-flow", **written)
    said = run(repo, "check", str(path))
    assert said.code == 1 and refused in said.out, said.said


def test_a_file_name_that_is_no_slug_is_refused(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow")
    named = path.rename(tickets / "One_Flow.md")
    said = run(repo, "check", str(named))
    assert said.code == 1 and "is no slug" in said.out


def test_a_parent_that_closes_a_cycle_is_refused(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", parent="map-columns")
    ticket(tickets, "map-columns", parent="one-flow")
    said = run(repo, "check", str(tickets / "one-flow.md"))
    assert said.code == 1 and "closes a cycle" in said.out


def test_the_old_property_stamp_is_refused_with_the_citation_that_replaced_it(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow", "## Acceptance criteria\n\n- [ ] Property P3, reviewed: what this slice holds.\n")
    said = run(repo, "check", str(path))
    assert said.code == 1
    assert "a property is stated once and cited `<slug>#P<n>`" in said.out


def test_files_from_two_trackers_in_one_run_are_refused(tickets: Path, repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()
    said = run(repo, "check", str(ticket(tickets, "one-flow")), str(ticket(other, "map-columns")))
    assert said.code == 1 and "one tracker per run" in said.err


def test_an_id_that_names_two_things_is_refused_with_the_line_that_took_it_first(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow", "## Questions\n\n- [D1] **One?** Its detail.\n- [D1] **Two?** Its detail.\n")
    said = run(repo, "check", "agent/tickets/one-flow.md")
    assert said.code == 1
    assert f"{path}:{line_of(path, 'Two?')}: tag D1 is already taken, on line {line_of(path, 'One?')}" in said.out, said.out


def test_the_check_reads_the_staged_text_and_not_the_worktrees(tickets: Path, repo: Path) -> None:
    """What the commit hook has to hold: the commit is made of the index, so that is what is read."""
    path = ticket(tickets, "one-flow", priority=7)
    git(repo, "add", "-A")
    path.write_text(path.read_text().replace("priority: 7", "priority: 1"))
    said = run(repo, "check")
    assert said.code == 1, "the staged copy is the one being committed"
    assert "`priority: 7` is none of 1, 2, 3, 4, 5" in said.out


def test_the_commit_hook_blocks_a_commit_that_stages_a_ticket_no_reader_can_read(tickets: Path, repo: Path) -> None:
    assert run(repo, "hook").code == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    assert hook.exists() and os.access(hook, os.X_OK)

    ticket(tickets, "one-flow")
    git(repo, "add", "-A")
    on_path = {**os.environ, "PATH": f"{Path(tr.__file__).parents[2] / 'bin'}:{os.environ['PATH']}"}
    good = subprocess.run(["git", "-C", str(repo), "commit", "-m", "a ticket"], capture_output=True, text=True, env=on_path)
    assert good.returncode == 0, good.stderr

    path = ticket(tickets, "map-columns", "## Questions\n\n- [D1] **Ask?** Its detail.\n- [D1] **Again?** Its detail.\n")
    git(repo, "add", "-A")
    blocked = subprocess.run(["git", "-C", str(repo), "commit", "-m", "a malformed ticket"], capture_output=True, text=True, env=on_path)
    assert blocked.returncode != 0
    said = blocked.stdout + blocked.stderr  # git hands a hook's own stdout to the commit's stderr
    assert f"{path}:{line_of(path, 'Again?')}: tag D1 is already taken" in said, said


def test_the_commit_hook_says_so_when_there_is_no_tracker_on_path_rather_than_passing_in_silence(tickets: Path, repo: Path) -> None:
    run(repo, "hook")
    ticket(tickets, "one-flow", priority=7)
    git(repo, "add", "-A")
    bare = {**os.environ, "PATH": str(without_tracker(repo))}
    said = subprocess.run(["git", "-C", str(repo), "commit", "-m", "unchecked"], capture_output=True, text=True, env=bare)
    assert said.returncode == 0, "a missing tool does not block the commit"
    assert "no tracker on PATH" in said.stderr


def test_a_pre_commit_hook_this_did_not_write_is_left_standing(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 0\n")
    said = run(repo, "hook")
    assert said.code == 1
    assert "add `tracker check` to it by hand" in said.err
    assert hook.read_text() == "#!/bin/sh\nexit 0\n"


# ---- the reads -------------------------------------------------------------


def test_one_field_is_printed_for_a_shell_to_read(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", status="claimed")
    assert run(repo, "get", "one-flow", "status").out == "claimed\n"
    assert run(repo, "get", "one-flow", "diff").code == 1


def test_the_frontier_is_what_can_be_started_now_in_the_order_it_matters(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", status="open", priority=2)
    ticket(tickets, "map-columns", status="proposed", priority=1)
    ticket(tickets, "saved-views", status="open", priority=4)
    ticket(tickets, "pick-a-date-library", status="open", priority=1, **{"needs-user": "true"})
    ticket(tickets, "speed-up-tests", status="claimed", priority=1)
    ticket(tickets, "flaky-upload", status="review", priority=1)
    ticket(tickets, "retire-exporter", status="done", priority=1)
    ready, _, waiting = run(repo, "frontier").out.partition("waiting\n")
    assert [line.split()[0] for line in ready.splitlines()] == ["map-columns", "one-flow", "saved-views"], "by priority"
    held = dict(line.split(maxsplit=1) for line in waiting.splitlines())
    assert held.keys() == {"pick-a-date-library", "speed-up-tests", "flaky-upload"}
    assert "on the user, who is in the loop for it" in held["pick-a-date-library"]
    assert "claimed, not the frontier's" in held["speed-up-tests"]
    assert "review, not the frontier's" in held["flaky-upload"], "a build waiting on a ruling is nobody's to take up"
    assert "retire-exporter" not in ready + waiting, "a done ticket is off the board's work"


def test_a_blocker_in_review_unblocks_nothing(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", status="review")
    ticket(tickets, "map-columns", status="open", **{"blocked-by": "[one-flow]"})
    ready, _, waiting = run(repo, "frontier").out.partition("waiting\n")
    assert "map-columns" not in ready and "on one-flow (review)" in waiting, "a dependent never builds on a guess"


def test_the_tracker_as_data_carries_every_construct_a_reader_asks_for(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", """
## Properties

- P1 A ticket is read whole or refused.

## Acceptance criteria

- [x] `one-flow#P1` holds.
- [ ] The rest.

## Questions

- [D1] **Ask?** Its detail.
  - Ruled 2026-09-21: keep it.

## Comments

Addressed: C1, C4

- [D2] Assumptions
  - A1 `mx/skills/tracker/tracker.py:12`: the call and why.
""", **{"gh": "[acme/backend#317]", "diff": "[4f2a91c..8b3ce07]"})
    read = json.loads(run(repo, "data", "one-flow").out)["tickets"][0]
    assert read["slug"] == "one-flow" and read["status"] == "open" and read["priority"] == 1
    assert read["gh"] == ["acme/backend#317"] and read["diff"] == ["4f2a91c..8b3ce07"]
    assert read["title"] == "One flow" and read["brief"] == "What one-flow is, cold."
    assert [p["id"] for p in read["properties"]] == ["P1"]
    assert [(c["met"], c["cites"]) for c in read["criteria"]] == [(True, ["one-flow#P1"]), (False, [])]
    assert [(q["tag"], q["ruled"], q["answer"]) for q in read["questions"]] == [("D1", "2026-09-21", "keep it.")]
    assert read["resolved"] == ["C1", "C4"]
    assert [note["text"] for note in read["assumptions"]] == ["the call and why."]
    assert [s["heading"] for s in read["sections"]] == ["Brief", "Properties", "Acceptance criteria", "Questions", "Comments"]


def test_a_ticket_on_stdin_is_read_the_same_way_as_one_on_disk(tickets: Path, repo: Path) -> None:
    """How a review page reads a build's assumptions: the ticket's own branch has them, the
    checkout does not."""
    path = ticket(tickets, "one-flow", "## Comments\n\n- [D1] Assumptions\n  - A1 `mx/x.py:1`: the call.\n")
    given = json.loads(run(repo, "data", "-", given=path.read_text()).out)["tickets"][0]
    assert given["assumptions"] == [{"id": 1, "path": "mx/x.py", "line": 1, "text": "the call.",
                                    "at": line_of(path, "A1 `mx/x.py:1`")}]
    for read in (("data", "one-flow"), ("data", str(path))):
        assert json.loads(run(repo, *read).out)["tickets"][0]["assumptions"] == given["assumptions"], read


def test_a_ticket_the_rules_refuse_is_refused_by_every_read_and_not_just_the_check(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow", "## Comments\n\n- A1 no anchor here.\n")
    for read in (("data",), ("data", "one-flow"), ("data", str(path)), ("context", "one-flow"), ("frontier",)):
        said = run(repo, *read)
        assert said.code == 1, read
        assert f"one-flow.md:{line_of(path, 'A1 no anchor')}:" in said.err, (read, said.said)


# ---- the writes ------------------------------------------------------------


def test_filing_writes_the_frontmatter_and_the_skeleton_and_leaves_the_body_to_the_agent(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow")
    said = run(repo, "new", "map-columns", "--parent", "one-flow", "--priority", "2", "--size", "M")
    assert said.code == 0 and said.out.strip() == str(tickets / "map-columns.md")
    filed = (tickets / "map-columns.md").read_text()
    assert filed.startswith("---\nstatus: proposed\nparent: one-flow\npriority: 2\nsize: M\n---\n")
    assert "## Brief" in filed and "## Acceptance criteria" in filed and "## Comments" in filed
    assert run(repo, "check", "agent/tickets/map-columns.md").code == 0
    assert run(repo, "new", "map-columns", "--priority", "2", "--size", "M").code == 1, "a slug names one ticket"


def test_filing_a_ticket_under_a_parent_that_is_no_ticket_is_refused(tickets: Path, repo: Path) -> None:
    said = run(repo, "new", "map-columns", "--parent", "nowhere", "--priority", "2", "--size", "M")
    assert said.code == 1 and "names no ticket" in said.err
    assert not (tickets / "map-columns.md").exists()


def test_every_status_transition_the_tracker_defines_is_accepted_and_every_other_is_refused_with_its_rule(
    tickets: Path, repo: Path
) -> None:
    """The whole space, since it is small enough to enumerate. Every ticket here has a branch merged
    into this one, so `done` turns on the transition alone; the merge is its own rule below."""
    for before in STATUSES:
        for after in STATUSES:
            slug = f"t-{before}-{after}"
            path = ticket(tickets, slug, status=before)
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", slug)
            git(repo, "branch", f"ticket/{slug}")  # merged by construction: it points at this tip
            said = run(repo, "set", slug, f"status={after}")
            allowed = before == after or (before, after) in DEFINED
            assert (said.code == 0) is allowed, (before, after, said.said)
            if not allowed:
                rule = said.err.split(f"{slug} {before} → {after}: ")[1]
                assert len(rule.split()) > 6, f"the rule that forbids it is named: {said.err}"
            assert run(repo, "get", slug, "status").out.strip() == (after if allowed else before)


def test_done_waits_for_the_merge_of_what_the_ticket_built(tickets: Path, repo: Path) -> None:
    ticket(tickets, "map-columns", status="review")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "map-columns")
    git(repo, "checkout", "-q", "-b", "ticket/map-columns")
    (repo / "columns.py").write_text("built\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the build")
    git(repo, "checkout", "-q", "main")

    said = run(repo, "set", "map-columns", "status=done")
    assert said.code == 1 and "ticket/map-columns is not merged into main" in said.err
    git(repo, "merge", "-q", "--no-ff", "ticket/map-columns", "-m", "land map-columns")
    assert run(repo, "set", "map-columns", "status=done").code == 0


def test_a_parent_ticket_is_done_once_every_child_ticket_is(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", status="review")
    children = [ticket(tickets, "map-columns", status="done", parent="one-flow"),
                ticket(tickets, "saved-views", status="review", parent="one-flow")]
    said = run(repo, "set", "one-flow", "status=done")
    assert said.code == 1 and "no branch ticket/one-flow here" in said.err, "one child still waits on a ruling"
    for child in children:
        child.write_text(child.read_text().replace("status: review", "status: done"))
    assert run(repo, "set", "one-flow", "status=done").code == 0


def test_a_write_the_rules_refuse_leaves_the_file_as_it_was(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow")
    before = path.read_text()
    assert run(repo, "set", "one-flow", "blocked-by=[nowhere]").code == 1
    assert run(repo, "set", "one-flow", "priority=9").code == 1
    assert run(repo, "set", "one-flow", "kind=build").code == 1
    assert path.read_text() == before


def test_a_range_is_appended_and_lands_away_from_the_status_line(tickets: Path, repo: Path) -> None:
    """Where `diff` goes matters: a ticket branch writes `status` too, and adjacent lines conflict."""
    path = ticket(tickets, "one-flow")
    run(repo, "set", "one-flow", "diff+=4f2a91c..8b3ce07")
    run(repo, "set", "one-flow", "diff+=aaaaaaa..bbbbbbb")
    lines = path.read_text().splitlines()
    assert "diff: [4f2a91c..8b3ce07, aaaaaaa..bbbbbbb]" in lines
    assert lines.index("diff: [4f2a91c..8b3ce07, aaaaaaa..bbbbbbb]") > lines.index("status: open") + 1


def test_a_ruling_goes_under_the_question_it_answers(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow", """
## Questions

- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake
  clock makes the test say nothing about timing.
- [D2] **Keep the test in the fast suite?** It takes four seconds either way.
""")
    assert run(repo, "rule", "one-flow", "D1", "fake the clock").code == 0
    read = json.loads(run(repo, "data", "one-flow").out)["tickets"][0]["questions"]
    assert [(q["tag"], q["answer"]) for q in read] == [("D1", "fake the clock"), ("D2", "")]
    assert "  - Ruled " in path.read_text()
    assert run(repo, "rule", "one-flow", "D1", "again").code == 1, "a ruled question is amended in place"
    assert run(repo, "rule", "one-flow", "D9", "nothing").code == 1


# ---- the corpus ------------------------------------------------------------


def test_the_real_ticket_files_of_this_tracker_are_read_whole() -> None:
    """The board-orients feature, converted to the one-ticket model by hand. Its worker wrapped the
    assumption bullets at about a hundred columns, which is how every note on its review page came
    out cut mid-sentence: they read whole here."""
    said = run(CORPUS, "check", *[str(path) for path in corpus_tickets()])
    assert said == Run(0, "", ""), said.said

    read = json.loads(run(CORPUS, "data", str(CORPUS / "board-orients-workflow.md")).out)["tickets"][0]
    assert len(read["assumptions"]) == 12
    assert read["assumptions"][5]["text"] == (
        "a relayed question carries two numberings, the ticket's and the relaying session's, as that "
        "sentence already said before this ticket."
    ), "the note the review page cut at \"the ticket's and\""
    assert all(note["text"].endswith(".") for note in read["assumptions"])
    assert [q["tag"] for q in read["questions"]] == ["D1", "D2", "D3", "D4", "D5"]
    assert all(q["ruled"] == "2026-09-23" for q in read["questions"])


def test_the_corpus_reads_as_one_tree(corpus: Path) -> None:
    """The feature's spec became the top-level ticket and its four tickets its child tickets."""
    read = {one["slug"]: one for one in json.loads(run(corpus, "data").out)["tickets"]}
    assert read["board-orients"]["children"] == [
        "board-orients-property-checks", "board-orients-questions-and-needs-me",
        "board-orients-rows", "board-orients-workflow",
    ]
    assert read["board-orients-workflow"]["ancestors"] == ["board-orients"]
    assert read["board-orients"]["ancestors"] == [] and read["board-orients-rows"]["children"] == []
    assert [p["id"] for p in read["board-orients"]["properties"]] == [f"P{n}" for n in range(1, 12)]
    assert read["board-orients-workflow"]["criteria"][0]["cites"] == ["board-orients#P1"]


# ---- properties ------------------------------------------------------------
# The executable Properties of agent/tickets/ticket-file-contract.md, at the one seam that ticket
# names: the command line. P5 is reviewed, not executable, and is not here.

WORDS = st.lists(
    st.sampled_from("retry the clock suite upload mapping bank payee ledger board window column".split()),
    min_size=4, max_size=25,
).map(" ".join)
WIDTH = st.integers(min_value=26, max_value=140)  # the column a writer's editor wraps at
ANCHOR = st.sampled_from(["mx/skills/tracker/tracker.py", "agent/tickets/one-flow.md", "Makefile"])
ASKED = st.lists(st.tuples(WORDS, WORDS), min_size=1, max_size=5)
ASSUMED = st.lists(st.tuples(ANCHOR, st.one_of(st.none(), st.integers(1, 900)), WORDS), min_size=1, max_size=6)


def wrapped(line: str, width: int) -> str:
    """One bullet as a writer's editor leaves it: wrapped at `width`, its later lines indented under
    the first. A path in backticks is one word and is never broken."""
    indent = " " * (len(line) - len(line.lstrip()) + 2)
    return textwrap.fill(line, width=max(width, 20), subsequent_indent=indent, break_long_words=False, break_on_hyphens=False)


def asking(asked: list) -> list[str]:
    return [f"- [D{n}] **{headline}?** {detail}." for n, (headline, detail) in enumerate(asked, start=1)]


def assuming(assumed: list) -> list[str]:
    return [f"  - A{n} `{path}{f':{line}' if line else ''}`: {text}."
            for n, (path, line, text) in enumerate(assumed, start=1)]


def saying(questions: list[str], notes: list[str], width: int) -> str:
    """A ticket body carrying those bullets, each wrapped where the writer's editor would wrap it."""
    asked = "\n".join(wrapped(bullet, width) for bullet in questions)
    assumed = "\n".join(wrapped(bullet, width) for bullet in notes)
    return f"## Questions\n\n{asked}\n\n## Comments\n\n- [D{len(questions) + 1}] Assumptions\n{assumed}\n"


@given(asked=ASKED, assumed=ASSUMED, width=WIDTH)
@settings(max_examples=120, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p1_text_in_a_machine_read_part_is_read_whole_however_the_writer_wrapped_it(
    tickets: Path, repo: Path, asked: list, assumed: list, width: int
) -> None:
    """board-orients 10 wrapped its assumptions at about a hundred columns and every note on its
    review page came out cut mid-sentence. Whatever column the writer wrapped at, the text arrives."""
    ticket(fresh(tickets), "one-flow", saying(asking(asked), assuming(assumed), width))
    said = run(repo, "data", "one-flow")
    assert said.code == 0, said.said
    read = json.loads(said.out)["tickets"][0]
    assert [(q["headline"], q["detail"]) for q in read["questions"]] == [(f"{headline}?", f"{detail}.") for headline, detail in asked]
    assert [(a["path"], a["line"], a["text"]) for a in read["assumptions"]] == [(path, line, f"{text}.") for path, line, text in assumed]


# What a writer can leave in a machine-read part that no reader can read, with the rule the refusal
# has to name.
BREAKS = [
    ("assuming", lambda bullet: bullet.replace("`", "", 2), "the review page would drop it"),
    ("asking", lambda bullet: bullet.replace("**", ""), "a question is `- [Dn] **headline** detail`"),
]


@given(asked=ASKED, assumed=ASSUMED, width=WIDTH, breaking=st.sampled_from(BREAKS), which=st.integers(0, 9))
@settings(max_examples=80, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p1_a_machine_read_part_no_reader_can_read_is_refused_with_its_file_and_line(
    tickets: Path, repo: Path, asked: list, assumed: list, width: int, breaking: tuple, which: int
) -> None:
    """The other half of the property: what is not read whole is refused where it was written, never
    dropped in silence."""
    where, mangle, rule = breaking
    written = {"asking": asking(asked), "assuming": assuming(assumed)}
    broken = which % len(written[where])
    written[where][broken] = mangle(written[where][broken])
    path = ticket(fresh(tickets), "one-flow", saying(written["asking"], written["assuming"], width))

    opens = wrapped(written[where][broken], width).splitlines()[0]
    said = run(repo, "check", str(path))
    assert said.code == 1, (opens, said.said)
    assert f"{path}:{line_of(path, opens)}: " in said.out, (opens, said.out)
    assert rule in said.out, (opens, said.out)


@given(status=st.sampled_from(STATUSES), priority=st.sampled_from(PRIORITIES), size=st.sampled_from(SIZES))
@settings(max_examples=40, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p2_every_machine_read_construct_has_one_parser_so_every_read_says_the_same(
    tickets: Path, repo: Path, status: str, priority: int, size: str
) -> None:
    """One parser means no reader can drift from another: the field a shell asks for, the constructs
    the JSON carries whichever way the ticket is handed over, and the line the frontier prints are
    one read."""
    path = ticket(fresh(tickets), "one-flow", "## Questions\n\n- [D1] **Ask?** Its detail.\n\n"
                  "## Comments\n\n- [D2] Assumptions\n  - A1 `mx/x.py:1`: the call and why.\n",
                  status=status, priority=priority, size=size)
    read = json.loads(run(repo, "data", "one-flow").out)["tickets"][0]
    assert run(repo, "get", "one-flow", "status").out.strip() == read["status"] == status
    assert run(repo, "get", "one-flow", "priority").out.strip() == str(read["priority"]) == str(priority)
    assert run(repo, "get", "one-flow", "size").out.strip() == read["size"] == size
    for handed in (("data", str(path)), ("data", "-")):
        other = json.loads(run(repo, *handed, given=path.read_text()).out)["tickets"][0]
        assert other["questions"] == read["questions"] and other["assumptions"] == read["assumptions"], handed
        assert other["title"] == read["title"] and other["brief"] == read["brief"], handed

    row = f"one-flow                                    {status:<10}p{priority}  {size}"
    ready, _, waiting = run(repo, "frontier").out.partition("waiting\n")
    assert (row in ready + waiting) is (status != "done"), run(repo, "frontier").out


DANGLING = [
    ("parent", lambda slug: {"parent": slug}, ""),
    ("blocked-by", lambda slug: {"blocked-by": f"[{slug}]"}, ""),
    ("a property citation", lambda slug: {}, "## Acceptance criteria\n\n- [ ] `{slug}#P1` holds.\n"),
]


@given(ref=st.from_regex(r"\A[a-z][a-z-]{2,20}[a-z]\Z"), naming=st.sampled_from(DANGLING))
@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p3_a_reference_that_names_no_ticket_or_property_is_refused_with_its_file_and_line(
    tickets: Path, repo: Path, ref: str, naming: tuple
) -> None:
    what, meta, body = naming
    ticket(fresh(tickets), "on-the-tracker")
    path = ticket(tickets, "one-flow", body.replace("{slug}", ref), **meta(ref))
    said = run(repo, "check", str(path))
    assert said.code == 1, (what, said.said)
    assert f"{path}:{line_of(path, ref)}: " in said.out, (what, said.out)

    held = ticket(tickets, "one-flow", body.replace("{slug}", "on-the-tracker"), **meta("on-the-tracker"))
    resolves = run(repo, "check", str(held))
    assert (resolves.code == 0) is (what != "a property citation"), "on-the-tracker states no P1"


@given(depth=st.integers(min_value=1, max_value=5))
@settings(max_examples=12, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p4_a_tickets_context_is_its_body_and_every_ancestors_body(
    tickets: Path, repo: Path, depth: int
) -> None:
    """One assembly, in one order: the ticket, then its ancestors as the work widens."""
    fresh(tickets)
    chain = [f"level-{n}" for n in range(depth)]
    for n, slug in enumerate(chain):
        ticket(tickets, slug, f"## Acceptance criteria\n\n- [ ] What {slug} has to hold.\n",
               parent=chain[n - 1] if n else None)
    ticket(tickets, "beside-it", "## Acceptance criteria\n\n- [ ] What beside-it has to hold.\n")

    said = run(repo, "context", chain[-1])
    assert said.code == 0, said.said
    marked = re.findall(r"^## ((?:parent ticket: )?level-\d)$", said.out, re.M)
    assert marked == [chain[-1]] + [f"parent ticket: {slug}" for slug in reversed(chain[:-1])], \
        "the marker says whose body follows, which is what tells a worker its own from its context"
    assert all(f"What {slug} has to hold." in said.out for slug in chain)
    assert "beside-it" not in said.out

    if depth > 1:
        (tickets / f"{chain[0]}.md").unlink()
        gone = run(repo, "context", chain[-1])
        assert gone.code == 1 and "names no ticket" in gone.err


def test_p6_retiring_loses_nothing_git_history_or_the_logs_does_not_keep(
    tickets: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fixture tracker holding one of each kind of file a ticket owns, with the route each takes
    printed as it runs: git history, ~/logs, or deletion for a render its tracked source redraws."""
    home = repo / "home"
    monkeypatch.setenv("HOME", str(home))
    show = repo / "agent" / "show"
    for directory in ("one-flow", "map-columns/out", "saved-views/out"):
        (show / directory).mkdir(parents=True)
    (repo / "agent" / "research").mkdir()
    (repo / "agent" / "prototypes" / "one-flow").mkdir(parents=True)

    kept = {  # tracked: git history holds it after the git rm
        show / "one-flow" / "flow.mmd": "flowchart\n",
        show / "map-columns" / "demo": "#!/bin/sh\necho the demo\n",
        repo / "agent" / "prototypes" / "one-flow" / "board.py": "the prototype\n",
    }
    deleted = {  # untracked renders, each beside the tracked source that redraws it
        show / "one-flow" / "flow.svg": "<svg/>\n",
        show / "map-columns" / "out" / "transcript.txt": "what the run printed\n",
    }
    moved = {  # untracked, with no source to redraw them: they leave for ~/logs
        show / "one-flow" / "by-hand.txt": "written by hand\n",
        show / "saved-views" / "out" / "gathered.txt": "no source beside it redraws this\n",
        repo / "agent" / "research" / "03-columns.md": "what the reading found\n",
    }
    for path, text in {**kept, **deleted, **moved}.items():
        path.write_text(text)

    ticket(tickets, "one-flow", "Its prototype is agent/prototypes/one-flow/ and its reading agent/research/03-columns.md.", status="done")
    ticket(tickets, "map-columns", parent="one-flow", status="done")
    ticket(tickets, "saved-views", parent="map-columns", status="done")  # a grandchild goes too
    ticket(tickets, "speed-up-tests", **{"blocked-by": "[one-flow]"})
    ticket(tickets, "flaky-upload", "It reads agent/research/06-timing.md.")
    (repo / "agent" / "research" / "06-timing.md").write_text("what a ticket that stays still cites\n")
    git(repo, "add", "agent/tickets", *[str(path) for path in kept])
    git(repo, "commit", "-q", "-m", "the work")

    said = run(repo, "retire", "one-flow")
    assert said.code == 0, said.said
    assert "retired one-flow and 2 child tickets; staged, not committed" in said.out

    for path, text in kept.items():
        assert not path.exists(), path
        assert git(repo, "show", f"HEAD:{path.relative_to(repo)}") == text, "git history keeps it"
        assert f"D  {path.relative_to(repo)}" in git(repo, "status", "--short"), "and the removal is staged"
        assert str(path.relative_to(repo)) in said.out, "the run says where it went"
    for path in deleted:
        assert not path.exists() and not (home / "logs").joinpath(path.relative_to(repo)).exists()
        assert f"rm {path.relative_to(repo)}" in said.out
        source = next(one for one in kept if one.parent in (path.parent, path.parent.parent))
        assert git(repo, "show", f"HEAD:{source.relative_to(repo)}"), \
            f"{path} is deleted only because the source beside it, {source}, is tracked"
    for path, text in moved.items():
        assert not path.exists(), path
        assert (home / "logs" / "agent" / repo.name / path.relative_to(repo)).read_text() == text
    assert (repo / "agent" / "research" / "06-timing.md").exists(), "a note a ticket that stays cites stays"
    assert sorted(path.name for path in tickets.glob("*.md")) == ["flaky-upload.md", "speed-up-tests.md"]
    assert git(repo, "show", "HEAD:agent/tickets/one-flow.md"), "and history holds the tickets"
    assert not (show / "one-flow").exists() and not (show / "map-columns").exists(), "and the emptied directories go"

    assert run(repo, "get", "speed-up-tests", "blocked-by").code == 1, "the edge onto a retired ticket goes with it"
    assert "M  agent/tickets/speed-up-tests.md" in git(repo, "status", "--short"), "staged with the rest"
    assert run(repo, "check", str(tickets / "speed-up-tests.md")).code == 0


def test_retiring_is_refused_while_a_ticket_that_stays_cites_a_property_of_one_leaving(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", "## Properties\n\n- P1 A ticket is read whole or refused.\n", status="done")
    path = ticket(tickets, "map-columns", "## Acceptance criteria\n\n- [ ] `one-flow#P1` holds.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the tickets")
    said = run(repo, "retire", "one-flow")
    assert said.code == 1 and f"{path}:{line_of(path, 'one-flow#P1')}: one-flow#P1" in said.err
    assert (tickets / "one-flow.md").exists()


@pytest.mark.parametrize("status", ["proposed", "open", "claimed", "review"])
def test_dropping_takes_a_ticket_nothing_shipped_out_and_leaves_no_edge_onto_it(
    tickets: Path, repo: Path, status: str
) -> None:
    """The reject ruling: the file goes, git history keeps it and the reason the commit gives, and
    the tickets that stay are left with no reference that names no ticket."""
    ticket(tickets, "pick-a-date-library", status=status)
    staying = ticket(tickets, "map-columns", **{"blocked-by": "[pick-a-date-library, one-flow]"})
    ticket(tickets, "one-flow")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the tickets")

    said = run(repo, "drop", "pick-a-date-library")
    assert said.code == 0, said.said
    assert said.out.splitlines() == [
        "+ git rm -q agent/tickets/pick-a-date-library.md",
        "+ drop pick-a-date-library from map-columns's blocked-by",
        "+ git add agent/tickets/map-columns.md",
        "dropped pick-a-date-library; staged, not committed",
    ], said.out
    assert not (tickets / "pick-a-date-library.md").exists()
    assert git(repo, "show", "HEAD:agent/tickets/pick-a-date-library.md"), "git history keeps the file"
    assert "D  agent/tickets/pick-a-date-library.md" in git(repo, "status", "--short"), "and the removal is staged"
    assert run(repo, "get", "map-columns", "blocked-by").out == "one-flow\n", "the edge onto it goes, the others stay"
    assert "M  agent/tickets/map-columns.md" in git(repo, "status", "--short")
    assert run(repo, "check", str(staying)).code == 0, "nothing is left naming no ticket"


def test_dropping_a_done_ticket_is_refused_as_retirings(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", status="done")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the ticket")
    said = run(repo, "drop", "one-flow")
    assert said.code == 1 and "retiring is what takes shipped work out" in said.err
    assert (tickets / "one-flow.md").exists()


def test_dropping_is_refused_while_a_ticket_that_stays_names_it(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", "## Properties\n\n- P1 A ticket is read whole or refused.\n")
    child = ticket(tickets, "map-columns", parent="one-flow")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the tickets")

    said = run(repo, "drop", "one-flow")
    assert said.code == 1 and "map-columns names one-flow as its parent ticket" in said.err
    child.unlink()
    citing = ticket(tickets, "saved-views", "## Acceptance criteria\n\n- [ ] `one-flow#P1` holds.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "one more")
    said = run(repo, "drop", "one-flow")
    assert said.code == 1 and f"{citing}:{line_of(citing, 'one-flow#P1')}: one-flow#P1" in said.err
    assert (tickets / "one-flow.md").exists()


def test_dropping_a_ticket_with_changes_no_commit_holds_is_refused(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the ticket")
    path.write_text(path.read_text() + "\nA line nothing has committed.\n")
    said = run(repo, "drop", "one-flow")
    assert said.code == 1 and "git history is what keeps a file that leaves" in said.err
    assert path.exists()


def test_retiring_a_ticket_whose_work_has_not_landed_is_refused(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", status="review")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the ticket")
    said = run(repo, "retire", "one-flow")
    assert said.code == 1 and "is not done" in said.err
    assert (tickets / "one-flow.md").exists()


def test_retiring_a_file_with_changes_no_commit_holds_is_refused_before_anything_moves(tickets: Path, repo: Path) -> None:
    path = ticket(tickets, "one-flow", status="done")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the ticket")
    path.write_text(path.read_text() + "\nA line nothing has committed.\n")
    said = run(repo, "retire", "one-flow")
    assert said.code == 1 and "git history is what keeps a file that leaves" in said.err
    assert path.exists()


def test_a_ticket_read_by_path_is_read_in_the_tracker_its_directory_holds(corpus: Path, tickets: Path) -> None:
    """A path names a file, and the file names a tracker: the ancestry is read from beside it."""
    read = json.loads(run(corpus, "data", str(tickets / "board-orients-workflow.md")).out)["tickets"][0]
    assert read["ancestors"] == ["board-orients"] and read["parent"] == "board-orients"


def test_a_section_keeps_the_code_the_ticket_fenced_in_it(tickets: Path, repo: Path) -> None:
    """A fence holds a shape the ticket quotes, which is not one of the ticket's own bullets and is
    still the ticket's own words."""
    ticket(tickets, "one-flow", "## Questions\n\n- [D1] **Ask?** Its detail.\n\n## Comments\n\n"
                                "```markdown\n- [D1] **A shape it quotes** rather than asks.\n```\n")
    read = json.loads(run(repo, "data", "one-flow").out)["tickets"][0]
    assert [q["tag"] for q in read["questions"]] == ["D1"], "the fenced item is quoted, not asked"
    assert "- [D1] **A shape it quotes** rather than asks." in read["sections"][-1]["text"]


def test_a_citation_the_writer_wrapped_cites_what_it_cited_unwrapped(tickets: Path, repo: Path) -> None:
    """The bullet is the unit a citation is read off, so the column an editor wrapped at cannot
    change which properties a criterion names."""
    ticket(tickets, "one-flow", "## Properties\n\n- P1 One.\n- P2 Two.\n- P3 Three.\n")
    for written in ("- [ ] `one-flow#P1`, `#P2` and `#P3` hold.\n",
                    "- [ ] `one-flow#P1`, `#P2` and\n  `#P3` hold.\n"):
        path = ticket(tickets, "map-columns", f"## Acceptance criteria\n\n{written}")
        assert run(repo, "check", str(path)) == Run(0, "", ""), written
        read = json.loads(run(repo, "data", "map-columns").out)["tickets"][0]
        assert read["criteria"][0]["cites"] == ["one-flow#P1", "one-flow#P2", "one-flow#P3"], written


def test_a_question_no_reader_looks_for_is_refused_rather_than_dropped(tickets: Path, repo: Path) -> None:
    """A whole question list indented by two spaces: every reader of a question looks for it at the
    start of a line, so nothing would see these."""
    path = ticket(tickets, "one-flow", "## Questions\n\n  - [D1] **Ask?** Its detail.\n")
    said = run(repo, "check", str(path))
    assert said.code == 1
    assert f"{path}:{line_of(path, 'Ask?')}: this question is indented" in said.out, said.out


def test_two_files_that_claim_one_slug_are_refused_by_name(tickets: Path, repo: Path) -> None:
    """What the flat layout has no room for, and what the conversion of a two-feature tracker walks
    into: two `spec.md` staged in one commit."""
    (tickets / "csv-import").mkdir()
    (tickets / "saved-views").mkdir()
    for feature in ("csv-import", "saved-views"):
        ticket(tickets / feature, "spec")
    git(repo, "add", "-A")
    said = run(repo, "check")
    assert said.code == 1
    assert said.out.count("two files claim the slug spec") == 2, said.out
    assert said.out.count("a spec is dropped") == 2, "and each is refused as the top-level ticket it becomes"


def test_a_commit_in_a_repo_with_no_tracker_is_refused_nothing(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main", ".")
    assert run(tmp_path, "check") == Run(0, "", "")


def test_a_list_field_written_as_one_value_is_refused_once(tickets: Path, repo: Path) -> None:
    """A bare scalar is a string, and walking it would refuse the line once per character."""
    path = ticket(tickets, "one-flow", **{"diff": "4f2a91c..8b3ce07"})
    said = run(repo, "check", str(path))
    assert said.code == 1
    assert said.out.splitlines() == [f"{path}:5: `diff: 4f2a91c..8b3ce07` is one value; `diff` is a list, written `diff: [4f2a91c..8b3ce07]`",
                                     "1 file refused"], said.out


def test_a_write_is_not_refused_over_breakage_it_did_not_make(tickets: Path, repo: Path) -> None:
    """A write moves the lines under it, and the refusals the file already carried move with them."""
    path = ticket(tickets, "one-flow", "## Questions\n\n- [D1] **Ask?** Its detail.\n\n## Comments\n\n- A1 no anchor here.\n")
    assert run(repo, "check", str(path)).code == 1, "the file already says something no reader can read"
    assert run(repo, "set", "one-flow", "diff+=4f2a91c..8b3ce07").code == 0, "which is not this write's doing"
    assert run(repo, "rule", "one-flow", "D1", "keep it").code == 0
    assert "diff: [4f2a91c..8b3ce07]" in path.read_text() and "Ruled " in path.read_text()


def test_a_write_that_would_break_the_file_is_refused_with_what_it_broke(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", "## Questions\n\n- [D1] **Ask?** Its detail.\n")
    said = run(repo, "set", "one-flow", "blocked-by=[nowhere]")
    assert said.code == 1 and "names no ticket" in said.err


def test_the_tracker_is_found_from_wherever_the_command_is_typed(tickets: Path, repo: Path) -> None:
    """An agent types this in the directory it is working in, which is rarely the repo's root."""
    ticket(tickets, "one-flow", status="claimed")
    deeper = repo / "agent" / "show" / "one-flow"
    deeper.mkdir(parents=True)
    assert run(deeper, "get", "one-flow", "status").out == "claimed\n"


def test_the_hook_installs_where_git_looks_for_one_from_any_worktree(repo: Path, tmp_path: Path) -> None:
    """One install covers every worktree of the repo, which is where dispatch stages its work."""
    worktree = tmp_path / "beside"
    git(repo, "worktree", "add", "-q", "--detach", str(worktree))
    (worktree / "agent" / "tickets").mkdir(parents=True)
    said = run(worktree, "hook")
    assert said.out.strip() == str(repo / ".git" / "hooks" / "pre-commit"), said.said
    assert (repo / ".git" / "hooks" / "pre-commit").exists()


def test_every_subcommand_is_in_the_help_the_interface_is_read_from(repo: Path) -> None:
    """`--help` is the reference for the interface, so it is run as a caller runs it."""
    said = subprocess.run([str(Path(tr.__file__).parents[2] / "bin" / "tracker"), "--help"],
                          capture_output=True, text=True, cwd=repo)
    assert said.returncode == 0
    for subcommand in ("check", "get", "data", "context", "frontier", "new", "set", "rule", "retire", "hook"):
        assert f"• {subcommand} " in said.stdout, subcommand
    assert "usage: tracker" in said.stdout, "the usage line names the command, not the script behind it"


def test_filing_writes_every_field_it_was_given(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow")
    run(repo, "new", "map-columns", "--priority", "3", "--size", "XL", "--status", "open",
        "--needs-user", "--blocked-by", "one-flow")
    read = json.loads(run(repo, "data", "map-columns").out)["tickets"][0]
    assert (read["status"], read["priority"], read["size"]) == ("open", 3, "XL")
    assert read["needs-user"] is True and read["blocked-by"] == ["one-flow"]


def test_a_list_field_is_printed_one_entry_per_line(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", **{"diff": "[4f2a91c..8b3ce07, aaaaaaa..bbbbbbb]"})
    assert run(repo, "get", "one-flow", "diff").out == "4f2a91c..8b3ce07\naaaaaaa..bbbbbbb\n"


def test_a_needs_user_field_is_printed_as_the_file_writes_it(tickets: Path, repo: Path) -> None:
    """A shell compares it against what it reads in the file, never against Python's spelling."""
    ticket(tickets, "one-flow", **{"needs-user": "true"})
    assert run(repo, "get", "one-flow", "needs-user").out == "true\n"


def test_the_check_says_how_many_files_it_refused(tickets: Path, repo: Path) -> None:
    ticket(tickets, "one-flow", priority=7)
    ticket(tickets, "map-columns", priority=7)
    said = run(repo, "check", str(tickets / "one-flow.md"), str(tickets / "map-columns.md"))
    assert said.out.splitlines()[-1] == "2 files refused"


def test_a_staged_deletion_is_not_read_as_a_file(tickets: Path, repo: Path) -> None:
    """Retiring stages removals, and the commit that carries them runs the hook like any other."""
    ticket(tickets, "one-flow")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the ticket")
    git(repo, "rm", "-q", "agent/tickets/one-flow.md")
    assert run(repo, "check") == Run(0, "", "")


def test_a_bullet_a_writer_wrapped_without_indenting_it_is_read_whole(tickets: Path, repo: Path) -> None:
    """CommonMark's lazy continuation: the line under a bullet continues it, indented or not."""
    path = ticket(tickets, "one-flow", "## Comments\n\n- [D1] Assumptions\n  - A1 `mx/x.py:1`: the call and\nwhy it was made.\n")
    read = json.loads(run(repo, "data", str(path)).out)["tickets"][0]
    assert [note["text"] for note in read["assumptions"]] == ["the call and why it was made."]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
