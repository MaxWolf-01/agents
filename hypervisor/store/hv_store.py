#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["tyro"]
# ///
"""The hypervisor's log and view.

Examples:

    hv_store.py --dir DIR init
    echo "an entry" | hv_store.py --dir DIR append
    hv_store.py --dir DIR view --budget 64

`append` takes any text: any length, any number of lines. Entries are numbered from 0 in the order
they were appended. A block LO-HI is an aligned power-of-two range of entries, inclusive at both
ends, as in OptMem (github.com/VictorTaelin/OptMem). A view line starts with its start time, to the
minute in one token, then names what it covers, `#ID` for one entry or `#LO-HI` for a block:

  2026-10-01T14:07 #16-31 <the block's compression>

The trailing newline of a text on stdin ends its last line and is not part of it. An entry holds
one line of at most 512 bytes; a text it cannot hold as it is gets a one-line gist ending in
`[raw: N bytes]`, and `raw` prints the whole text.
"""

import contextlib
import datetime
import fcntl
import importlib.machinery
import importlib.util
import re
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import tyro


def _vendored_memo():
    path = Path(__file__).resolve().parent / "optmem" / "memo"
    loader = importlib.machinery.SourceFileLoader("memo", str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("memo", loader))
    loader.exec_module(module)
    return module


memo = _vendored_memo()

ENTRY = 512  # bytes of text in one entry or one compression
STAMP = "%Y-%m-%dT%H:%M"


def main(argv: list[str]) -> int:
    """Run one command: its output goes to stdout, and the exit status is returned. The property
    checks call this in-process, many times in one process, so nothing may carry over between calls."""
    args = tyro.cli(Cli, args=argv, description=__doc__, config=(tyro.conf.OmitArgPrefixes,))
    try:
        if not isinstance(args.command, Init) and not Path(memo.log_path(args.dir)).is_file():
            raise Refused(f"No store at {args.dir}. `init` creates one.")
        COMMANDS[type(args.command)](args.dir, args.command)
    except Refused as refusal:
        print(refusal, file=sys.stderr)
        return 1
    except OSError as error:
        print(f"{error.filename or args.dir}: {error.strerror or error}", file=sys.stderr)
        return 1
    return 0


class Refused(Exception):
    """A command that did nothing, and the message saying why."""


# ---------------------------------------------------------------- the command line


@dataclass
class Init:
    """Create the store, or leave the one there as it is."""


@dataclass
class Append:
    """Log the text on stdin as one entry, stamped with the current minute, and print its number."""


@dataclass
class Import:
    """Log each `STAMP TEXT` line on stdin as one entry. STAMP is YYYY-MM-DDTHH:MM, or a date
    YYYY-MM-DD stamped at 00:00; no stamp may precede the one before it."""


@dataclass
class View:
    """Print a header line with the current time and the time since the last entry, then the view.
    Refused while a compression the view needs is not written yet."""

    budget: int = 256
    """The most view lines to print."""


@dataclass
class Zoom:
    """Print a block's two halves as view lines, leaving out a half not logged yet."""

    block: Annotated[str, tyro.conf.Positional]
    """LO-HI, inclusive at both ends."""


@dataclass
class Recall:
    """Print the entries whose view line or whole text matches, newest last, ignoring case."""

    regex: Annotated[str, tyro.conf.Positional]
    """A Python regular expression."""


@dataclass
class Raw:
    """Print the whole text of one entry."""

    id: Annotated[int, tyro.conf.Positional]
    """The entry's number."""


@dataclass
class Due:
    """Print the compressions ready to write, one LO-HI per line. They may be written in any order."""


@dataclass
class Compress:
    """Write the line on stdin, at most 512 bytes, as the compression of a block `due` lists."""

    block: Annotated[str, tyro.conf.Positional]
    """LO-HI, inclusive at both ends."""


def _named(cls: type, name: str):
    return Annotated[cls, tyro.conf.subcommand(name=name, prefix_name=False)]


Command = (
    _named(Init, "init")
    | _named(Append, "append")
    | _named(Import, "import")
    | _named(View, "view")
    | _named(Zoom, "zoom")
    | _named(Recall, "recall")
    | _named(Raw, "raw")
    | _named(Due, "due")
    | _named(Compress, "compress")
)


@dataclass
class Cli:
    dir: Path
    """The store's directory."""
    command: Command


# ---------------------------------------------------------------- the commands


def init(d: Path, _: Init) -> None:
    fresh = not d.exists()
    for sub in ("TREE", "RAW"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    open(memo.log_path(d), "a").close()
    print(f"Created {d}." if fresh else f"Found {d}: {memo.log_len(d)} entries.")


def append(d: Path, _: Append) -> None:
    text, whole = as_entry(stdin())
    print(f"#{log(d, [(now().strftime(STAMP), text, whole)])}")


def import_(d: Path, _: Import) -> None:
    last = memo.log_get(d, memo.log_len(d) - 1)[1] if memo.log_len(d) else ""
    items = []
    for n, line in enumerate(stdin().split("\n"), 1):
        if not line.strip():
            continue
        stamp, _, text = line.partition(" ")
        stamp = stamp + "T00:00" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp) else stamp
        try:
            datetime.datetime.strptime(stamp, STAMP)
        except ValueError:
            raise Refused(f"line {n}: expected `YYYY-MM-DD[THH:MM] TEXT`, got: {line}") from None
        if stamp < last:
            raise Refused(f"line {n}: {stamp} precedes the entry before it, stamped {last}.")
        if not text.strip():
            raise Refused(f"line {n}: no text after the stamp.")
        items.append((stamp, *as_entry(text.strip())))
        last = stamp
    if not items:
        raise Refused("No entries on stdin.")
    first = log(d, items)
    print(f"Imported {len(items)} entries, #{first} to #{first + len(items) - 1}.")


def view(d: Path, cmd: View) -> None:
    T = memo.log_len(d)
    if cmd.budget < 1:
        raise Refused("The budget is at least one line.")
    blocks = memo.cover(T, cmd.budget)
    if len(blocks) > cmd.budget:
        raise Refused(f"{T} entries take at least {len(blocks)} lines, over the budget of {cmd.budget}.")
    missing = [f"{lo}-{hi - 1}" for lo, hi in blocks if hi - lo > 1 and memo.tree_get(d, lo, hi) is None]
    if missing:
        raise Refused(f"The view needs compressions not written yet: {' '.join(missing)}. `due` lists what can be written.")
    print(header(d, T, now()))
    for lo, hi in blocks:
        print(line(d, lo, hi))


def zoom(d: Path, cmd: Zoom) -> None:
    lo, hi = block(cmd.block)
    T = memo.log_len(d)
    if lo >= T:
        raise Refused(f"#{lo} is not logged yet: the log holds {T} entries.")
    mid = (lo + hi) // 2
    for a, b in ((lo, mid), (mid, hi)):
        if a < T:
            print(line(d, a, b))


def recall(d: Path, cmd: Recall) -> None:
    try:
        pattern = re.compile(cmd.regex, re.I)
    except re.error as error:
        raise Refused(f"Bad regex: {error}") from None
    kept = sidecars(d)
    # Only the newest matches that fit one harness's output are held: a vague regex matches the whole log.
    hits, out, size = 0, deque(), 0
    for i, stamp, text in memo.log_scan(d):
        found = f"{stamp} #{i} {text}"
        if not (pattern.search(found) or (i in kept and pattern.search(whole_text(d, i)))):
            continue
        hits += 1
        out.append(found)
        size += len(found.encode()) + 1
        while size > memo.PART_CHARS:
            size -= len(out.popleft().encode()) + 1
    for found in out:
        print(found)
    if len(out) < hits:
        print(f"(the newest {len(out)} of {hits} matches; narrow the regex)")


def raw(d: Path, cmd: Raw) -> None:
    if not 0 <= cmd.id < memo.log_len(d):
        raise Refused(f"No entry #{cmd.id}: the log holds {memo.log_len(d)} entries.")
    print(whole_text(d, cmd.id))


def due(d: Path, _: Due) -> None:
    for lo, hi in ready(d):
        print(f"{lo}-{hi - 1}")


def compress(d: Path, cmd: Compress) -> None:
    lo, hi = block(cmd.block)
    text = stdin().strip()
    if len(text.splitlines()) != 1:
        raise Refused("A compression is one line of text.")
    if len(text.encode()) > ENTRY:
        raise Refused(f"Too long: {len(text.encode())} bytes, limit {ENTRY}.")
    if (lo, hi) not in ready(d):
        if memo.tree_get(d, lo, hi) is not None:
            raise Refused(f"{cmd.block} is already written.")
        if hi > memo.log_len(d):
            raise Refused(f"{cmd.block} is not all logged yet: the log holds {memo.log_len(d)} entries.")
        raise Refused(f"{cmd.block} is not due yet. `due` lists what can be written.")
    if not memo.tree_put(d, lo, hi, text):
        raise Refused(f"{cmd.block} was written meanwhile.")


COMMANDS = {
    Init: init,
    Append: append,
    Import: import_,
    View: view,
    Zoom: zoom,
    Recall: recall,
    Raw: raw,
    Due: due,
    Compress: compress,
}


# ---------------------------------------------------------------- entries


def as_entry(text: str) -> tuple[str, str | None]:
    """The text an entry holds, and the whole text when the entry cannot hold it as it is: one line,
    no surrounding whitespace (a record drops it), at most ENTRY bytes."""
    if text and text == text.strip() and len(text.splitlines()) == 1 and len(text.encode()) <= ENTRY:
        return text, None
    note = f" [raw: {len(text.encode())} bytes]"
    return (clip(" ".join(text.split()), ENTRY - len(note)) + note).strip(), text


def clip(text: str, limit: int) -> str:
    b = text.encode()
    if len(b) <= limit:
        return text
    return b[: limit - len("…".encode())].decode(errors="ignore").rstrip() + "…"


def log(d: Path, items: list[tuple[str, str, str | None]]) -> int:
    """Append (stamp, text, whole) entries and return the first one's number. A whole text lands in
    RAW/<number> before its entry is logged, so a reader never sees the entry without it."""
    with locked(d):
        first = memo.log_len(d)
        for i, (_, _, whole) in enumerate(items, first):
            side = d / "RAW" / str(i)
            if whole is None:
                # Left by a run that died between its sidecar and its entry.
                side.unlink(missing_ok=True)
            else:
                (staged := side.with_suffix(".new")).write_bytes(whole.encode())
                staged.replace(side)
        assert memo.log_append(d, [(stamp, text) for stamp, text, _ in items]) == first
    return first


@contextlib.contextmanager
def locked(d: Path):
    """The store's own lock, around memo's: an entry's number is fixed before memo takes its lock."""
    with open(d / ".hv.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def sidecars(d: Path) -> set[int]:
    return {int(p.name) for p in (d / "RAW").iterdir() if p.name.isdigit()}


def whole_text(d: Path, i: int) -> str:
    side = d / "RAW" / str(i)
    return side.read_bytes().decode() if side.exists() else memo.log_get(d, i)[2]


def stdin() -> str:
    try:
        return sys.stdin.buffer.read().decode().removesuffix("\n")
    except UnicodeDecodeError:
        raise Refused("The text on stdin is not UTF-8.") from None


def now() -> datetime.datetime:
    return datetime.datetime.now()


# ---------------------------------------------------------------- the view


def line(d: Path, lo: int, hi: int) -> str:
    """The view line of entry `lo`, or of block [lo, hi)."""
    if hi - lo == 1:
        i, stamp, text = memo.log_get(d, lo)
        return f"{stamp} #{i} {text}"
    text = memo.tree_get(d, lo, hi) if hi <= memo.log_len(d) else None
    return f"{memo.log_get(d, lo)[1]} #{lo}-{hi - 1} {text or '(not compressed yet)'}"


def header(d: Path, T: int, at: datetime.datetime) -> str:
    head = f"now {at.strftime(STAMP)} ({at:%a})"
    if not T:
        return f"{head}, the log is empty"
    last = datetime.datetime.strptime(memo.log_get(d, T - 1)[1], STAMP)
    minutes = int((at.replace(second=0, microsecond=0) - last).total_seconds() // 60)
    if minutes < 0:
        return f"{head}, the last entry, #{T - 1}, is stamped {span(-minutes)} later"
    return f"{head}, {span(minutes)} since the last entry, #{T - 1}"


def span(minutes: int) -> str:
    """A duration in its largest unit and the one below it: `3 weeks 2 days`, `5 hours`."""
    counts = []
    for name, size in (("week", 7 * 24 * 60), ("day", 24 * 60), ("hour", 60), ("minute", 1)):
        n, minutes = divmod(minutes, size)
        counts.append((n, name))
    lead = next((k for k, (n, _) in enumerate(counts) if n), None)
    if lead is None:
        return "0 minutes"
    return " ".join(f"{n} {name}" + "s" * (n != 1) for n, name in counts[lead : lead + 2] if n)


def block(text: str) -> tuple[int, int]:
    """Parse LO-HI, inclusive at both ends, into [lo, hi), refusing a range that is not a block."""
    m = re.fullmatch(r"([0-9]+)-([0-9]+)", text)
    lo, hi = (int(m[1]), int(m[2]) + 1) if m else (0, 0)
    n = hi - lo
    if n < 2 or n & (n - 1) or lo % n:
        raise Refused(f"{text} is not a block: an aligned power-of-two range LO-HI, like 16-31.")
    return lo, hi


def ready(d: Path) -> list[tuple[int, int]]:
    """Per level, the next block to write, once all its entries are logged and its inputs written:
    the entries themselves for a block of up to RAW_MAX, its two halves above that. memo writes a
    level in order, so this is what can be written in any order."""
    T, out, size = memo.log_len(d), [], 2
    while size <= T:
        lo = memo.count(memo.tree_path(d, size), memo.TREE_REC) * size
        hi, mid = lo + size, lo + size // 2
        if hi <= T and (size <= memo.RAW_MAX or (memo.tree_get(d, lo, mid) and memo.tree_get(d, mid, hi))):
            out.append((lo, hi))
        size *= 2
    return out


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
