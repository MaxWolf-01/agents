#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""Gather what a retro reads, for the period since a given start, into a run directory outside
every git work tree. `retro_run.py` runs it as a run's collect stage; its subcommands run it alone.

`sessions`, what a retro reads of sessions and git, writes into the run directory:

- `sessions/<id>.md`: a digest of every interactive session with an entry in the period, from
  every Claude Code profile given, holding the period's days alone; in a repo retro, of those
  alone that worked in the repos its tracker plans (`Worked`). A digest keeps max's messages
  verbatim, pasted text clipped; every tool call's input, error and denial in full; the model's
  text; and the session page's turn records. It keeps no tool output. Beside them it marks
  interrupts, rewinds, messages queued while the agent worked, hook send-backs, context
  compactions and how long each turn took.
- `sample/<id>.md`: digests of about 20 older sessions, from two to eight weeks before the end
  of the period, drawn at random, weighted to sessions with more of max's messages; in a repo
  retro, from those that worked in its repos.
- `sessions.jsonl`: one row per digest above: id, profile, project, start, end, max's messages,
  and which of the two it is in.
- `git/<repo>.md` and `versions.md`, as `git` writes the first.
- `proposed.md` and `in-flight.md`, given an agent repo: its commit at collect time and the slugs
  of the tickets proposed, and of those in flight (open, claimed or review), at that commit, each
  as it stood in `proposed/<slug>.md` and `in-flight/<slug>.md`.
- `permissions/<profile>/`, what a workflow retro reads beside them, for each profile: `scan.json`,
  the Bash calls of the period no allowlist rule covers, as `scan_unapproved.py` buckets them;
  `rules.json`, the permission rules and auto mode settings of the profile's own settings files;
  and `auto-mode.json`, the effective auto mode config `claude auto-mode config` prints for it, or
  `auto-mode.failed` saying why there is none.

`git` writes `git/<repo>.md` alone, for each repo given: its commits in the period with their
messages, its reverts, and, where the repo holds an agent repo, the tickets filed, every status
change, the tickets deleted, and the worker reports committed in the period.

Both kinds also get `touched.md`, the files the period's commits touched in the repos whose code
the lens pass reads.

Digests are cached per session in the cache directory and digested again only once the
transcript or its session page changed.

Examples:

    retro_collect.py sessions --since 2026-10-05 --run ~/.local/share/retro/runs/2026-10-12 \\
        --repos ~/repos/github/MaxWolf-01/agents ~/.dotfiles
    retro_collect.py git --since 2026-10-05 --run /tmp/run --repos ~/.dotfiles
"""

from __future__ import annotations

import itertools
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "session-page"))
import scan_unapproved  # noqa: E402
import session_page  # noqa: E402  what counts as the user's own message, as the session page reads it
import tracker  # noqa: E402  a ticket file and the repo list, as the tracker reads them

SAMPLE_SIZE = 20
SAMPLE_WINDOW = (timedelta(weeks=2), timedelta(weeks=8))  # how far before the period's end
PASTE_CLIP = 600  # pasted text in a message of max's
# A denial in a transcript that predates `toolDenialKind`: the harness's own wordings, not a shell's "Permission denied".
DENIAL = re.compile(r"^(Permission to use \S+ has been denied|The user doesn't want to proceed)")
# An absolute path, or one from the home, in any string of a tool call's input: a field of its own, or a word of a
# command or of a file's text.
NAMED_PATH = re.compile(r"(?<![\w.~/$-])~?/[^\s\"'`;|&<>(){}\[\],]*")
PASTED = re.compile(r"(<pasted_content\b[^>]*>)(.*?)(</pasted_content>)", re.S)
IN_FLIGHT = tuple(s for s in tracker.STATUSES if s not in ("proposed", "done"))  # ruled on, not done yet
RETRO = Path("retro")  # in an agent repo: its report, and under `<name>/` the report a listed repo kept before its tracker's retro folded it in


# ── what runs ────────────────────────────────────────────────────────────────


def collect_sessions(since: datetime, until: datetime, run: Path, cache: Path, projects: list[Path],
                     repos: list[Path], sample_seed: int | None = None, agent: Path | None = None,
                     worked_in: list[Path] | None = None) -> None:
    """The digests, the git records, the versions and the tickets, written into `run`: of every
    session, or of the sessions alone that worked in the repos `worked_in` names."""
    worked = Worked.of(worked_in) if worked_in is not None else None
    def kept(d: Digest, first: datetime, last: datetime) -> bool:
        return worked is None or worked.by(d, first, last)

    digests = interactive_digests(projects, cache, repos, min(since, until - SAMPLE_WINDOW[1]))
    period = [d for d in digests if d.end >= since and d.start <= until and kept(d, since, until)]
    ids = {d.sid for d in period}
    older = [d for d in digests if d.sid not in ids and until - SAMPLE_WINDOW[1] <= d.start <= until - SAMPLE_WINDOW[0]
             and kept(d, d.start, d.end)]
    write_digests(run, since, period, weighted_sample(older, SAMPLE_SIZE, random.Random(sample_seed)))
    collect_git(since, run, repos, until)
    (run / "versions.md").write_text(versions(since, until, period, repos))
    if agent:
        collect_tickets(run, agent)


def write_digests(run: Path, since: datetime, period: list[Digest], sample: list[Digest]) -> None:
    """`sessions/<id>.md`, each digest of the period from the day `since` falls on, `sample/<id>.md`,
    and `sessions.jsonl`, a row per digest."""
    rows = []
    for where, chosen in (("sessions", period), ("sample", sample)):
        (run / where).mkdir(parents=True, exist_ok=True)
        for stale in (run / where).glob("*.md"):  # a run again into the same directory replaces its digests
            stale.unlink()
        for d in sorted(chosen, key=lambda d: d.start):
            (run / where / f"{d.sid}.md").write_text(d.since(since) if where == "sessions" else d.text)
            rows.append(dict(id=d.sid, set=where, profile=d.profile, project=d.cwd, start=stamp(d.start),
                             end=stamp(d.end), messages=d.messages))
    (run / "sessions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def collect_touched(since: datetime, until: datetime, run: Path, repos: list[Path]) -> None:
    """`touched.md`: per repo, the files the period's commits touched that it still tracks, by how
    many of those commits touched each, most first."""
    out = ["# Files the period's commits touched", "",
           f"From {stamp(since)} to {stamp(until)}, on any local branch; each file a repo still tracks, with how many "
           f"of the period's commits touched it."]
    for repo in repos:
        log = git(repo, "log", "--branches", f"--since-as-filter={since.isoformat()}", f"--until={until.isoformat()}",
                  "--format=", "--name-only")
        tracked = set(git(repo, "ls-files").splitlines())
        counts = Counter(path for path in log.splitlines() if path in tracked)
        out += ["", f"## {repo.resolve()}", "", *(f"- {n} {path}" for path, n in sorted(counts.items(), key=lambda pn: (-pn[1], pn[0])))]
    run.mkdir(parents=True, exist_ok=True)
    (run / "touched.md").write_text("\n".join(out) + "\n")


def latest_commit(repos: list[Path], since: datetime) -> str:
    """The newest commit on any local branch of the repos since `since`, or "" when there is none."""
    found = [(parse_time(rows[0]["date"]), rows[0]["sha"], repo) for repo in repos if (rows := commits(repo, since))]
    if not found:
        return ""
    at, sha, repo = max(found, key=lambda f: f[0])
    return f"a commit at {stamp(at)} in {repo.resolve()} ({sha[:7]})"


def collect_git(since: datetime, run: Path, repos: list[Path], until: datetime | None = None) -> None:
    """`git/<repo>.md` for each repo: its commits since `since`, and its agent repo's tickets."""
    (run / "git").mkdir(parents=True, exist_ok=True)
    names = Counter()
    for repo in repos:
        name = repo.resolve().name.lstrip(".")
        names[name] += 1
        if names[name] > 1:
            name = f"{name}-{names[name]}"
        (run / "git" / f"{name}.md").write_text(git_record(repo, since, until))


def activity(since: datetime, projects: list[Path], cache: Path, repos: list[Path]) -> str:
    """A sign of max since `since`, or "" when there is none: his latest message in an
    interactive session, else a commit of his on a branch of one of the repos, his being the author
    identity the repo itself commits with. The digests it reads are cached as a run's are."""
    said = [d for d in interactive_digests(projects, cache, repos, since) if d.said_last and parse_time(d.said_last) >= since]
    if said:
        d = max(said, key=lambda d: d.said_last)
        return f"a message of max's at {d.said_last} in session {d.sid} ({d.cwd})"
    for repo in repos:
        who = subprocess.run(["git", "-C", str(repo), "var", "GIT_AUTHOR_IDENT"], capture_output=True, text=True)
        if who.returncode != 0 or not (email := re.search(r"<([^>]*)>", who.stdout)):
            sys.exit(f"{repo} has no author identity, which is what tells max's commits from the rest")
        if line := git(repo, "log", "--branches", "-1", f"--since-as-filter={since.isoformat()}", "--fixed-strings",
                       f"--author=<{email.group(1)}>", "--format=%h %cI").strip():
            sha, date = line.split()
            return f"a commit of max's at {stamp(parse_time(date))} in {repo.resolve()} ({sha})"
    return ""


def refuse_inside_git(*directories: Path) -> None:
    """Exit, writing nothing, when a directory is or would be inside a git work tree."""
    for directory in directories:
        existing = next(p for p in (directory.resolve(), *directory.resolve().parents) if p.exists())
        inside = subprocess.run(["git", "-C", str(existing), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True)
        if inside.stdout.strip() == "true":
            sys.exit(f"{directory} is inside a git work tree; a retro's run and cache stay outside every repo")


def refuse_unless_git(repos: list[Path]) -> None:
    """Exit, writing nothing, when a repo given is no git repo."""
    for repo in repos:
        if subprocess.run(["git", "-C", str(repo), "rev-parse"], capture_output=True).returncode != 0:
            sys.exit(f"{repo} is no git repo")


# ── permissions ──────────────────────────────────────────────────────────────

SETTINGS = ("settings.json", "settings.local.json")  # a profile's own settings files


def collect_permissions(since: datetime, run: Path, projects: list[Path]) -> None:
    """`permissions/<profile>/` for each profile's directory of transcripts in `projects`."""
    for root in projects:
        profile = root.parent
        out = run / "permissions" / profile.name.lstrip(".")
        out.mkdir(parents=True, exist_ok=True)
        settings = [profile / name for name in SETTINGS if (profile / name).is_file()]
        (out / "rules.json").write_text(json.dumps({p.name: rules(p) for p in settings}, indent=1) + "\n")
        commands = scan_unapproved.scan_sessions(root, since.timestamp()) if root.is_dir() else []
        found = scan_unapproved.scan(scan_unapproved.load_allowlist(*settings), commands)
        (out / "scan.json").write_text(json.dumps(found, indent=1) + "\n")
        for stale in ("auto-mode.json", "auto-mode.failed"):
            (out / stale).unlink(missing_ok=True)
        name, text = auto_mode(profile, run)
        (out / name).write_text(text)


def rules(settings: Path) -> dict:
    """A settings file's permission rules and auto mode settings."""
    try:
        data = json.loads(settings.read_text())
    except json.JSONDecodeError as e:
        return {"unreadable": str(e)}
    return {key: data[key] for key in ("permissions", "autoMode") if key in data}


def auto_mode(profile: Path, cwd: Path) -> tuple[str, str]:
    """The profile's effective auto mode config: the file to write, `auto-mode.json` or
    `auto-mode.failed`, and what it holds."""
    try:
        # From a directory with no project settings, which the config would otherwise merge in.
        done = subprocess.run(["claude", "auto-mode", "config"], capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, cwd=cwd, env={**os.environ, "CLAUDE_CONFIG_DIR": str(profile)})
    except (OSError, subprocess.TimeoutExpired) as e:
        return "auto-mode.failed", f"claude auto-mode config failed: {e}\n"
    if done.returncode != 0:
        return "auto-mode.failed", f"claude auto-mode config exited {done.returncode}: {done.stderr.strip()}\n"
    return "auto-mode.json", done.stdout


# ── the tickets ──────────────────────────────────────────────────────────────


def collect_tickets(run: Path, agent: Path) -> None:
    """The agent repo's tickets as they stand at its commit now: those
    proposed, by slug in `proposed.md` and each in `proposed/<slug>.md`, and those in flight, in
    `in-flight.md` and `in-flight/<slug>.md`."""
    sha = git(agent, "rev-parse", "HEAD").strip()
    found = subprocess.run(["git", "-C", str(agent), "grep", "-l", "-E", f"^status: *({'|'.join(('proposed', *IN_FLIGHT))}) *$",
                            sha, "--", "tickets/*.md"], capture_output=True, text=True)
    if found.returncode > 1:  # 1 is git grep finding nothing
        raise subprocess.CalledProcessError(found.returncode, found.args, found.stdout, found.stderr)
    texts = {Path(path).stem: git(agent, "show", f"{sha}:{path}")
             for path in sorted(line.split(":", 1)[1] for line in found.stdout.splitlines())}
    tickets = [tracker.read(Path(f"{slug}.md"), text) for slug, text in texts.items()]
    for name, title, statuses in (("proposed", "Proposed tickets", ("proposed",)), ("in-flight", "Tickets in flight", IN_FLIGHT)):
        chosen = [t for t in tickets if t.status in statuses]
        (run / name).mkdir(parents=True, exist_ok=True)
        for t in chosen:
            (run / name / f"{t.slug}.md").write_text(texts[t.slug])
        (run / f"{name}.md").write_text("\n".join([
            f"# {title} ({len(chosen)})", "",
            f"The agent repo `{agent}` at {sha}, when the run collected. Each ticket, as it stood then, is "
            f"`{name}/<slug>.md`.", "",
            *(f"- {t.slug}" + ("" if name == "proposed" else f": {t.status}") for t in chosen)]) + "\n")


def planned(agent: Path) -> list[Path]:
    """The repos the agent repo's repo list names, by their paths; exits when the list cannot be read."""
    root = agent / tracker.TICKETS.name
    try:
        return [tracker.listed_path(root, table) for table in tracker.repo_list(root).values()]
    except tracker.Refused as refused:
        sys.exit(str(refused))


def folded(agent: Path) -> list[str]:
    """The names of the reports the agent repo holds at HEAD beside its own, `retro/<name>/report.md`:
    each a report a listed repo kept of its own before its tracker's retro took it in."""
    if subprocess.run(["git", "-C", str(agent), "rev-parse", "--verify", "--quiet", "HEAD"], capture_output=True).returncode:
        return []  # no commit yet, so no report
    paths = git(agent, "ls-tree", "-r", "--name-only", "HEAD", "--", str(RETRO)).splitlines()
    return sorted(Path(p).parent.name for p in paths if Path(p).match(f"{RETRO}/*/report.md"))


# ── which sessions ───────────────────────────────────────────────────────────


def profiles() -> list[Path]:
    """Every Claude Code profile's directory of transcripts under the home: `~/.claude*/projects`."""
    return sorted(p for p in Path.home().glob(".claude*/projects") if p.is_dir())


def interactive_digests(projects: list[Path], cache: Path, repos: list[Path], since: datetime) -> list[Digest]:
    """The digest of every interactive session whose transcript was written to since `since`."""
    transcripts = [t for t in find_transcripts(projects) if t.stat().st_mtime >= since.timestamp()]
    return [d for d in digest_all(transcripts, cache, repos) if d.interactive and d.text]


@dataclass(frozen=True)
class Worked:
    """Where a session has to have worked to count for a tracker's repos: inside one of them or a
    worktree git lists for one, or inside a directory beside one named `<repo>-<anything>` that no
    longer exists, which is what a worktree made beside the repo leaves once it is removed."""
    roots: tuple[Path, ...]
    repos: tuple[Path, ...]

    @staticmethod
    def of(repos: list[Path]) -> Worked:
        return Worked(tuple(w for r in repos for w in worktrees(r)), tuple(r.resolve() for r in repos))

    def by(self, d: Digest, first: datetime, last: datetime) -> bool:
        """Whether the session, on a day from `first` to `last`, ran there or made a tool call naming
        a path there."""
        days = [t.astimezone(UTC).date().isoformat() for t in (first, last)]
        return any(self.holds(p) for day, paths in d.paths.items() if days[0] <= day <= days[1] for p in paths)

    def holds(self, path: str) -> bool:
        """A path taken as it resolves now, so one through a symlink counts where the link points."""
        p = Path(os.path.realpath(os.path.expanduser(path)))
        if any(p.is_relative_to(root) for root in self.roots):
            return True
        for repo in self.repos:
            if p.is_relative_to(repo.parent) and p != repo.parent:
                beside = repo.parent / p.relative_to(repo.parent).parts[0]
                if beside.name.startswith(f"{repo.name}-") and not beside.exists():
                    return True
        return False


def worktrees(repo: Path) -> list[Path]:
    """The repo's main checkout and every worktree of it, resolved."""
    out = git(repo, "worktree", "list", "--porcelain")
    return [Path(line.split(" ", 1)[1]).resolve() for line in out.splitlines() if line.startswith("worktree ")]


def find_transcripts(projects: list[Path]) -> list[Path]:
    """Every session's transcript under the profiles' project directories."""
    return [t for root in projects if root.is_dir() for t in sorted(root.glob("*/*.jsonl"))]


def weighted_sample(digests: list[Digest], k: int, rng: random.Random) -> list[Digest]:
    """`k` digests drawn without replacement, each with odds proportional to max's messages in
    it (Efraimidis and Spirakis' keys)."""
    keyed = [(rng.random() ** (1 / d.messages), d) for d in digests if d.messages > 0]
    return [d for _, d in sorted(keyed, key=lambda kd: kd[0], reverse=True)[:k]]


# ── the digest, and its cache ────────────────────────────────────────────────


@dataclass
class Digest:
    sid: str
    profile: str
    cwd: str
    start: datetime
    end: datetime
    interactive: bool
    messages: int
    text: str
    said_last: str = ""  # when max's last message in it was sent, "" when none was
    versions: dict[str, dict[str, list[str]]] = field(default_factory=dict)  # Claude Code version: day: [first, last seen]
    models: dict[str, dict[str, list[str]]] = field(default_factory=dict)  # model: day: [first, last seen]
    days: dict[str, int] = field(default_factory=dict)  # each day's heading: where in `text` it starts
    paths: dict[str, list[str]] = field(default_factory=dict)  # day: the working directories and the paths its tool calls named
    page_at: int = 0  # where in `text` the days end and the session page's records begin

    def since(self, start: datetime) -> str:
        """The digest from the day `start` falls on: its header, a line naming the days before,
        then the rest. A session that went on for weeks is otherwise read again every week."""
        first = start.astimezone(UTC).date()
        before = sorted(d for d in self.days if d < first.isoformat())
        if not before:
            return self.text
        after = [o for d, o in self.days.items() if d >= first.isoformat()]
        head = self.text[:min(self.days.values())]
        gap = f"\n(left out: {before[0]} to {first - timedelta(days=1)}, the days before the period)\n"
        return head + gap + self.text[min(after, default=self.page_at):]

    def to_json(self) -> dict:
        return {**self.__dict__, "start": stamp(self.start), "end": stamp(self.end)}

    @staticmethod
    def from_json(d: dict) -> Digest:
        return Digest(**{**d, "start": parse_time(d["start"]), "end": parse_time(d["end"])})


def digest_all(transcripts: list[Path], cache: Path, repos: list[Path]) -> list[Digest]:
    """Each transcript's digest, from the cache where its key still matches, else digested now
    and cached."""
    cache.mkdir(parents=True, exist_ok=True)
    out, todo = [], []
    for t in transcripts:
        records = page_records(t, repos)
        key = cache_key(t, records)
        cached = cache / f"{t.parent.parent.parent.name}-{t.stem}.json"
        if cached.exists() and (hit := json.loads(cached.read_text()))["key"] == key:
            out.append(Digest.from_json(hit["digest"]))
        else:
            todo.append((t, records, key, cached))
    pool = ProcessPoolExecutor(min(8, os.cpu_count() or 1)) if len(todo) > 4 else _Inline()
    try:
        for (t, records, key, cached), d in zip(todo, pool.map(digest, [t for t, *_ in todo], [r for _, r, *_ in todo])):
            if d is not None:
                cache_digest(cached, key, d)
                out.append(d)
    finally:
        pool.shutdown(cancel_futures=True)  # on a stop, the queued digests are cancelled and those under way finished
    return out


def cache_digest(cached: Path, key: list, d: Digest) -> None:
    """Write a cached digest whole or not at all: a run stopped mid-write leaves the old file or none."""
    partial = cached.with_suffix(".partial")
    partial.write_text(json.dumps({"key": key, "digest": d.to_json()}))
    partial.replace(cached)


class _Inline:
    def shutdown(self, cancel_futures: bool = False) -> None:
        pass

    @staticmethod
    def map(f, *items):
        return map(f, *items)


CACHE_FORMAT = 8  # raised when a cached digest's shape changes, so every cached digest is redone


def cache_key(transcript: Path, records: list[Path]) -> list:
    """What a digest is digested from, by size and modification time, and the digest's format."""
    return [CACHE_FORMAT, *([str(p), p.stat().st_size, p.stat().st_mtime_ns] for p in (transcript, *records))]


def page_records(transcript: Path, repos: list[Path]) -> list[Path]:
    """The session page's records of a session: `session.md` and its turn records, in the agent
    repo of the project its working directory is in, else of any repo given."""
    sid = transcript.stem
    cwd = first_cwd(transcript)
    candidates = []
    if cwd and Path(cwd).is_dir() and (d := session_page.session_directory(Path(cwd), sid)) is not None:
        candidates.append(d)
    candidates += [r / "agent" / session_page.SESSIONS.name / sid for r in repos]
    for d in candidates:
        if d.is_dir():
            return [p for p in [d / "session.md", *sorted((d / "turns").glob("*.md"))] if p.is_file()]
    return []


def first_cwd(transcript: Path) -> str:
    with transcript.open() as f:
        for line in f:
            if m := re.search(r'"cwd":"((?:[^"\\]|\\.)*)"', line):
                return json.loads(f'"{m.group(1)}"')
    return ""


def digest(transcript: Path, records: list[Path]) -> Digest | None:
    """A session as the retro reads it: the user's messages, the model's text, every tool call's
    input, errors, denials and hook send-backs, each under its time, then the session page's
    records. None for a transcript with no timed entry."""
    entries = session_page.read_transcript(transcript)
    times = [parse_time(e["timestamp"]) for e in entries if e.get("timestamp")]
    if not times:
        return None
    lines: list[str] = []
    headings: dict[str, int] = {}  # each day's heading: its index in `lines`
    day = None
    calls: dict[str, str] = {}
    parents: Counter = Counter()
    versions: dict[str, dict[str, list[str]]] = {}
    models: dict[str, dict[str, list[str]]] = {}
    messages = 0
    said_last: datetime | None = None
    paths: dict[str, set[str]] = {}

    def put(at: datetime | None, text: str) -> None:
        nonlocal day
        if at is not None and at.date() != day:
            day = at.date()
            headings[day.isoformat()] = len(lines)
            lines.append(f"\n## {day.isoformat()}\n")
        lines.append(f"[{at:%H:%M}] {text}" if at else text)

    for e in entries:
        if e.get("isSidechain"):
            continue
        at = parse_time(e["timestamp"]) if e.get("timestamp") else None
        if at and isinstance(e.get("cwd"), str) and e["cwd"]:
            paths.setdefault(at.date().isoformat(), set()).add(e["cwd"])
        if at and e.get("version"):
            seen(versions, e["version"], at)
        kind = e.get("type")
        if kind == "assistant":
            message = e.get("message", {})
            if at and message.get("model") and message["model"] != "<synthetic>":
                seen(models, message["model"], at)
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text", "").strip():
                    put(at, f"A: {block['text'].strip()}")
                elif block.get("type") == "tool_use":
                    calls[block.get("id", "")] = block.get("name", "?")
                    if at:
                        paths.setdefault(at.date().isoformat(), set()).update(named_paths(block.get("input")))
                    put(at, f"→ {block.get('name', '?')} {json.dumps(block.get('input'), ensure_ascii=False)}")
        elif kind == "system":
            sub = e.get("subtype")
            if sub == "stop_hook_summary" and (e.get("preventedContinuation") or e.get("hookErrors")):
                put(at, f"! STOP HOOK {'blocked' if e.get('preventedContinuation') else 'errored'}: "
                        f"{e.get('stopReason') or ''} {json.dumps(e.get('hookErrors') or [], ensure_ascii=False)}")
            elif sub == "api_error":
                put(at, f"! API ERROR {json.dumps(e.get('error') or e.get('content') or '', ensure_ascii=False)}")
            elif sub == "turn_duration" and e.get("durationMs"):
                s = e["durationMs"] // 1000
                put(None, f"(turn took {s // 60}m{s % 60:02d}s)")
            elif sub == "compact_boundary":
                put(at, "(context compacted)")
        elif kind == "attachment":
            a = e.get("attachment", {})
            if a.get("type") == "hook_additional_context":
                put(at, f"! HOOK → agent: {flatten(a.get('content'))}")
            elif a.get("type") == "queued_command" and a.get("commandMode", "prompt") == "prompt" and (t := said(a.get("prompt"))):
                messages += 1
                said_last = at or said_last
                put(at, f"MAX (queued while the agent worked): {t}")
        elif kind == "user" and session_page.prompted(e):
            content = e.get("message", {}).get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                    name = calls.get(block.get("tool_use_id", ""), "?")
                    error = flatten(block.get("content"))
                    if e.get("toolDenialKind") or DENIAL.search(error):
                        put(at, f"! DENIED {name} ({e.get('toolDenialKind') or 'denial'}): {error}")
                    else:
                        put(at, f"! ERROR {name}: {error}")
            if e.get("isCompactSummary") or e.get("origin", {}).get("kind", "human") != "human":
                continue
            text = session_page.flat(content)
            if text.lstrip().startswith("[Request interrupted"):
                put(at, "MAX INTERRUPTED")
                continue
            if not (t := said(content)):
                continue
            messages += 1
            said_last = at or said_last
            tag = "MAX"
            if parent := e.get("parentUuid"):
                parents[parent] += 1
                if parents[parent] > 1:
                    tag = "MAX REWOUND and re-sent (the agent's turn after the first send was abandoned)"
            if e.get("promptSource") == "queued":
                tag += " (queued while the agent worked)"
            put(at, f"{tag}: {t}")

    interactive = any(e.get("entrypoint") == "cli" for e in entries)
    cwd = next((e["cwd"] for e in entries if isinstance(e.get("cwd"), str) and e["cwd"]), "")
    profile = transcript.parent.parent.parent.name
    start, end = min(times), max(times)
    head = [f"# session {transcript.stem}", f"title: {session_page.claude_title(entries) or '-'}",
            f"project: {cwd or transcript.parent.name}", f"profile: {profile}",
            f"from {stamp(start)} to {stamp(end)}, {messages} messages of max's",
            f"models: {', '.join(models) or '-'}", f"claude code: {', '.join(versions) or '-'}"]
    page = [f"\n## Session page: {r.parent.name + '/' if r.parent.name == 'turns' else ''}{r.name}\n\n{r.read_text().strip()}"
            for r in records]
    text = "\n".join(head + lines + page) + "\n" if interactive else ""  # only interactive sessions are read
    starts = list(itertools.accumulate((len(line) + 1 for line in lines), initial=len("\n".join(head)) + 1))
    return Digest(sid=transcript.stem, profile=profile, cwd=cwd, start=start, end=end, interactive=interactive,
                  messages=messages, text=text, said_last=stamp(said_last) if said_last else "",
                  versions=versions, models=models, days={d: starts[i] for d, i in headings.items()} if interactive else {},
                  page_at=starts[-1] - 1 if interactive else 0,
                  paths={day: sorted(named) for day, named in paths.items()} if interactive else {})


def named_paths(value: object) -> Iterable[str]:
    """The paths NAMED_PATH finds in every string of a tool call's input."""
    if isinstance(value, str):
        yield from NAMED_PATH.findall(value)
    for item in value.values() if isinstance(value, dict) else value if isinstance(value, list) else ():
        yield from named_paths(item)


def said(content: object) -> str:
    """A prompt of max's as the session page reads it, each pasted block clipped first; empty for
    what Claude Code writes as the user."""
    pasted = PASTED.sub(lambda m: m.group(1) + clip(m.group(2), PASTE_CLIP) + m.group(3), session_page.flat(content))
    if not (text := session_page.message_text(pasted)):
        return ""
    images = sum(1 for b in content if isinstance(b, dict) and b.get("type") == "image") if isinstance(content, list) else 0
    return text + " [image]" * images


def clip(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    head = n * 2 // 3
    return f"{s[:head]} […{len(s) - n} chars clipped…] {s[len(s) - (n - head):]}"


def flatten(content: object) -> str:
    """Any content's text, a tool result's included, which `session_page.flat` leaves out."""
    if isinstance(content, list):
        return "\n".join(flatten(c) for c in content)
    if isinstance(content, dict):
        return content.get("text", "") if content.get("type", "text") == "text" else f"[{content.get('type')}]"
    return str(content or "")


def seen(record: dict[str, dict[str, list[str]]], key: str, at: datetime) -> None:
    """Note `key` as seen at `at`: the first and last time it was, per UTC day."""
    days, day, now = record.setdefault(key, {}), at.astimezone(UTC).date().isoformat(), stamp(at)
    first, last = days.get(day, [now, now])
    days[day] = [min(first, now), max(last, now)]


def parse_time(s: str) -> datetime:
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def stamp(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── git ──────────────────────────────────────────────────────────────────────

SEP, END = "\x1f", "\x1e"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def commits(repo: Path, since: datetime, *paths: str, until: datetime | None = None) -> list[dict]:
    """The commits on any local branch committed after `since` (and by `until`), newest first.
    `--since` alone stops at the first commit dated before it, which skips a commit of the period
    beneath one with an older date."""
    out = git(repo, "log", "--branches", f"--since-as-filter={since.isoformat()}",*([f"--until={until.isoformat()}"] if until else []),
              f"--format=%H{SEP}%cI{SEP}%an{SEP}%s{SEP}%b{END}",
              "--", *paths)
    rows = []
    for chunk in out.split(END):
        if chunk.strip():
            sha, date, author, subject, body = chunk.strip("\n").split(SEP)
            rows.append(dict(sha=sha, date=date, author=author, subject=subject, body=body.strip()))
    return rows


def git_record(repo: Path, since: datetime, until: datetime | None = None) -> str:
    """A repo's commits since `since` in markdown, its reverts, and its agent repo's tickets."""
    rows = commits(repo, since, until=until)
    out = [f"# {repo.resolve()} since {stamp(since)}", "", f"## Commits ({len(rows)})", ""]
    for c in rows:
        out.append(f"- {c['sha'][:10]} {c['date']} {c['author']}: {c['subject']}")
        out += [f"  {line}" for line in c["body"].splitlines()]
    reverts = [c for c in rows if c["subject"].startswith("Revert") or "This reverts commit" in c["body"]]
    out += ["", f"## Reverts ({len(reverts)})", ""] + [f"- {c['sha'][:10]} {c['date']}: {c['subject']}" for c in reverts]
    if (repo / "agent" / ".git").exists():
        out += ["", ticket_record(repo / "agent", since, until)]
    return "\n".join(out) + "\n"


def ticket_record(agent: Path, since: datetime, until: datetime | None) -> str:
    """An agent repo's tickets in the period: filed, every status change, deleted (dropped or
    retired, as the commit says), and each worker report as committed."""
    filed, changes, deleted = [], [], []
    for c in reversed(commits(agent, since, "tickets", until=until)):
        diff = git(agent, "show", "--format=", "--no-renames", c["sha"], "--", "tickets")
        for path, before, after, status in file_diffs(diff):
            slug = Path(path).stem
            if status == "added":
                filed.append(f"- {slug} ({c['date']}, {c['subject']}): {after or '?'}")
            elif status == "deleted":
                deleted.append(f"- {slug} ({c['date']}, {c['subject']}): was {before or '?'}")
            elif before != after and (before or after):
                changes.append(f"- {slug} ({c['date']}, {c['subject']}): {before} → {after}")
    reports = []
    for c in reversed(commits(agent, since, "show/*/report.md", until=until)):
        for path in git(agent, "show", "--format=", "--name-only", "--diff-filter=AM", c["sha"], "--", "show/*/report.md").split():
            text = git(agent, "show", f"{c['sha']}:{path}").strip()
            reports.append(f"### {path} ({c['date']}, {c['subject']})\n\n{text}")
    return "\n".join(["## Tickets", "", f"In `{agent}`.", "", f"### Filed ({len(filed)})", "", *filed, "",
                      f"### Status changes ({len(changes)})", "", *changes, "",
                      f"### Deleted ({len(deleted)})", "", *deleted, "",
                      f"## Worker reports ({len(reports)})", "", *reports])


def file_diffs(diff: str) -> Iterable[tuple[str, str, str, str]]:
    """Per file in a diff: its path, the `status:` it had and has, and whether it was added,
    deleted or changed."""
    for part in re.split(r"^diff --git ", diff, flags=re.M)[1:]:
        path = re.search(r"^\+\+\+ (?:b/(.*)|/dev/null)$", part, re.M)
        old = re.search(r"^--- (?:a/(.*)|/dev/null)$", part, re.M)
        name = (path and path.group(1)) or (old and old.group(1)) or ""
        status = "added" if "\nnew file mode" in part else "deleted" if "\ndeleted file mode" in part else "changed"
        before = re.search(r"^-status: *(\S+)", part, re.M)
        after = re.search(r"^\+status: *(\S+)", part, re.M)
        yield name, before.group(1) if before else "", after.group(1) if after else "", status


# ── versions ─────────────────────────────────────────────────────────────────

PLUGIN = "mx/.claude-plugin/plugin.json"


def versions(since: datetime, until: datetime, period: list[Digest], repos: list[Path]) -> str:
    """The mx releases committed in the period, each with its commit, and the Claude Code versions and models that ran in
    it, each with the first and last day it ran on. A day counts when an entry of that day falls in
    the period."""
    out = [f"# Versions since {stamp(since)}", "", "## mx releases", ""]
    for repo in repos:
        if (repo / PLUGIN).exists():
            for c in reversed(commits(repo, since, PLUGIN, until=until)):
                version = json.loads(git(repo, "show", f"{c['sha']}:{PLUGIN}")).get("version", "?")
                out.append(f"- {version} {c['sha'][:10]} ({c['date']}): {c['subject']}")
    for title, attr in (("Claude Code", "versions"), ("Models", "models")):
        ran: dict[str, set[str]] = {}
        sessions: Counter = Counter()
        for d in period:
            for key, days in getattr(d, attr).items():
                inside = {day for day, (first, last) in days.items() if last >= stamp(since) and first <= stamp(until)}
                if inside:
                    ran.setdefault(key, set()).update(inside)
                    sessions[key] += 1
        out += ["", f"## {title}", ""]
        out += [f"- {k}: first seen {min(days)}, last seen {max(days)}, in {sessions[k]} sessions"
                for k, days in sorted(ran.items(), key=lambda kv: min(kv[1]))]
    return "\n".join(out) + "\n"


# ── command line ─────────────────────────────────────────────────────────────


@dataclass
class Sessions:
    """What a workflow retro collects but `touched.md`: the period's session digests, the older sample, git across the repos, the versions, the tickets and the permissions."""

    since: str
    """The period's start, an ISO date or time; UTC where it names no offset."""
    run: Path
    """The run directory, written into; outside every git work tree."""
    repos: list[Path] = field(default_factory=list)
    """The repos whose commits and tickets are collected, and whose agent repos hold session pages."""
    projects: list[Path] = field(default_factory=profiles)
    """Each profile's directory of transcripts; by default every `~/.claude*/projects`."""
    cache: Path | None = None
    """Where digests are cached; by default `digest-cache` beside the run directory."""
    agent: Path | None = None
    """The agent repo whose tickets `proposed.md` and `in-flight.md` name; none by default."""


@dataclass
class Git:
    """The commits and tickets of the given repos since the period's start, alone."""

    since: str
    """The period's start, an ISO date or time; UTC where it names no offset."""
    run: Path
    """The run directory, written into; outside every git work tree."""
    repos: list[Path] = field(default_factory=list)
    """The repos whose commits and tickets are collected."""


def main(command: Sessions | Git) -> None:
    since = parse_time(command.since)
    refuse_unless_git(command.repos)
    if isinstance(command, Git):
        refuse_inside_git(command.run)
        collect_git(since, command.run, command.repos)
        return
    cache = command.cache or command.run.parent / "digest-cache"
    refuse_inside_git(command.run, cache)
    collect_sessions(since, datetime.now(UTC), command.run, cache, command.projects, command.repos, agent=command.agent)
    collect_permissions(since, command.run, command.projects)


if __name__ == "__main__":
    import tyro

    args = tyro.extras.subcommand_cli_from_dict({"sessions": Sessions, "git": Git}, description=__doc__)
    main(args)
