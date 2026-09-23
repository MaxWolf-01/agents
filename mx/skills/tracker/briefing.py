"""The board briefing: the session that writes it, and what a tracker change does to that session.

A fresh `claude -p` session explores the repo and writes where things stand and the next picks; the
board's watcher keeps it current by sending each tracker change to that same session with
`--resume`, debounced, until the session retires and the next change starts a new one. This holds
the cache file the session's state lives in, beside the rendered board, the rule that decides a
change's fate, and the two runs of the model behind it.

The session is given a short prompt of its own rather than the one the user's own sessions carry,
and tools that only read: it runs unattended, on the repo the board is rendered from.
"""

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

DEBOUNCE = timedelta(minutes=5)  # a burst of tracker changes reaches the session as one ping; the spec allows five to ten
# The prompt cache's lifetime, which is what a ping rereads the session's context at: a run of the
# command below reports its input under `cache_creation.ephemeral_1h_input_tokens` and nothing
# under the five-minute one, so it is the hour-long cache this is set against.
IDLE = timedelta(hours=1)
PING_CAP = 20  # pings one session takes before a fresh one explores from scratch: two hours of a tracker changing every window

COMMAND = "claude"
# What the session explores with: reading the repo is the whole of its work. The list is what the
# run allows on top of the machine's own settings, which stand whatever it says, so the three that
# write are named as denied rather than left out.
TOOLS = "Read,Glob,Grep,Bash(git log:*),Bash(git show:*),Bash(git diff:*)"
DENIED = "Write,Edit,NotebookEdit"
# The user's own sessions carry their memory files and hooks; a briefing session is none of their
# conversations, and the repo's own CLAUDE.md is the one thing about it worth reading.
SETTINGS = json.dumps({"autoMemoryEnabled": False, "claudeMdExcludes": [str(Path.home() / ".claude" / "CLAUDE.md")]})
RUN_LIMIT = 900  # seconds a run gets; one that has not answered by then is dropped and the next change tries again
UNCHANGED = "unchanged"  # what a ping answers when what changed leaves the briefing standing

SILENT = ""  # what the last run that answered nothing said, for the page to say once (board.absences)

SYSTEM = """You write the briefing at the head of one person's ticket board, for the tracker of the repo you are in.

Your reader is that person, back after a week away, reading a narrow column beside their tickets. Write markdown, under 150 words, opening with the words themselves rather than a title:

- Two or three sentences on where things stand, in plain words.
- Then `## next` and three picks, one line each: the ticket, and why it is a pick. Say which of them can run at the same time, in those words, so dispatching a wave is one decision.

The tracker's state is given to you below. Read the repo for what it cannot say: the commits, the code, the specs, a ticket's own file. What earns a sentence is what someone who has only read the board would not know."""

CHANGED = """The tracker has changed since you wrote the briefing:

{note}

Look at whatever this makes you want to look at, then answer with the whole briefing again: the sentences, then `## next` and the three picks, as before. Answer with the single word `unchanged` where what happened leaves your briefing standing."""


@dataclass(frozen=True)
class Briefing:
    """The cache file beside the board: the briefing, and the session that wrote it."""

    text: str
    written: datetime
    session: str  # the Claude Code session id, what `--resume` takes
    started: datetime
    last_activity: datetime
    pings: int

    TIMES = ("written", "started", "last_activity")  # the fields the file holds as ISO strings

    def write(self, path: Path) -> None:
        """In one move: the session writes this from a thread of its own while the board renders
        from it, and half a file is a board with no briefing on it."""
        path.parent.mkdir(parents=True, exist_ok=True)
        held = {k: v.isoformat() if k in self.TIMES else v for k, v in asdict(self).items()}
        written = path.with_suffix(".writing")
        written.write_text(json.dumps(held, indent=1))
        written.replace(path)

    @classmethod
    def read(cls, path: Path) -> "Briefing | None":
        """The cached briefing, or None where no briefing stands: none written yet, or a file this
        version cannot read."""
        try:
            held = json.loads(path.read_text())
            return cls(**{k: datetime.fromisoformat(v) if k in cls.TIMES else v for k, v in held.items()})
        except (OSError, ValueError, KeyError, TypeError):
            return None


def cache_path(board: Path) -> Path:
    """The cache beside the rendered board, as the stamp file is."""
    return Path(str(board) + ".briefing.json")


def on_change(cached: Briefing | None, changed_at: datetime, now: datetime) -> str:
    """What a tracker change last seen at `changed_at`, read at `now`, does to the session the cache
    file holds:
    "ping" it with a note of what changed, "wait" out the debounce window, or retire it and write a
    "fresh" briefing from a new session. A pure function of the cache file's state, the change's
    time and the clock.

    The session's own last activity is the window's start, so the pings of a tracker changing all
    day are one a window and no more, and the same field, an hour untouched, is what retires it.

    A change the session already has is what a retired session is read against first: retirement is
    the next change's business, and a board watching a tracker that has not moved since the morning
    would otherwise explore it again on the hour, all night, for the same change."""
    if cached is not None and cached.last_activity >= changed_at:
        return "wait"  # this change reached it already, in the note of an earlier one
    if cached is None or retired(cached, now):
        return "fresh"
    return "wait" if now - cached.last_activity < DEBOUNCE else "ping"


def retired(cached: Briefing, now: datetime) -> bool:
    """Whether the session the cache file names is past what it is given: an hour of quiet, which
    is the prompt cache's lifetime, or the pings one session takes."""
    return now - cached.last_activity >= IDLE or cached.pings >= PING_CAP


# ---- the runs of the model ------------------------------------------------


def available() -> bool:
    """Whether this machine has the model the briefing is written by."""
    return bool(shutil.which(COMMAND))


def first(state: str, repo: Path, now: datetime) -> Briefing | None:
    """The briefing a fresh session writes from the tracker's state, exploring `repo` from there,
    or None where the model did not answer.

    `now` is the moment the run starts, not the moment it answers: the session's last activity is
    what a change is read as told or untold against (on_change), and a change arriving while the
    repo is being explored is one the session has not heard."""
    answer = ask(["--system-prompt", SYSTEM, "-p", state], repo)
    if not answer or not answer["result"].strip():
        return None
    return Briefing(answer["result"].strip(), now, answer["session_id"], now, now, 0)


def ping(cached: Briefing, note: str, repo: Path, now: datetime) -> Briefing | None:
    """The cache after the session that wrote the briefing is told what changed: its own rewrite, or
    the briefing it left standing, and either way one more ping against its retirement."""
    answer = ask(["--resume", cached.session, "-p", CHANGED.format(note=note)], repo)
    if not answer:
        return None
    said = answer["result"].strip()
    # the word as the prompt writes it, which is in backticks: an answer that keeps them, or ends
    # the sentence, is the same answer, and taking it for a briefing would put it in the column
    stands = not said or said.strip("`*. ").lower() == UNCHANGED
    return replace(
        cached,
        text=cached.text if stands else said,
        written=cached.written if stands else now,  # the time the briefing was written, not the time it was looked at
        session=answer["session_id"],
        last_activity=now,
        pings=cached.pings + 1,
    )


def ask(args: list[str], repo: Path) -> dict | None:
    """One `claude -p` run in `repo`: what it answered and the session it answered in, or None where
    it did not answer at all.

    The board renders without the model, so every way this comes back empty is one the caller goes
    on from: no claude on the machine, no auth, no network, a run past RUN_LIMIT, an error. Each of
    them is kept for the page to say once, in the words the run itself used, since a login that has
    lapsed is a different thing to fix from a machine that never had the model."""
    global SILENT
    if not available():
        return None
    try:
        done = subprocess.run(
            [COMMAND, *args, "--output-format", "json", "--allowedTools", TOOLS, "--disallowedTools", DENIED,
             "--settings", SETTINGS],
            cwd=repo, capture_output=True, text=True, timeout=RUN_LIMIT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        quiet(str(e))
        return None
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        answer = None
    if not isinstance(answer, dict) or answer.get("is_error") or not answer.get("session_id"):
        said = (answer or {}).get("result") or next((line for line in done.stderr.splitlines() if line.strip()), "")
        quiet(str(said) or "it answered nothing")
        return None
    SILENT = ""
    return answer | {"result": str(answer.get("result", ""))}


def quiet(said: str) -> None:
    """A run that came back with no briefing: the board carries on with the briefing it has, or with
    its own count, and what went wrong is on the watcher's own output and on the page (missing)."""
    global SILENT
    SILENT = f"The briefing session answered nothing ({said.strip()[:120]}), so the briefing is the board's own count."
    print(f"{COMMAND}: {said.strip()[:200]}", file=sys.stderr)


def missing() -> str:
    """Why this machine has written no briefing, in the words the page says once, or empty where the
    model is here and the last run of it answered."""
    if not available():
        return f"No {COMMAND} on this machine, so the briefing is the board's own count rather than a model's reading."
    return SILENT
