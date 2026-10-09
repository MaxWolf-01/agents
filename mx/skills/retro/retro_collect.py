#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown-it-py"]
# ///
"""Gather what a workflow retro reads, for the period since a given start, into a run directory.

`sessions` writes, into the run directory:

- `sessions/<id>.md`: a digest of every interactive session with an entry in the period, from
  every Claude Code profile given, holding the period's days alone. A digest keeps the user's
  messages verbatim, pasted text clipped; every tool call's input, error and denial in full; the
  model's text; and the session page's turn records. It keeps no tool output. Beside them it
  marks interrupts, rewinds, messages queued while the agent worked, hook send-backs, context
  compactions and how long each turn took.
- `sample/<id>.md`: digests of about 20 older sessions, from two to eight weeks before the end
  of the period, drawn at random, weighted to sessions with more of the user's messages.
- `sessions.jsonl`: one row per digest above: id, profile, project, start, end, the user's
  messages, and which of the two it is in.
- `git/<repo>.md` and `versions.md`, as `git` writes them.

`git` writes `git/<repo>.md` alone, for each repo given: its commits in the period with their
messages, its reverts, and, where the repo holds an agent repo, the tickets filed, every status
change, the tickets deleted, and the worker reports committed in the period.

A session whose working directory matches a pattern of the exclude file, which `sessions` cannot
run without, is never digested. Digests are
cached per session in the cache directory and digested again only once the transcript or its
session page changed. Neither the run directory nor the cache may be inside a git work tree.

Examples:

    retro_collect.py sessions --since 2026-10-05 --run ~/.local/share/retro/runs/2026-10-12 \\
        --exclude-file ~/repos/github/MaxWolf-01/agents/agent/retro/excluded-sessions \\
        --repos ~/repos/github/MaxWolf-01/agents ~/.dotfiles
    retro_collect.py git --since 2026-10-05 --run /tmp/run --repos ~/.dotfiles
"""

from __future__ import annotations

import fnmatch
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
import session_page  # noqa: E402  what counts as the user's own message, as the session page reads it

SAMPLE_SIZE = 20
SAMPLE_WINDOW = (timedelta(weeks=2), timedelta(weeks=8))  # how far before the period's end
PASTE_CLIP = 600  # pasted text in a message of the user's
PROFILES = (Path.home() / ".claude/projects", Path.home() / ".claude-helferline/projects")  # each profile's transcripts
# A denial in a transcript that predates `toolDenialKind`: the harness's own wordings, not a shell's "Permission denied".
DENIAL = re.compile(r"^(Permission to use \S+ has been denied|The user doesn't want to proceed)")
PASTED = re.compile(r"(<pasted_content\b[^>]*>)(.*?)(</pasted_content>)", re.S)


# ── what runs ────────────────────────────────────────────────────────────────


def collect_sessions(since: datetime, until: datetime, run: Path, cache: Path, projects: list[Path],
                     repos: list[Path], exclude: list[str], seed: int | None = None) -> None:
    """Everything a workflow retro's later stages read, written into `run`."""
    refuse_inside_git(run, cache)
    refuse_unless_git(repos)
    oldest = until - SAMPLE_WINDOW[1]
    transcripts = [t for t in find_transcripts(projects, exclude) if t.stat().st_mtime >= min(since, oldest).timestamp()]
    digests = [d for d in digest_all(transcripts, cache, repos, exclude) if d.interactive and d.text]
    period = [d for d in digests if d.end >= since and d.start <= until]
    ids = {d.sid for d in period}
    older = [d for d in digests if d.sid not in ids and until - SAMPLE_WINDOW[1] <= d.start <= until - SAMPLE_WINDOW[0]]
    sample = weighted_sample(older, SAMPLE_SIZE, random.Random(seed))
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
    collect_git(since, run, repos, until)
    (run / "versions.md").write_text(versions(since, until, period, repos))


def collect_git(since: datetime, run: Path, repos: list[Path], until: datetime | None = None) -> None:
    """`git/<repo>.md` for each repo: its commits since `since`, and its agent repo's tickets."""
    refuse_inside_git(run)
    refuse_unless_git(repos)
    (run / "git").mkdir(parents=True, exist_ok=True)
    names = Counter()
    for repo in repos:
        name = repo.resolve().name.lstrip(".")
        names[name] += 1
        if names[name] > 1:
            name = f"{name}-{names[name]}"
        (run / "git" / f"{name}.md").write_text(git_record(repo, since, until))


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


# ── which sessions ───────────────────────────────────────────────────────────


def find_transcripts(projects: list[Path], exclude: list[str]) -> list[Path]:
    """Every session's transcript under the profiles' project directories, less those whose
    project directory, Claude Code's encoding of the directory the session started in, matches an
    exclude pattern: those are never opened."""
    encoded = [e for p in exclude for e in (encode(p), encode(p.rstrip("/")) + "-*")]
    return [t for root in projects if root.is_dir() for t in sorted(root.glob("*/*.jsonl"))
            if not any(fnmatch.fnmatchcase(t.parent.name, e) for e in encoded)]


def encode(pattern: str) -> str:
    """A pattern over a directory, as one over the name Claude Code gives that directory's
    project: every character but a letter, a digit or the pattern's own `*` and `?` becomes `-`.
    The encoding is lossy, so a pattern over a directory also matches its siblings whose names
    extend it (`/a/b-c` for `/a/b`): the error is on the side of reading less."""
    return re.sub(r"[^A-Za-z0-9*?]", "-", pattern)


def excluded(directories: list[str], exclude: list[str]) -> bool:
    """Whether any directory a session worked in is, or is under, one an exclude pattern matches:
    a session can move into an excluded directory after it started outside one."""
    return any(fnmatch.fnmatchcase(d, p) or fnmatch.fnmatchcase(d, p.rstrip("/") + "/*")
               for d in directories for p in exclude)


def weighted_sample(digests: list[Digest], k: int, rng: random.Random) -> list[Digest]:
    """`k` digests drawn without replacement, each with odds proportional to the user's messages
    in it (Efraimidis and Spirakis' keys)."""
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
    directories: list[str] = field(default_factory=list)  # every working directory, in order
    versions: dict[str, dict[str, list[str]]] = field(default_factory=dict)  # Claude Code version: day: [first, last seen]
    models: dict[str, dict[str, list[str]]] = field(default_factory=dict)  # model: day: [first, last seen]
    days: dict[str, int] = field(default_factory=dict)  # each day's heading: where in `text` it starts
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


def digest_all(transcripts: list[Path], cache: Path, repos: list[Path], exclude: list[str]) -> list[Digest]:
    """Each transcript's digest, from the cache where its key still matches, else digested now
    and cached. A session that worked in an excluded directory keeps no text, in the cache either."""
    cache.mkdir(parents=True, exist_ok=True)
    out, todo = [], []
    for t in transcripts:
        records = page_records(t, repos)
        key = cache_key(t, records)
        cached = cache / f"{t.parent.parent.parent.name}-{t.stem}.json"
        if cached.exists() and (hit := json.loads(cached.read_text()))["key"] == key:
            d = Digest.from_json(hit["digest"])
            if d.text and excluded(d.directories, exclude):  # a pattern added since the session was cached
                d.text = ""
                cached.write_text(json.dumps({"key": key, "digest": d.to_json()}))
            out.append(d)
        else:
            todo.append((t, records, key, cached))
    with ProcessPoolExecutor(min(8, os.cpu_count() or 1)) if len(todo) > 4 else _Inline() as pool:
        for (t, records, key, cached), d in zip(todo, pool.map(digest_job, [(t, r) for t, r, _, _ in todo])):
            if d is not None:
                if excluded(d.directories, exclude):
                    d.text = ""
                cached.write_text(json.dumps({"key": key, "digest": d.to_json()}))
                out.append(d)
    return out


class _Inline:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    @staticmethod
    def map(f, items):
        return map(f, items)


def digest_job(args: tuple[Path, list[Path]]) -> Digest | None:
    return digest(*args)


CACHE_FORMAT = 5  # raised when a cached digest's shape changes, so every cached digest is redone


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
            tag = "MAX"
            if parent := e.get("parentUuid"):
                parents[parent] += 1
                if parents[parent] > 1:
                    tag = "MAX REWOUND and re-sent (the agent's turn after the first send was abandoned)"
            if e.get("promptSource") == "queued":
                tag += " (queued while the agent worked)"
            put(at, f"{tag}: {t}")

    interactive = any(e.get("entrypoint") == "cli" for e in entries)
    directories = list(dict.fromkeys(e["cwd"] for e in entries if isinstance(e.get("cwd"), str) and e["cwd"]))
    cwd = directories[0] if directories else ""
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
                  messages=messages, text=text, directories=directories,
                  versions=versions, models=models, days={d: starts[i] for d, i in headings.items()} if interactive else {},
                  page_at=starts[-1] - 1 if interactive else 0)


def said(content: object) -> str:
    """A prompt of the user's as the session page reads it, each pasted block clipped first;
    empty for what Claude Code writes as the user."""
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
    days = record.setdefault(key, {})
    first, last = days.get(at.astimezone(UTC).date().isoformat(), [stamp(at), stamp(at)])
    days[at.astimezone(UTC).date().isoformat()] = [min(first, stamp(at)), max(last, stamp(at))]


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
    """The commits on any local branch committed after `since` (and by `until`), newest first."""
    out = git(repo, "log", "--branches", f"--since={since.isoformat()}", *([f"--until={until.isoformat()}"] if until else []),
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
    agent = repo / "agent"
    if (agent / ".git").exists():
        out += ["", ticket_record(agent, since, until)]
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
                filed.append(f"- {slug} ({c['date']}): {after or '?'} — {c['subject']}")
            elif status == "deleted":
                deleted.append(f"- {slug} ({c['date']}): was {before or '?'} — {c['subject']}")
            elif before != after and (before or after):
                changes.append(f"- {slug} ({c['date']}): {before} → {after} — {c['subject']}")
    reports = []
    for c in reversed(commits(agent, since, "show/*/report.md", until=until)):
        for path in git(agent, "show", "--format=", "--name-only", "--diff-filter=AM", c["sha"], "--", "show/*/report.md").split():
            text = git(agent, "show", f"{c['sha']}:{path}").strip()
            reports.append(f"### {path} ({c['date']}, {c['subject']})\n\n{text}")
    return "\n".join(["## Tickets", "", f"### Filed ({len(filed)})", "", *filed, "",
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
    """The mx releases committed in the period, and the Claude Code versions and models the
    period's sessions ran in the period, each with the first and last day it ran on there. A day
    counts when an entry of that day falls in the period."""
    out = [f"# Versions since {stamp(since)}", "", "## mx releases", ""]
    for repo in repos:
        if (repo / PLUGIN).exists():
            for c in reversed(commits(repo, since, PLUGIN, until=until)):
                version = json.loads(git(repo, "show", f"{c['sha']}:{PLUGIN}")).get("version", "?")
                out.append(f"- {version} ({c['date']}): {c['subject']}")
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


def read_list(path: Path) -> list[str]:
    """A list file's entries, one per line, `#` starting a comment; exits when the file is missing."""
    if not path.is_file():
        sys.exit(f"{path} is missing")
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]


def read_patterns(path: Path) -> list[str]:
    """The exclude file's patterns; exits when it holds none, so a run without its list fails closed."""
    patterns = read_list(path)
    if not patterns:
        sys.exit(f"{path} holds no pattern; a run reads no session without its exclusions")
    return patterns


@dataclass
class Sessions:
    """The period's session digests, the older sample, git across the repos, and the versions."""

    since: str
    """The period's start, an ISO date or time; UTC where it names no offset."""
    run: Path
    """The run directory, written into; outside every git work tree."""
    exclude_file: Path
    """Glob patterns over a session's working directory, one per line, `#` starting a comment; a
    session that worked in a matching directory, or under one, is never digested."""
    repos: list[Path] = field(default_factory=list)
    """The repos whose commits and tickets are collected, and whose agent repos hold session pages."""
    projects: list[Path] = field(default_factory=lambda: list(PROFILES))
    """Each profile's directory of transcripts."""
    cache: Path | None = None
    """Where digests are cached; by default `digest-cache` beside the run directory."""


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
    if isinstance(command, Git):
        collect_git(since, command.run, command.repos)
        return
    collect_sessions(since, datetime.now(UTC), command.run, command.cache or command.run.parent / "digest-cache",
                     command.projects, command.repos, read_patterns(command.exclude_file))


if __name__ == "__main__":
    import tyro

    args = tyro.extras.subcommand_cli_from_dict({"sessions": Sessions, "git": Git}, description=__doc__)
    main(args)
