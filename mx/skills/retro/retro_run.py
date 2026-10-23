#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""Run a retro on a project: collect, then one model run per stage, then commit the living report
and its page into the project's agent repo, in its main checkout.

A retro is one per tracker. Its report is `retro/report.md` in the project's agent repo, and a
project whose `agent/` is no git repo of its own is refused.

The project's kind decides what a run reads and which stages it runs. The agents repo, which holds
the mx plugin, gets the workflow retro: it reads every session of every Claude Code profile under
the home (`~/.claude*/projects`), its permission data, and the git of the agents repo and of the
repos `retro/repos` lists in its agent repo, one path per line; its lens pass reads the agents
repo's code; it runs read-fresh, follow-up, go-deep, the lens pass and synthesize. Any other project
gets a repo retro: it reads the commits, tickets and code of the project's repo and of every repo
its `agent/repos.toml` lists but one with `retro = false` and one with an agent repo of its own,
which its own tracker's retro reads, and the sessions of every profile that worked in those repos
(`retro_collect.Worked`); it runs read-fresh, follow-up, the lens pass and synthesize. A run's
stages log in as the profile `CLAUDE_CONFIG_DIR` names, as every `claude` does.

A run's period starts where the last run committed to the report ended, or at --since; a
repo retro's first run, given no --since, takes the eight weeks before it (--first-weeks). Everything a run writes
but the report lives in its run directory, `<data>/<repo>/runs/<end of period>/`, outside every git
repo: what collect gathered, each stage's prompt, notes and output, and the new report. Each event
of a run is a line of `<data>/<repo>/runs.log`.

The stages run one after another, each a `claude -p` that may write only in the run directory.
The first, read-fresh, may read nothing outside it either, and runs before the earlier reports are
copied into it, under `previous/`. A repo retro's stages read sessions as the digests in the run
directory alone: they may not read the session pages in its agent repos, and run no git command
there.

The commit holds the report and its page, `report.html` beside it, alone, and leaves whatever else
is staged in the agent repo staged. It is not made, and the report stays in the run directory, when
the agent repo is mid-merge, mid-rebase, mid-cherry-pick or mid-revert, when either file has changes
of its own there, or when the report was committed to while the run ran. Nothing is pushed.
A run that ends without its commit, there, in collect or at a stage that failed or left out a file
it owes, exits 1, and its last line in the log says why. A run stopped by TERM, INT or HUP ends the
stage it is in, and whatever that stage started, before it exits; one stopped during the commit lets the
commit finish. On Linux, a run killed outright takes its stage down with it.

A new run given --if-active first looks for something new since the period's start: for the
workflow retro, a message of max's in an interactive session or a commit of his in the agents
repo or a repo `retro/repos` lists; for a repo retro, a commit on any branch of one of its repos.
Finding none, it logs that it skipped and exits 3, having run no stage.

A run that ended without its commit, once collect had finished, is resumed with --resume and its
directory: it keeps the run's repo, period, focus and seed, picks up at the first stage that left
out a file it owes, and commits as any run does.

Examples:

    retro_run.py ~/repos/github/MaxWolf-01/agents
    retro_run.py ~/repos/github/MaxWolf-01/agents --if-active
    retro_run.py ~/repos/github/MaxWolf-01/agents --focus "the tests are overbuilt"
    retro_run.py ~/repos/github/MaxWolf-01/agents --since 2026-10-03 --seed ~/retro-2026-10/REPORT.md
    retro_run.py ~/.dotfiles --if-active
    retro_run.py ~/.dotfiles --focus "the backup scripts"
    CLAUDE_CONFIG_DIR=~/.claude-helferline retro_run.py ~/work/helferline --if-active
    retro_run.py ~/repos/github/MaxWolf-01/agents --resume ~/.local/share/retro/agents/runs/<end of period>
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import tyro

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import retro_collect  # noqa: E402
import qualified  # noqa: E402  what a qualified tag on the report's page names, which the page links
from retro_collect import git, parse_time, stamp  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "high"
SKIPPED = 3  # the exit status of an --if-active run that found nothing new
STAGE_TIMEOUT = 4 * 3600  # seconds; a stage reading a heavy week runs about an hour
BATCH_CHARS = 300_000  # digest text one read-fresh subagent reads
FIRST_WEEKS = 8  # how far back a repo retro's first run reads, given no --since; --first-weeks overrides it
REPORT = ("report.md", "report.html")  # what synthesis writes, and all the commit holds, in the report's directory
REPORT_PATH = f"{qualified.RETRO}/report.md"  # in the agent repo
RUN_LOG = HERE.parent / "run-log" / "run-log"
AUTO_MODE_CRITIQUE = HERE / "auto_mode_critique.py"
# `status` is left out: it refreshes the index, a write into the repo. `diff` is left out: given a
# path outside the work tree it diffs files from disk, `--no-index` or not, so it reads any file;
# `log -p` and `show` read the same history from the repo's objects alone.
GIT_READS = ("log", "show", "blame", "rev-parse", "rev-list", "merge-base", "ls-files", "ls-tree",
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
    runs: tuple[Path, ...] = ()
    """Scripts the stage may run, each given the run directory and nothing else."""
    model: str = MODEL
    """The model the stage and its subagents run on; a run's --model overrides it for every stage."""
    effort: str = EFFORT


@dataclass(frozen=True)
class Kind:
    name: str
    """As the report's title, its commit and the stages' prompts name it."""
    stages: tuple[Stage, ...]


READ_FRESH = Stage("read-fresh", ("notes/{batch}.md", "notes/git.md"), fresh=True)
LENS_PASS = Stage("lens-pass", tuple(f"lens-pass/{lens}.md" for lens in
                                     ("architecture", "bloat", "tests", "footguns", "escaped-defects")))
FOLLOW_UP = Stage("follow-up", ("follow-up.md",))
SYNTHESIZE = Stage("synthesize", REPORT)
WORKFLOW = Kind("workflow retro", (
    READ_FRESH,
    FOLLOW_UP,
    Stage("go-deep", ("deep/leading-words.md", "deep/permissions.md", "deep/critique.md"), runs=(AUTO_MODE_CRITIQUE,)),
    LENS_PASS,
    SYNTHESIZE,
))
REPO = Kind("repo retro", (READ_FRESH, FOLLOW_UP, LENS_PASS, SYNTHESIZE))


def kind_of(repo: Path) -> Kind:
    return WORKFLOW if (repo / retro_collect.PLUGIN).exists() else REPO


# ── what runs ────────────────────────────────────────────────────────────────


def run_retro(repo: Path, data: Path, projects: Sequence[Path], since: datetime | None = None, focus: str = "",
              seed: Sequence[Path] = (), until: datetime | None = None, resume: Path | None = None,
              if_active: bool = False, model: str = "", effort: str = "", first_weeks: int = FIRST_WEEKS) -> Path:
    """A whole retro on `repo`, or the rest of the one `resume` names; returns its run directory.
    The handlers of STOP are the caller's again afterwards, for a caller that goes on in the same
    process: a signal left ignored is inherited by every process it starts later, which no TERM then
    stops. `model` and `effort`, where given, replace every stage's own."""
    found = {s: signal.getsignal(s) for s in STOP}
    try:
        return retro(repo, data, projects, since, focus, seed, until, resume, if_active, model, effort, first_weeks)
    finally:
        for s, handler in found.items():
            signal.signal(s, handler)


def retro(repo: Path, data: Path, projects: Sequence[Path], since: datetime | None, focus: str,
          seed: Sequence[Path], until: datetime | None, resume: Path | None, if_active: bool,
          model: str = "", effort: str = "", first_weeks: int = FIRST_WEEKS) -> Path:
    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        sys.exit(f"{repo} does not exist")
    kind = kind_of(repo)
    agent = main_checkout(repo / "agent")
    runs = run_commits(agent)
    seed = [Path(p).expanduser().resolve() for p in seed]
    if len({p.name for p in seed}) < len(seed):
        sys.exit("two seed files share a name; each is copied into previous/seed/ under its own")
    if resume:
        run = resume.expanduser().resolve()
        since, until, focus, seed, base = resumed(run, repo, agent, since, focus, seed)
        home = run.parent.parent
    else:
        until = until or datetime.now(UTC)
        if since is None and not runs and kind is WORKFLOW:
            sys.exit(f"no earlier run of this retro in {agent}/{REPORT_PATH}'s history: pass --since")
        since = since or (runs[0][1] if runs else until - timedelta(weeks=first_weeks))
        home = data.expanduser() / repo.name.lstrip(".")
        run = home / "runs" / dirname(until)
        base = blob(agent, REPORT_PATH)
    retro_collect.refuse_inside_git(home)
    log = Log(home / "runs.log", run.name)
    if kind is WORKFLOW:
        listed, left_out = [Path(p).expanduser().resolve() for p in read_list(agent / "retro" / "repos")], []
    else:
        listed, left_out = retro_collect.planned(agent)
    repos = list(dict.fromkeys([repo, *listed]))
    code = [repo] if kind is WORKFLOW else repos  # the repos whose code the lens pass reads
    where = "the check for something new"
    try:
        retro_collect.refuse_unless_git(repos)
        active = ""
        if if_active and not resume:
            if kind is WORKFLOW and not (active := retro_collect.activity(since, list(projects), home / "digest-cache", repos)):
                log(f"skipped: no session or commit of max's since {stamp(since)}")
                sys.exit(SKIPPED)
            if kind is REPO and not (active := retro_collect.latest_commit(repos, since)):
                log(f"skipped: no commit in {', '.join(map(str, repos))} since {stamp(since)}")
                sys.exit(SKIPPED)
        log(f"{'resumed' if resume else 'started'}: {kind.name} of {repo}, {stamp(since)} to {stamp(until)}"
            + (f", focus: {focus}" if focus else "") + (f"; new since: {active}" if active else ""))
        for s in STOP:
            signal.signal(s, on_stop)
        where = "collect"
        if not (run / "run.json").is_file():
            collect(kind, since, until, run, home, list(projects), repos, code, agent, left_out)
            # What a resumed run keeps; written last, so its presence says collect finished.
            (run / "run.json").write_text(json.dumps(dict(repo=str(repo), report=str(agent / REPORT_PATH),
                                                          since=stamp(since), until=stamp(until),
                                                          focus=focus, seed=[str(p) for p in seed], base=base)) + "\n")
        values = dict(run=str(run), repo=str(repo), skills=str(HERE.parent), since=stamp(since), until=stamp(until),
                      critique=f"{AUTO_MODE_CRITIQUE} {run}",
                      kind=kind.name, agent=str(agent), repos="\n".join(f"- {r}" for r in repos),
                      code="\n".join(f"- {r}" for r in code),
                      sessions="every interactive session of max's, from every Claude Code profile" if kind is WORKFLOW
                               else "max's interactive sessions that worked in its repos, listed below",
                      sample=f"about {retro_collect.SAMPLE_SIZE} older sessions that started "
                             f"{retro_collect.SAMPLE_WINDOW[0].days // 7} to {retro_collect.SAMPLE_WINDOW[1].days // 7} "
                             f"weeks before the period's end",
                      focus=f'max named a focus for this run: "{focus}".' if focus else "max named no focus for this run.")
        within = reach(kind, repos, agent)
        for stage in kind.stages:
            stage = replace(stage, model=model or stage.model, effort=effort or stage.effort)
            where = stage.name
            if resume and not missing(stage, run):
                continue
            if not stage.fresh and not (run / "previous").exists():
                write_previous(run, agent, runs, seed)
            if failed := run_stage(stage, run, values, within):
                log(f"failed: {stage.name} {failed}; its output is {run / stage.name}.log")
                sys.exit(1)
            log(f"{stage.name} done")
    except Stopped as stop:
        log(f"stopped: {stop.signal.name} during {where}, which ended with it; the run's directory is {run}")
        sys.exit(128 + stop.signal)
    except SystemExit as e:
        if isinstance(e.code, str):  # a refusal, which says why; an exit status is a line already logged
            log(f"failed: {where}: {e.code}")
            sys.exit(1)
        raise
    except Exception as e:
        log(f"failed: {where}: {failure(e)}")
        raise
    for s in STOP:  # the commit takes a moment, and one cut short leaves the agent repo half-changed
        signal.signal(s, signal.SIG_IGN)
    try:
        committed, line = commit_report(agent, run, base, since, until, kind)
    except Exception as e:
        log(f"failed: the commit: {failure(e)}; the report stays in {run}")
        raise
    log(line)
    if not committed:
        sys.exit(1)
    return run


def failure(e: Exception) -> str:
    """An exception as a run log's line says it: a git command with what it printed, anything else by its type."""
    if isinstance(e, subprocess.CalledProcessError):
        return f"{' '.join(map(str, e.cmd))} exited {e.returncode}: {(e.stderr or '').strip()}"
    return f"{type(e).__name__}: {e}"


def collect(kind: Kind, since: datetime, until: datetime, run: Path, home: Path, projects: list[Path],
            repos: list[Path], code: list[Path], agent: Path, left_out: list[Path]) -> None:
    """Stage 1, by script: the sessions the kind reads, the git records and tickets, the workflow
    retro's permission data, and the files the period's commits touched where the lens pass reads."""
    retro_collect.collect_sessions(since, until, run, home / "digest-cache", projects, repos, agent=agent,
                                   worked=None if kind is WORKFLOW else retro_collect.Worked.of(repos, left_out))
    if kind is WORKFLOW:
        retro_collect.collect_permissions(run, projects)
    write_batches(run)
    retro_collect.collect_touched(since, until, run, code)


def resumed(run: Path, repo: Path, agent: Path, since: datetime | None, focus: str,
            seed: list[Path]) -> tuple[datetime, datetime, str, list[Path], str | None]:
    """The period, focus, seed and base of the run in `run`, from its `run.json`. Exits when the
    run was of another repo or for another report, or when the report was committed to since the
    run began: its stages read the report as it was, and its commit would undo the change."""
    if not (run / "run.json").is_file():
        sys.exit(f"{run} holds no run.json: no retro run finished collecting into it; start a new run")
    if since or focus or seed:
        sys.exit(f"{run} keeps its own period, focus and seed in run.json; --resume takes none of them")
    state = json.loads((run / "run.json").read_text())
    if state.get("repo") != str(repo):
        sys.exit(f"{run} is a run of {state.get('repo', 'a repo its run.json does not name')}, not of {repo}; start a new run")
    report = agent / REPORT_PATH
    if (was := state.get("report", str(report))) != str(report):
        sys.exit(f"{run} is a run for {was}, not for {report}; start a new run")
    if blob(agent, REPORT_PATH) != state["base"]:
        sys.exit(f"{report} was committed to since {run.name} began; start a new run, which reads it as it is")
    return (parse_time(state["since"]), parse_time(state["until"]), state["focus"],
            [Path(p) for p in state["seed"]], state["base"])


def main_checkout(agent: Path) -> Path:
    """The agent repo's main checkout, where the report is committed, also when `agent` is a
    worktree of it on another branch. Exits when `agent` is no git repo of its own: git would
    otherwise answer for the code repo around it, and the report land in that."""
    done = subprocess.run(["git", "-C", str(agent), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, text=True)
    common = Path(done.stdout.strip())
    if not (agent / ".git").exists() or done.returncode != 0 or common.name != ".git":
        sys.exit(f"{agent} is no agent repo with a main checkout, a git repo of its own, which a retro's report is "
                 f"committed in; /mx:project-setup makes one")
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


def read_list(path: Path) -> list[str]:
    """A list file's entries, one per line, `#` starting a comment; exits when the file is missing."""
    if not path.is_file():
        sys.exit(f"{path} is missing")
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]


@dataclass(frozen=True)
class Reach:
    """What a stage after read-fresh may reach beside its run directory."""
    read: list[Path]
    git: list[Path]
    """Where it may run git's read commands."""
    hidden: list[Path]
    """Directories inside `read` it may not read."""


def reach(kind: Kind, repos: list[Path], agent: Path) -> Reach:
    """The repos, their agent repos and the skills, whose files the stages' prompts name. A repo
    retro reads the sessions worked in its repos as their digests in the run directory, and the
    session pages of its agent repos, which are of every session of the project, are hidden: git,
    which would show a committed page by its commit or blob, is not run in them, and their tickets
    are read as files."""
    agents = list(dict.fromkeys(d.resolve() for d in (agent, *(r / "agent" for r in repos if (r / "agent" / ".git").exists()))))
    read = list(dict.fromkeys(d.resolve() for d in (*repos, *agents, HERE.parent)))
    if kind is WORKFLOW:
        return Reach(read, read, [])
    return Reach(read, [d for d in read if d not in agents], [a / retro_collect.session_page.SESSIONS.name for a in agents])


# ── the stages ───────────────────────────────────────────────────────────────


def write_batches(run: Path) -> None:
    """`batches.json`: the period's digests in batches of about BATCH_CHARS, a project's sessions
    together and in order of their start, named `batch-01`, …; then the older sample's, in order of
    their start, named `sample-01`, …"""
    rows = [json.loads(line) for line in (run / "sessions.jsonl").read_text().splitlines()]
    period = sorted((r for r in rows if r["set"] == "sessions"), key=lambda r: (r["project"], r["start"]))
    sample = sorted((r for r in rows if r["set"] == "sample"), key=lambda r: r["start"])
    batches = pack(run, "batch", [f"sessions/{r['id']}.md" for r in period])
    batches += pack(run, "sample", [f"sample/{r['id']}.md" for r in sample])
    (run / "batches.json").write_text(json.dumps(batches, indent=1) + "\n")


def pack(run: Path, prefix: str, digests: list[str]) -> list[dict]:
    """The digests, in their order, in batches of at most BATCH_CHARS, but for a digest larger
    than that, which is a batch of its own."""
    batches: list[dict] = []
    for path in digests:
        size = (run / path).stat().st_size
        if not batches or batches[-1]["chars"] + size > BATCH_CHARS:
            batches.append(dict(name=f"{prefix}-{len(batches) + 1:02d}", digests=[], chars=0))
        batches[-1]["digests"].append(path)
        batches[-1]["chars"] += size
    return batches


def run_stage(stage: Stage, run: Path, values: dict[str, str], within: Reach) -> str:
    """One stage's model run, from its prompt filled in with `values`; what went wrong, or nothing."""
    prompt = render((HERE / "stages" / f"{stage.name}.md").read_text(), values)
    (run / "prompts").mkdir(exist_ok=True)
    (run / "prompts" / f"{stage.name}.md").write_text(prompt)
    with (run / f"{stage.name}.log").open("w") as out:
        # A session of its own, so a signal meant for the run (a closed terminal's HUP, a Ctrl-C) reaches
        # the stage only through `end`, which `run-log` turns into the model run's end.
        process = subprocess.Popen(launch(stage, run, within), cwd=run, stdin=subprocess.PIPE, stdout=out,
                                   stderr=subprocess.STDOUT, text=True, start_new_session=True,
                                   preexec_fn=dies_with(os.getpid()),
                                   env={**os.environ, "CLAUDE_CODE_SUBAGENT_MODEL": stage.model, "GIT_OPTIONAL_LOCKS": "0",
                                        # print mode otherwise stops a subagent still running 10 minutes after the last turn
                                        "CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS": "0"})
        try:
            process.communicate(prompt)
        except Stopped:
            end(process)
            raise
    if process.returncode != 0:
        return f"exited {process.returncode}"
    if left := missing(stage, run):
        return f"left out {', '.join(left)}"
    return ""


def missing(stage: Stage, run: Path) -> list[str]:
    """The files the stage owes that the run directory lacks, or holds empty."""
    batched = any("{batch}" in p for p in stage.owes)
    batches = [b["name"] for b in json.loads((run / "batches.json").read_text())] if batched else []
    owed = [p.format(batch=b) for p in stage.owes for b in (batches if "{batch}" in p else [""])]
    return [p for p in owed if not (run / p).is_file() or not (run / p).stat().st_size]


class Stopped(Exception):
    def __init__(self, sig: signal.Signals) -> None:
        super().__init__(sig)
        self.signal = sig


# What stops a run: `job stop` and a timer's stop send TERM, Ctrl-C INT, a closed terminal HUP.
STOP = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
PR_SET_PDEATHSIG = 1
LIBC = ctypes.CDLL(None) if sys.platform.startswith("linux") else None


def on_stop(signum: int, _frame: object) -> None:
    """Stop the run where it is. A second signal is ignored, so `end` ends the stage under way whole."""
    for s in STOP:
        signal.signal(s, signal.SIG_IGN)
    raise Stopped(signal.Signals(signum))


def dies_with(parent: int) -> Callable[[], None]:
    """For a stage's process: TERM when the run's process dies, SIGKILL included, through Linux's
    parent-death signal. `run-log` ends the model run on TERM, and `timeout`, which it runs the
    model under, passes the signal to every process the model started."""
    def arm() -> None:
        if LIBC is not None:
            LIBC.prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
            if os.getppid() != parent:  # the run died before the signal was armed
                os.kill(os.getpid(), signal.SIGTERM)
    return arm


def end(process: subprocess.Popen, grace: float = 60) -> None:
    """TERM a stage's process and wait for it, KILL once `grace` seconds have passed."""
    process.terminate()
    try:
        process.wait(grace)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def launch(stage: Stage, run: Path, within: Reach) -> list[str]:
    """The command line of a stage's model run. It starts from none of the host's settings, and
    `--restricted` confines its file tools to the run directory and, after read-fresh, what is
    `within` its reach; the one write rule covers the run directory alone, the stage's scripts may
    be run on the run directory alone, git's options that write a file or read one outside the repo
    are denied, and every other write is refused, since nobody is there to approve it."""
    tools, allowed, add = "Read,Grep,Glob,Write,Edit,Agent", [f"Edit(/{run}/**)"], []
    if not stage.fresh:
        tools += ",Bash"
        # --output writes a file; blame's --contents reads any file on disk, a hidden one included.
        denied = [*(f"Bash(git -C {d} * {option}*)" for d in within.git for option in ("--output", "--contents")),
                  *(f"Read(/{h}/**)" for h in within.hidden)]
        add = ["--add-dir", *map(str, within.read), "--disallowedTools", *denied]
        allowed += [f"Bash(git -C {d} {sub}{rest})" for d in within.git for sub in GIT_READS for rest in ("", " *")]
        allowed += [f"Bash({script} {run})" for script in stage.runs]
    return ["bash", str(RUN_LOG), "run", "--site", f"retro-{stage.name}", "--timeout", str(STAGE_TIMEOUT), "--",
            "claude", "-p", "--model", stage.model, "--effort", stage.effort,
            "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
            "--settings", '{"autoMemoryEnabled": false}', "--restricted", *add, "--allowedTools", *allowed,
            "--tools", tools, "--permission-mode", "manual", "--permission-prompts", "none"]


def render(template: str, values: dict[str, str]) -> str:
    """A stage's prompt with each `{{name}}` replaced by its value; an unknown name is an error."""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)


# ── the earlier reports ──────────────────────────────────────────────────────


def run_commits(agent: Path) -> list[tuple[str, datetime]]:
    """The commits a run made of the report, newest first, each with the end of its period."""
    out = git(agent, "log", "--format=%H %(trailers:key=Retro-until,valueonly,separator=)", "--", REPORT_PATH)
    return [(sha, parse_time(until)) for sha, until in (line.split(" ", 1) for line in out.splitlines()) if until]


def write_previous(run: Path, agent: Path, runs: list[tuple[str, datetime]], seed: list[Path]) -> None:
    """`previous/`: the report as it stands now, verdicts since the last run included, as
    `current.md`; the last three runs' reports, each named for the end of its period; and the
    seed, the reports a first run takes as its previous ones, under `seed/`. Built beside it and
    renamed into place, so a `previous/` a stopped run left is whole."""
    previous = run / "previous.partial"
    shutil.rmtree(previous, ignore_errors=True)
    previous.mkdir()
    if blob(agent, REPORT_PATH):
        (previous / "current.md").write_text(git(agent, "show", f"HEAD:{REPORT_PATH}"))
    for sha, until in runs[:3]:
        (previous / f"{dirname(until)}.md").write_text(git(agent, "show", f"{sha}:{REPORT_PATH}"))
    if seed:
        (previous / "seed").mkdir()
        for path in seed:
            shutil.copy(path, previous / "seed" / path.name)
    previous.rename(run / "previous")


# ── the commit ───────────────────────────────────────────────────────────────


def commit_report(agent: Path, run: Path, base: str | None, since: datetime, until: datetime,
                  kind: Kind) -> tuple[bool, str]:
    """Copy the run's report and page into the report's directory and commit those two files alone.
    Whether it committed, and the line the run log gets, saying what was committed or why nothing was."""
    paths = [f"{qualified.RETRO}/{name}" for name in REPORT]
    gitdir = Path(git(agent, "rev-parse", "--absolute-git-dir").strip())
    if busy := [op for marker, op in IN_PROGRESS.items() if (gitdir / marker).exists()]:
        return False, f"not committed: {agent} is mid-{busy[0]}; the report stays in {run}"
    if blob(agent, REPORT_PATH) != base:
        return False, f"not committed: {agent}/{REPORT_PATH} was committed to while the run ran; the report stays in {run}"
    if changed := git(agent, "status", "--porcelain", "--", *paths).strip():
        changes = ", ".join(line[3:] for line in changed.splitlines())
        return False, f"not committed: {changes} has changes of its own in {agent}; the report stays in {run}"
    (agent / qualified.RETRO).mkdir(parents=True, exist_ok=True)
    for name in REPORT:
        shutil.copy(run / name, agent / qualified.RETRO / name)
    link_tags(agent)
    message = (f"retro: the {kind.name} of {since.date()} to {until.date()}\n\n"
               f"Retro-since: {stamp(since)}\nRetro-until: {stamp(until)}\n")
    try:
        # `--only` stages a tracked file itself, so a commit that fails leaves it unstaged; a first
        # run's files, untracked, need the add.
        if new := [path for path in paths if blob(agent, path) is None]:
            git(agent, "add", "--", *new)
        git(agent, "commit", "--quiet", "--only", "-m", message, "--", *paths)
    except subprocess.CalledProcessError as e:
        restore(agent, paths)
        return False, f"not committed: git {e.cmd[3]} failed ({(e.stderr or e.stdout).strip()}); the report stays in {run}"
    return True, f"committed {git(agent, 'rev-parse', '--short', 'HEAD').strip()} in {agent}"


def link_tags(agent: Path) -> None:
    """Make each qualified tag on the report's page in `agent` a link to what it names, as the
    tracker and the reviews stand now, the report's own entries included."""
    page = agent / qualified.RETRO / "report.html"
    page.write_text(qualified.link_html(page.read_text(), qualified.cites(agent), qualified.hrefs(agent, page)))


def restore(agent: Path, paths: list[str]) -> None:
    """Put each file back as HEAD has it, unstaged. Each step stands alone, and the file's text
    comes from the object store, not the index: what failed the commit is most often another
    process holding the index's lock, which fails a reset too."""
    for path in paths:
        subprocess.run(["git", "-C", str(agent), "reset", "--quiet", "--", path], capture_output=True)
        if (committed := blob(agent, path)) is None:
            (agent / path).unlink(missing_ok=True)
        else:
            (agent / path).write_bytes(subprocess.run(["git", "-C", str(agent), "cat-file", "blob", committed],
                                                      capture_output=True, check=True).stdout)


def blob(agent: Path, path: str) -> str | None:
    """The object id of `path` at HEAD, None when HEAD has no such file."""
    done = subprocess.run(["git", "-C", str(agent), "rev-parse", "--verify", "--quiet", f"HEAD:{path}"],
                          capture_output=True, text=True)
    return done.stdout.strip() or None


# ── command line ─────────────────────────────────────────────────────────────


@dataclass
class Args:
    repo: tyro.conf.Positional[Path]
    """The project the retro is for, whose agent repo at `agent/` holds its tracker and the report: the agents repo, which holds the mx plugin, for the workflow retro; any other for a repo retro, which reads every repo its `agent/repos.toml` lists beside it but one with `retro = false` or an agent repo of its own."""
    focus: str = ""
    """What max names for this run to look at: a pattern ("the tests are overbuilt"), which becomes one of a workflow retro's deep-dives, or a module or pain point, which directs the lens pass."""
    since: str = ""
    """The period's start, an ISO date or time, UTC where it names no offset; by default the end of the last run committed to the report, and for a repo retro's first run `--first-weeks` before its end. A run after a gap reads the whole gap, since the last report."""
    first_weeks: int = FIRST_WEEKS
    """How many weeks a repo retro's first run reads back, given no --since."""
    seed: list[Path] = field(default_factory=list)
    """Files the run's later stages read as earlier reports, beside those in git history; no two may share a name."""
    data: Path = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "retro"
    """The retro's data directory, outside every git repo."""
    projects: list[Path] = field(default_factory=retro_collect.profiles)
    """Each Claude Code profile's directory of transcripts, whose sessions the workflow retro reads every one of and a repo retro those worked in its repos; by default every `~/.claude*/projects`."""
    if_active: bool = False
    """Skip the run, exiting 3, when there is nothing new since the period's start: for the workflow retro, no message of max's in an interactive session and no commit of his in the listed repos; for a repo retro, no commit in any of its repos."""
    resume: Path | None = None
    """An earlier run's directory: the run keeps its period, focus and seed, and picks up at the first stage that left out a file it owes."""
    model: str = ""
    """The model every stage of this run runs on, in place of each stage's own (`Stage.model`, in this file's stage table); a try on a cheaper model is `--model claude-sonnet-5-5`."""
    effort: str = ""
    """The effort every stage of this run runs at, in place of each stage's own."""


if __name__ == "__main__":
    args = tyro.cli(Args, description=__doc__)
    run_retro(args.repo, args.data, args.projects, parse_time(args.since) if args.since else None, args.focus, args.seed,
              resume=args.resume, if_active=args.if_active, model=args.model, effort=args.effort, first_weeks=args.first_weeks)
