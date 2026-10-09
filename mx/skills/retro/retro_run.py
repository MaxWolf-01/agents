#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py"]
# ///
"""Run a workflow retro on the agents repo: collect, then one model run per stage, then commit the
living report and its page into `retro/` of the repo's agent repo.

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
A run that ends without its commit, there or at a stage that wrote nothing, exits 1, and its last
line in the log says why.

Examples:

    retro_run.py ~/repos/github/MaxWolf-01/agents
    retro_run.py ~/repos/github/MaxWolf-01/agents --focus "the tests are overbuilt"
    retro_run.py ~/repos/github/MaxWolf-01/agents --since 2026-10-03 --seed ~/Downloads/show/retro-2026-10/REPORT.md
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import tyro

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import retro_collect  # noqa: E402
from retro_collect import parse_time, stamp  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "high"
STAGE_TIMEOUT = 4 * 3600  # seconds; a stage reading a heavy week runs about an hour
BATCH_CHARS = 300_000  # digest text one read-fresh subagent reads
REPORT = ("report.md", "report.html")  # what synthesis writes, and all the commit holds, in retro/
RUN_LOG = HERE.parent / "run-log" / "run-log"
GIT_READS = ("log", "show", "diff", "blame", "rev-parse", "rev-list", "merge-base", "ls-files", "ls-tree",
             "cat-file", "shortlog", "status")
IN_PROGRESS = ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD")


@dataclass(frozen=True)
class Stage:
    name: str
    writes: tuple[str, ...]
    """Globs in the run directory each of which matches a file once the stage is done."""
    fresh: bool = False
    """Confined to the run directory, which holds no earlier report while it runs."""


WORKFLOW = (
    Stage("read-fresh", ("notes/*.md",), fresh=True),
    Stage("follow-up", ("follow-up.md",)),
    Stage("go-deep", ("deep/*.md",)),
    Stage("synthesize", REPORT),
)


# ── what runs ────────────────────────────────────────────────────────────────


def run_retro(repo: Path, data: Path, projects: list[Path], since: datetime | None = None, focus: str = "",
              seed: list[Path] = (), until: datetime | None = None) -> Path:
    """A whole workflow retro on `repo`; returns its run directory."""
    repo = repo.expanduser().resolve()
    agent = repo / "agent"
    if not (repo / retro_collect.PLUGIN).exists():
        sys.exit(f"{repo} holds no mx plugin: the workflow retro is the agents repo's, and no other kind is built yet")
    if not (agent / ".git").exists():
        sys.exit(f"{agent} is no agent repo; the report is committed there")
    home = data.expanduser() / repo.name
    runs = run_commits(agent)
    if since is None and not runs:
        sys.exit(f"no earlier run of this retro in {agent}/retro/report.md's history: pass --since")
    since = since or runs[0][1]
    until = until or datetime.now(UTC)
    run = home / "runs" / until.astimezone(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    log = Log(home / "runs.log", run.name)
    repos = read_paths(agent / "retro" / "repos")
    exclude = retro_collect.read_patterns(agent / "retro" / "excluded-sessions")
    base = blob(agent, "retro/report.md")
    log(f"started: {repo}, {stamp(since)} to {stamp(until)}" + (f", focus: {focus}" if focus else ""))
    retro_collect.collect_sessions(since, until, run, home / "digest-cache", projects, repos, exclude)
    write_batches(run)
    values = dict(run=str(run), repo=str(repo), skills=str(HERE.parent), since=stamp(since), until=stamp(until),
                  lenses=(HERE / "LENSES.md").read_text(), repos="\n".join(f"- {r}" for r in repos),
                  focus=f"max named a focus for this run: “{focus}”." if focus else "max named no focus for this run.")
    for stage in WORKFLOW:
        if not stage.fresh and not (run / "previous").exists():
            write_previous(run, agent, runs, seed)
        if not run_stage(stage, run, values, readable(repos, agent)):
            log(f"stopped: {stage.name} wrote no {' or '.join(stage.writes)}; its output is {run / stage.name}.log")
            sys.exit(1)
        log(f"{stage.name} done")
    committed, line = commit_report(agent, run, base, since, until)
    log(line)
    if not committed:
        sys.exit(1)
    return run


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


def read_paths(path: Path) -> list[Path]:
    """The paths a list file holds, one per line, `~` expanded, `#` starting a comment."""
    if not path.exists():
        sys.exit(f"{path} is missing: it lists the repos whose git a workflow retro collects")
    return [Path(line.strip()).expanduser() for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


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


def run_stage(stage: Stage, run: Path, values: dict[str, str], dirs: list[Path]) -> bool:
    """One stage's model run, from its prompt filled in with `values`; whether it wrote what it should."""
    prompt = render((HERE / "stages" / f"{stage.name}.md").read_text(), values)
    (run / "prompts").mkdir(exist_ok=True)
    (run / "prompts" / f"{stage.name}.md").write_text(prompt)
    with (run / f"{stage.name}.log").open("w") as out:
        subprocess.run(launch(stage, run, dirs), cwd=run, input=prompt, stdout=out, stderr=subprocess.STDOUT, text=True,
                       env={**os.environ, "CLAUDE_CODE_SUBAGENT_MODEL": MODEL})
    return all(any(p.stat().st_size for p in run.glob(g)) for g in stage.writes)


def launch(stage: Stage, run: Path, dirs: list[Path]) -> list[str]:
    """The command line of a stage's model run. It starts from none of the host's settings, and
    `--restricted` confines its file tools to the run directory and, after read-fresh, the
    readable directories; the one write rule covers the run directory alone, and every other
    write is refused, since nobody is there to approve it."""
    tools, allowed, add = "Read,Grep,Glob,Write,Edit,Agent", [f"Edit(/{run}/**)"], []
    if not stage.fresh:
        tools += ",Bash"
        add = ["--add-dir", *map(str, dirs)]
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
    if (now := show(agent, "HEAD:retro/report.md")) is not None:
        (previous / "current.md").write_text(now)
    for sha, until in runs[:3]:
        (previous / f"{until.date().isoformat()}.md").write_text(show(agent, f"{sha}:retro/report.md") or "")
    if seed:
        (previous / "seed").mkdir()
        for path in seed:
            shutil.copy(path.expanduser(), previous / "seed" / path.name)


# ── the commit ───────────────────────────────────────────────────────────────


def commit_report(agent: Path, run: Path, base: str | None, since: datetime, until: datetime) -> tuple[bool, str]:
    """Copy the run's report and page into `retro/` and commit those two files alone. Whether it
    committed, and the line the run log gets, saying what was committed or why nothing was."""
    paths = [f"retro/{name}" for name in REPORT]
    gitdir = Path(git(agent, "rev-parse", "--absolute-git-dir").strip())
    if busy := [name for name in IN_PROGRESS if (gitdir / name).exists()]:
        return False, f"not committed: {agent} is mid-{operation(busy[0])}; the report stays in {run}"
    if blob(agent, "retro/report.md") != base:
        return False, f"not committed: {agent}/retro/report.md was committed to while the run ran; the report stays in {run}"
    if changed := git(agent, "status", "--porcelain", "--", *paths).strip():
        return False, f"not committed: {', '.join(line[3:] for line in changed.splitlines())} has changes of its own in {agent}; the report stays in {run}"
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
            if show(agent, f"HEAD:{path}") is None:
                (agent / path).unlink()
            else:
                git(agent, "checkout", "--", path)
        return False, f"not committed: git commit failed ({(done.stderr or done.stdout).strip()}); the report stays in {run}"
    return True, f"committed {git(agent, 'rev-parse', '--short', 'HEAD').strip()} in {agent}"


def operation(name: str) -> str:
    return {"MERGE_HEAD": "merge", "CHERRY_PICK_HEAD": "cherry-pick", "REVERT_HEAD": "revert"}.get(name, "rebase")


def blob(agent: Path, path: str) -> str | None:
    """The object id of `path` at HEAD, None when HEAD has no such file."""
    done = subprocess.run(["git", "-C", str(agent), "rev-parse", "--verify", "--quiet", f"HEAD:{path}"],
                          capture_output=True, text=True)
    return done.stdout.strip() or None


def show(agent: Path, spec: str) -> str | None:
    done = subprocess.run(["git", "-C", str(agent), "show", spec], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else None


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


# ── command line ─────────────────────────────────────────────────────────────


@dataclass
class Args:
    repo: tyro.conf.Positional[Path]
    """The repo the retro is for: the agents repo, which holds the mx plugin and an agent repo at `agent/`."""
    focus: str = ""
    """A pattern max names (\"the tests are overbuilt\"), which becomes one of the run's deep-dives."""
    since: str = ""
    """The period's start, an ISO date or time, UTC where it names no offset; by default the end of the last run committed to `retro/report.md`."""
    seed: list[Path] = field(default_factory=list)
    """Files the run's later stages read as earlier reports, beside those in git history."""
    data: Path = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "retro"
    """The retro's data directory, outside every git repo."""
    projects: list[Path] = field(default_factory=lambda: [Path.home() / ".claude/projects",
                                                         Path.home() / ".claude-helferline/projects"])
    """Each Claude Code profile's directory of transcripts."""


if __name__ == "__main__":
    args = tyro.cli(Args, description=__doc__)
    run_retro(args.repo, args.data, args.projects, parse_time(args.since) if args.since else None, args.focus, args.seed)
