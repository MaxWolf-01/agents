"""The light review a turn record's prose gets before the session page renders it.

A fresh Opus 5.5 at low effort reads the record the turn wrote against the rules of
../writing-for-humans/CATALOGUE.md tagged `chat` or `both`, the selection that file's header
states, seeing what the page's reader has seen: the earlier records, each after the user's messages
it answered, and the messages this record answers. Tool calls are not on the page, so the reviewer
never sees them. The record's shape, as ../show/SKILL.md gives it to the agent, is exempt as
structure. It answers against a JSON schema; a finding whose quote is not in the record is
dropped, and at most three go back to the agent.

Fails open: a reviewer that errors, times out or answers off the schema finds nothing. Every
review is one JSON line in session_page.LOG, carrying the session id and the record as it was
reviewed.
"""

import contextlib
import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import session_page
from session_page import Session, Turn

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent / "writing-for-humans" / "CATALOGUE.md"
RUN_LOG = HERE.parent / "run-log" / "run-log"  # every model run goes through it, one line each in the run log
MODEL = "claude-opus-5-5"
EFFORT = "low"
# run-log's limit on the model call, and the caller's on run-log, which leaves it time to write its
# line; both under the hook's 60 in ../../hooks/hooks.json, so a slow reviewer fails open
REVIEWER_TIMEOUT_S = 45
WRAPPER_TIMEOUT_S = 55
MOST = 3  # findings handed back per record

SHOW = HERE.parent / "show" / "SKILL.md"  # its turn-record section is the shape the reviewer exempts
SHAPE = "### The turn record"

SYSTEM = """You review the prose of one turn record: the file a coding agent writes as a turn ends, which its user reads rendered on a web page. Review it against the rules below, as a careful human editor would.

The input is the session as the page's reader has read it: each earlier turn as the user's messages inside <user> tags and the agent's record inside <turn> tags, then the user's messages this record answers, then the record under review inside <record> tags. Review the text inside <record> and nothing else; the rest is what the reader already knows.

Report at most three findings, the ones that cost the reader most. Each quotes a short excerpt of the record verbatim, names the rule it breaks by id, and says in a few words what is wrong. When in doubt, leave it out; no findings is a good answer.

# The record's shape

The structure the shape below requires is not prose, so never flag it; code, file paths, commands, identifiers and tables are not prose either. The agent writing the record was given its shape in these words:

{shape}

# Rules

{rules}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "maxItems": MOST,
            "items": {
                "type": "object",
                "properties": {"rule": {"type": "string"}, "quote": {"type": "string"}, "note": {"type": "string"}},
                "required": ["rule", "quote", "note"],
            },
        }
    },
    "required": ["findings"],
}


def feedback_on(session: Session, turn: Turn) -> str:
    """What the agent is sent back with for `turn`'s record: the reviewer's findings that quote
    it, at most MOST, and the text of each rule they cite; empty where none holds. Logged either
    way."""
    record = turn.path.read_text()
    t0 = time.monotonic()
    try:
        rules = chat_rules(CATALOGUE.read_text())
        answer = review(SYSTEM.format(shape=record_shape(SHOW.read_text()), rules=rules), reviewer_input(session, turn))
    except Exception as e:  # noqa: BLE001  fail open: a broken reviewer never holds up the page
        log(session.id, decision="failed", why=str(e), ms=ms_since(t0), record=str(turn.path), text=record)
        return ""
    quoting = [f for f in answer if isinstance(f, dict) and str(f.get("quote") or "").strip() and str(f["quote"]).strip() in record]
    kept = quoting[:MOST]
    log(session.id, decision="feedback" if kept else "clean", findings=kept, dropped=[f for f in answer if f not in quoting],
        ms=ms_since(t0), record=str(turn.path), text=record)
    return feedback(turn, kept, rules_by_id(rules)) if kept else ""


def reviewed_since(session_id: str, when: datetime | None) -> bool:
    """Whether the log has a review of this session after `when`, which is what holds the review to
    once per turn whichever send-back continued it. A line cut short by a concurrent write is
    skipped."""
    if not session_page.LOG.exists():
        return False
    with session_page.LOG.open() as f:
        for line in f:
            if session_id not in line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (entry.get("session_id") == session_id and entry.get("decision") in REVIEWED
                    and (when is None or datetime.fromisoformat(entry["ts"]) > when)):
                return True
    return False


REVIEWED = ("feedback", "clean", "failed")  # the log's decisions a model call was made for


def reviewer_input(session: Session, turn: Turn) -> str:
    """The session up to `turn` as its page shows it, oldest first, with `turn`'s record fenced
    last in <record>."""
    earlier = [t for t in session.turns if t.number < turn.number]
    parts = [block(t) + f"\n<turn>\n{t.path.read_text().strip()}\n</turn>" for t in earlier]
    parts.append(block(turn) + f"\n<record>\n{turn.path.read_text().strip()}\n</record>")
    return "\n\n".join(p.strip() for p in parts)


def block(turn: Turn) -> str:
    return "\n".join(f"<user>\n{m.strip()}\n</user>" for m in turn.messages)


def review(system: str, prompt: str) -> list[dict]:
    """The reviewer's findings on `prompt`, from a bare `claude -p`: no tools, settings, plugins,
    hooks or MCP servers, and `system` in place of Claude Code's own system prompt, under which
    the model answers the text instead of reviewing it."""
    proc = subprocess.run(
        [str(RUN_LOG), "run", "--site", "turn-review", "--json", "--timeout", str(REVIEWER_TIMEOUT_S), "--",
         "claude", "-p", "--tools", "", "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
         "--model", MODEL, "--effort", EFFORT, "--system-prompt", system, "--json-schema", json.dumps(SCHEMA)],
        input=prompt, capture_output=True, text=True, timeout=WRAPPER_TIMEOUT_S,
    )
    if proc.returncode != 0:
        ended = f"ran past {REVIEWER_TIMEOUT_S}s" if proc.returncode == 124 else f"exited {proc.returncode}"
        # run-log prints what a claude that reported no result printed, so its stdout says why
        raise RuntimeError(f"claude {ended}: {(proc.stderr.strip() or proc.stdout.strip())[:300]}")
    final = json.loads(proc.stdout)  # claude's result object, which run-log's --json prints
    answer = (final.get("structured_output") or {}).get("findings")
    if not isinstance(answer, list):
        raise RuntimeError(f"no findings in reviewer output: {proc.stdout[:300]}")
    return answer


def chat_rules(catalogue: str) -> str:
    """The catalogue's rule blocks tagged `chat` or `both`, whole, headings dropped.

    An empty selection is a broken catalogue, not a clean record: it would let every record
    through as though a model had read it, so it raises into the fail-open path instead.
    """
    kept, keep = [], False
    for line in catalogue.splitlines():
        if line.startswith("#"):
            keep = False
        if line.startswith("- `"):
            keep = line.split()[2] in ("`chat`", "`both`")
        if keep:
            kept.append(line)
    if not any(line.strip() for line in kept):
        raise RuntimeError(f"no rule tagged `chat` or `both` in {CATALOGUE}")
    return "\n".join(kept).rstrip("\n")


def record_shape(skill: str) -> str:
    """The section of the show skill under SHAPE, down to the next heading of its level or above;
    a heading inside a fenced block is the example record's own.

    A skill with no such section, or an empty one, raises into the fail-open path, as a catalogue
    with no chat rules does.
    """
    level = SHAPE.split()[0]
    kept: list[str] | None = None
    fence = False
    for line in skill.splitlines():
        if line.startswith("```"):
            fence = not fence
        heading = not fence and re.match(r"#+ ", line)
        if kept is None:
            if line.strip() == SHAPE:
                kept = []
        elif heading and len(heading.group().strip()) <= len(level):
            break
        else:
            kept.append(line)
    if not kept or not "\n".join(kept).strip():
        raise RuntimeError(f"no {SHAPE!r} section in {SHOW}")
    return "\n".join(kept).strip()


def rules_by_id(rules: str) -> dict[str, str]:
    """The selected rule blocks keyed by id, each without its scope tag, which tells a reviewer
    where the rule binds and tells the agent reading the findings nothing."""
    blocks = re.split(r"^(?=- `)", rules, flags=re.M)
    return {
        block.split("`")[1]: re.sub(r"^(- `[^`]+`) `[^`]+`", r"\1", block.strip())
        for block in blocks
        if block.startswith("- `")
    }


def feedback(turn: Turn, found: list[dict], rules: dict[str, str]) -> str:
    """Each finding under the id of the rule it cites, then the text of each cited rule, once."""
    ids = [str(f.get("rule")).strip("` ") for f in found]
    flagged = [f'- rule {i}: "{f["quote"]}"' + (f' ({f["note"]})' if f.get("note") else "") for i, f in zip(ids, found)]
    cited = [rules[i] for i in dict.fromkeys(ids) if i in rules]
    return "\n".join([
        f"A review of {turn.path} against the chat prose rules flagged these passages:",
        *flagged,
        *(["", "The rules they cite:", *cited] if cited else []),
        "",
        "Revise the record where a finding holds and keep it where it does not; the page renders when the turn ends again.",
    ])


def log(session_id: str | None, **entry: object) -> None:
    """Fails open: a log that cannot be written never holds up the turn it describes."""
    with contextlib.suppress(OSError):
        session_page.LOG.parent.mkdir(parents=True, exist_ok=True)
        with session_page.LOG.open("a") as f:
            f.write(json.dumps({"ts": datetime.now(UTC).isoformat(timespec="seconds"), "session_id": session_id, **entry}) + "\n")


def ms_since(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)
