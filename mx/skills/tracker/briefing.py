"""The board briefing: the session that writes it, and what a tracker change does to that session.

A fresh `claude -p` session explores the repo and writes where things stand and the next picks; the
board's watcher keeps it current by sending each tracker change to that same session with
`--resume`, debounced, until the session retires and the next change starts a new one. This holds
the cache file the session's state lives in, beside the rendered board, and the rule that decides a
change's fate.

The rule is a stub: test_briefing.py holds the property it has to satisfy, and 09-briefing fills it
in against agent/tickets/board-orients/spec.md.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

DEBOUNCE = timedelta(minutes=5)  # a burst of tracker changes reaches the session as one ping; the spec allows five to ten
IDLE = timedelta(hours=1)  # a session idle this long is retired; 09 confirms it against the prompt cache's lifetime
PING_CAP = 20  # pings one session takes before it is retired, whatever the clock says; the spec gives no number, so 09 confirms it


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
        path.parent.mkdir(parents=True, exist_ok=True)
        held = {k: v.isoformat() if k in self.TIMES else v for k, v in asdict(self).items()}
        path.write_text(json.dumps(held, indent=1))

    @classmethod
    def read(cls, path: Path) -> "Briefing | None":
        """The cached briefing, or None where no briefing has been written yet."""
        if not path.exists():
            return None
        held = json.loads(path.read_text())
        return cls(**{k: datetime.fromisoformat(v) if k in cls.TIMES else v for k, v in held.items()})


def cache_path(board: Path) -> Path:
    """The cache beside the rendered board, as the stamp file is."""
    return Path(str(board) + ".briefing.json")


def on_change(cached: Briefing | None, changed_at: datetime, now: datetime) -> str:
    """What a tracker change last seen at `changed_at`, read at `now`, does to the session the cache
    file holds:
    "ping" it with a note of what changed, "wait" out the debounce window, or retire it and write a
    "fresh" briefing from a new session. A pure function of the cache file's state, the change's
    time and the clock. Lifted by 09-briefing."""
    raise NotImplementedError
