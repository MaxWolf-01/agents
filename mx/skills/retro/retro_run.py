#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py"]
# ///
"""Run a workflow retro on the agents repo: collect, then one model run per stage, then commit the
living report and its page into `retro/` of the repo's agent repo, in its main checkout.

The run reads two lists from that `retro/`: `repos`, the repos whose git it collects, one path per
line, and `excluded-sessions`, the directories whose sessions it never reads. Its period starts
where the last run committed to `retro/report.md` ended, or at --since. Everything a run writes
but the report lives in its run directory, `<data>/<repo>/runs/<end of period>/`, outside every git
repo: the digests, each stage's prompt, notes and output, and the new report. Each event of a run
is a line of `<data>/<repo>/runs.log`.

The stages run one after another, each a `claude -p` on Opus 5.5 that may write only in the run
directory. The first, read-fresh, may read nothing outside it either, and runs before the earlier
reports are copied into it, under `previous/`.

The commit holds `retro/report.md` and `retro/report.html` alone, and leaves whatever else is
staged in the agent repo staged. It is not made, and the report stays in the run directory, when
the agent repo is mid-merge, mid-rebase, mid-cherry-pick or mid-revert, when either file has
changes of its own there, or when the report was committed to while the run ran. Nothing is pushed.
A run that ends without its commit, there or at a stage that failed or left out a file it owes,
exits 1, and its last line in the log says why.

Examples:

    retro_run.py ~/repos/github/MaxWolf-01/agents
    retro_run.py ~/repos/github/MaxWolf-01/agents --focus "the tests are overbuilt"
    retro_run.py ~/repos/github/MaxWolf-01/agents --since 2026-10-03 --seed ~/retro-2026-10/REPORT.md
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import tyro

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import retro_collect  # noqa: E402
from retro_collect import git, parse_time, stamp  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "high"
STAGE_TIMEOUT = 4 * 3600  # seconds; a stage reading a heavy week runs about an hour
BATCH_CHARS = 300_000  # digest text one read-fresh subagent reads
REPORT = ("report.md", "report.html")  # what synthesis writes, and all the commit holds, in retro/
RUN_LOG = HERE.parent / "run-log" / "run-log"
# `status` is left out: it refreshes the index, a write into the repo.
GIT_READS = ("log", "show", "diff", "blame", "rev-parse", "rev-list", "merge-base", "ls-files", "ls-tree",
             "cat-file", "shortlog")
IN_PROGRESS = {"MERGE_HEAD": "merge", "rebase-merge": "rebase", "rebase-apply": "rebase",
               "CHERRY_PICK_HEAD": "cherry-pick", "REVERT_HEAD": "revert"}  # marker in the git dir: operation


@dataclass(frozen=True)
class Stage:
    name: str
    owes: tuple[str, ...]
    """Files in the run directory the stage writes; `{batch}` stands for each batch's name."""
    fresh: bool = False
    """Confined to the run directory, which holds no earlier report while it runs."""


WORKFLOW = (
    Stage("read-fresh", ("notes/{batch}.md", "notes/git.md"), fresh=True),
    Stage("follow-up", ("follow-up.md",)),
    Stage("go-deep", ("deep/architecture.md",)),
    Stage("synthesize", REPORT),
)


# ── what runs ────────────────────────────────────────────────────────────────


def run_retro(repo: Path, data: Path, projects: Sequence[Path], since: datetime | None = None, focus: str = "",
              seed: Sequence[Path] = (), until: datetime | None = None) -> Path:
    """A whole workflow retro on `repo`; returns its run directory."""
    repo = repo.expanduser().resolve()
    if not (repo / retro_collect.PLUGIN).exists():
        sys.exit(f"{repo} holds no mx plugin: the workflow retro is the agents repo's, and no other kind is built yet")
    agent = main_checkout(repo / "agent")
    home = data.expanduser() / repo.name
    runs = run_commits(agent)
    if since is None and not runs:
        sys.exit(f"no earlier run of this retro in {agent}/retro/report.md's history: pass --since")
    since = since or runs[0][1]
    until = until or datetime.now(UTC)
    run = home / "runs" / dirname(until)
    log = Log(home / "runs.log", run.name)
    repos = [Path(p).expanduser().resolve() for p in retro_collect.read_list(agent / "retro" / "repos")]
    exclude = retro_collect.read_patterns(agent / "retro" / "excluded-sessions")
    seed = [Path(p).expanduser() for p in seed]
    if len({p.name for p in seed}) < len(seed):
        sys.exit("two seed files share a name; each is copied into previous/seed/ under its own")
    base = blob(agent, "retro/report.md")
    log(f"started: {repo}, {stamp(since)} to {stamp(until)}" + (f", focus: {focus}" if focus else ""))
    retro_collect.collect_sessions(since, until, run, home / "digest-cache", list(projects), repos, exclude)
    write_batches(run)
    values = dict(run=str(run), repo=str(repo), skills=str(HERE.parent), since=stamp(since), until=stamp(until),
                  lenses=(HERE / "LENSES.md").read_text(), repos="\n".join(f"- {r}" for r in repos),
                  sample=f"about {retro_collect.SAMPLE_SIZE} older sessions that started "
                         f"{retro_collect.SAMPLE_WINDOW[0].days // 7} to {retro_collect.SAMPLE_WINDOW[1].days // 7} "
                         f"weeks before the period's end",
                  focus=f'max named a focus for this run: "{focus}".' if focus else "max named no focus for this run.")
    for stage in WORKFLOW:
        if not stage.fresh and not (run / "previous").exists():
            write_previous(run, agent, runs, seed)
        if failed := run_stage(stage, run, values, readable(repos, agent)):
            log(f"stopped: {stage.name} {failed}; its output is {run / stage.name}.log")
            sys.exit(1)
        log(f"{stage.name} done")
    committed, line = commit_report(agent, run, base, since, until)
    log(line)
    if not committed:
        sys.exit(1)
    return run


def main_checkout(agent: Path) -> Path:
    """The agent repo's main checkout, where the report is committed, also when `agent` is a
    worktree of it on another branch."""
    done = subprocess.run(["git", "-C", str(agent), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, text=True)
    common = Path(done.stdout.strip())
    if done.returncode != 0 or common.name != ".git":
        sys.exit(f"{agent} is no agent repo with a main checkout; the report is committed there")
    return common.parent


def dirname(until: datetime) -> str:
    return until.astimezone(UTC).strftime("%Y-%m-%dT%H%M%SZ")


class Log:
    """One line per event of a run, appended to the retro's log and printed."""

    def __init__(self, path: Path, run: str) -> None:
        self.path, self.run = path, run
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, message: str) -> None:
        line = f"{stamp(datetime.now(UTC))} {self.run} {message}"
        print(line, file=sys.stderr)
        with self.path.open("a") as f:
            f.write(line + "\n")


def readable(repos: list[Path], agent: Path) -> list[Path]:
    """What a stage after read-fresh may read and run git reads in: the repos, their agent repos,
    and the skills, whose files the stages' prompts name."""
    dirs = [*repos, agent, *(r / "agent" for r in repos if (r / "agent" / ".git").exists()), HERE.parent]
    return list(dict.fromkeys(d.resolve() for d in dirs))


# ── the stages ───────────────────────────────────────────────────────────────


def write_batches(run: Path) -> None:
    """`batches.json`: the period's digests in batches of about BATCH_CHARS, a project's sessions
    together and in order of their start; the older sample as one batch of its own."""
    rows = [json.loads(line) for line in (run / "sessions.jsonl").read_text().splitlines()]
    batches: list[dict] = []
    for row in sorted((r for r in rows if r["set"] == "sessions"), key=lambda r: (r["project"], r["start"])):
        path = f"sessions/{row['id']}.md"
        size = (run / path).stat().st_size
        if not batches or batches[-1]["chars"] + size > BATCH_CHARS:
            batches.append(dict(name=f"batch-{len(batches) + 1:02d}", digests=[], chars=0))
        batches[-1]["digests"].append(path)
        batches[-1]["chars"] += size
    sample = [f"sample/{r['id']}.md" for r in rows if r["set"] == "sample"]
    if sample:
        batches.append(dict(name="sample", digests=sample, chars=sum((run / p).stat().st_size for p in sample)))
    (run / "batches.json").write_text(json.dumps(batches, indent=1) + "\n")


def run_stage(stage: Stage, run: Path, values: dict[str, str], dirs: list[Path]) -> str:
    """One stage's model run, from its prompt filled in with `values`; what went wrong, or nothing."""
    prompt = render((HERE / "stages" / f"{stage.name}.md").read_text(), values)
    (run / "prompts").mkdir(exist_ok=True)
    (run / "prompts" / f"{stage.name}.md").write_text(prompt)
    with (run / f"{stage.name}.log").open("w") as out:
        done = subprocess.run(launch(stage, run, dirs), cwd=run, input=prompt, stdout=out, stderr=subprocess.STDOUT,
                              text=True, env={**os.environ, "CLAUDE_CODE_SUBAGENT_MODEL": MODEL, "GIT_OPTIONAL_LOCKS": "0"})
    if done.returncode != 0:
        return f"exited {done.returncode}"
    batches = [b["name"] for b in json.loads((run / "batches.json").read_text())]
    owed = [p.format(batch=b) for p in stage.owes for b in (batches if "{batch}" in p else [""])]
    if missing := [p for p in owed if not (run / p).is_file() or not (run / p).stat().st_size]:
        return f"left out {', '.join(missing)}"
    return ""


def launch(stage: Stage, run: Path, dirs: list[Path]) -> list[str]:
    """The command line of a stage's model run. It starts from none of the host's settings, and
    `--restricted` confines its file tools to the run directory and, after read-fresh, the
    readable directories; the one write rule covers the run directory alone, git's `--output`,
    which writes a file, is denied, and every other write is refused, since nobody is there to
    approve it."""
    tools, allowed, add = "Read,Grep,Glob,Write,Edit,Agent", [f"Edit(/{run}/**)"], []
    if not stage.fresh:
        tools += ",Bash"
        add = ["--add-dir", *map(str, dirs), "--disallowedTools", *(f"Bash(git -C {d} * --output*)" for d in dirs)]
        allowed += [f"Bash(git -C {d} {sub}{rest})" for d in dirs for sub in GIT_READS for rest in ("", " *")]
    return ["bash", str(RUN_LOG), "run", "--site", f"retro-{stage.name}", "--timeout", str(STAGE_TIMEOUT), "--",
            "claude", "-p", "--model", MODEL, "--effort", EFFORT,
            "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
            "--settings", '{"autoMemoryEnabled": false}', "--restricted", *add, "--allowedTools", *allowed,
            "--tools", tools, "--permission-mode", "manual", "--permission-prompts", "none"]


def render(template: str, values: dict[str, str]) -> str:
    """A stage's prompt with each `{{name}}` replaced by its value; an unknown name is an error."""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)


# ── the earlier reports ──────────────────────────────────────────────────────


def run_commits(agent: Path) -> list[tuple[str, datetime]]:
    """The commits a run made of the report, newest first, each with the end of its period."""
    out = git(agent, "log", "--format=%H %(trailers:key=Retro-until,valueonly,separator=)", "--", "retro/report.md")
    return [(sha, parse_time(until)) for sha, until in (line.split(" ", 1) for line in out.splitlines()) if until]


def write_previous(run: Path, agent: Path, runs: list[tuple[str, datetime]], seed: list[Path]) -> None:
    """`previous/`: the report as it stands now, verdicts since the last run included, as
    `current.md`; the last three runs' reports, each named for the end of its period; and the
    seed, the reports a first run takes as its previous ones, under `seed/`."""
    previous = run / "previous"
    previous.mkdir()
    if blob(agent, "retro/report.md"):
        (previous / "current.md").write_text(git(agent, "show", "HEAD:retro/report.md"))
    for sha, until in runs[:3]:
        (previous / f"{dirname(until)}.md").write_text(git(agent, "show", f"{sha}:retro/report.md"))
    if seed:
        (previous / "seed").mkdir()
        for path in seed:
            shutil.copy(path, previous / "seed" / path.name)


# ── the commit ───────────────────────────────────────────────────────────────


def commit_report(agent: Path, run: Path, base: str | None, since: datetime, until: datetime) -> tuple[bool, str]:
    """Copy the run's report and page into `retro/` and commit those two files alone. Whether it
    committed, and the line the run log gets, saying what was committed or why nothing was."""
    paths = [f"retro/{name}" for name in REPORT]
    gitdir = Path(git(agent, "rev-parse", "--absolute-git-dir").strip())
    if busy := [op for marker, op in IN_PROGRESS.items() if (gitdir / marker).exists()]:
        return False, f"not committed: {agent} is mid-{busy[0]}; the report stays in {run}"
    if blob(agent, "retro/report.md") != base:
        return False, f"not committed: {agent}/retro/report.md was committed to while the run ran; the report stays in {run}"
    if changed := git(agent, "status", "--porcelain", "--", *paths).strip():
        changes = ", ".join(line[3:] for line in changed.splitlines())
        return False, f"not committed: {changes} has changes of its own in {agent}; the report stays in {run}"
    (agent / "retro").mkdir(exist_ok=True)
    for name in REPORT:
        shutil.copy(run / name, agent / "retro" / name)
    message = (f"retro: the workflow retro of {since.date()} to {until.date()}\n\n"
               f"Retro-since: {stamp(since)}\nRetro-until: {stamp(until)}\n")
    git(agent, "add", "--", *paths)
    done = subprocess.run(["git", "-C", str(agent), "commit", "--quiet", "--only", "-m", message, "--", *paths],
                          capture_output=True, text=True)
    if done.returncode != 0:
        git(agent, "reset", "--quiet", "--", *paths)
        for path in paths:
            if blob(agent, path) is None:
                (agent / path).unlink()
            else:
                git(agent, "checkout", "--", path)
        return False, f"not committed: git commit failed ({(done.stderr or done.stdout).strip()}); the report stays in {run}"
    return True, f"committed {git(agent, 'rev-parse', '--short', 'HEAD').strip()} in {agent}"


def blob(agent: Path, path: str) -> str | None:
    """The object id of `path` at HEAD, None when HEAD has no such file."""
    done = subprocess.run(["git", "-C", str(agent), "rev-parse", "--verify", "--quiet", f"HEAD:{path}"],
                          capture_output=True, text=True)
    return done.stdout.strip() or None


# ── command line ─────────────────────────────────────────────────────────────


@dataclass
class Args:
    repo: tyro.conf.Positional[Path]
    """The repo the retro is for: the agents repo, which holds the mx plugin and an agent repo at `agent/`."""
    focus: str = ""
    """A pattern max names ("the tests are overbuilt"), which becomes one of the run's deep-dives."""
    since: str = ""
    """The period's start, an ISO date or time, UTC where it names no offset; by default the end of the last run committed to `retro/report.md`."""
    seed: list[Path] = field(default_factory=list)
    """Files the run's later stages read as earlier reports, beside those in git history; no two may share a name."""
    data: Path = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "retro"
    """The retro's data directory, outside every git repo."""
    projects: list[Path] = field(default_factory=lambda: list(retro_collect.PROFILES))
    """Each Claude Code profile's directory of transcripts."""


if __name__ == "__main__":
    args = tyro.cli(Args, description=__doc__)
    run_retro(args.repo, args.data, args.projects, parse_time(args.since) if args.since else None, args.focus, args.seed)
