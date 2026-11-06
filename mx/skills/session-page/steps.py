"""The steps a turn takes on the way to what it delivers, and each as the page's log shows it: its
icon's kind, the words its line opens with, what it acted on, its request and result whole.

The page's log reads them from the transcript once a turn ends (`steps_of`); the live hook builds
them from hook events while the turn runs (`live_hook.py`). Only the standard library, since the
live hook imports this on every tool call.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Step:
    """One thing a turn did on the way to what it delivered: a tool call with its result, or a
    thinking block that kept its text. Claude Code stores thinking redacted, so few blocks do."""

    at: datetime
    tool: str  # the tool's name; empty for thinking
    input: dict = field(default_factory=dict)
    output: str = ""  # the call's result as text, or the thinking's text
    failed: bool = False  # the result is an error
    done: datetime | None = None  # when the result came back; None for thinking, or a call with no result yet


def steps_of(entries: list[dict]) -> list[Step]:
    """Every tool call and every thinking block with text, oldest first, each call with its result.
    A subagent's own steps are its transcript's, not this one's."""
    results: dict[str, tuple[datetime, str, bool]] = {}
    for entry in entries:
        content = (entry.get("message") or {}).get("content")
        if entry.get("type") == "user" and isinstance(content, list) and "timestamp" in entry:
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    results[str(b.get("tool_use_id"))] = (datetime.fromisoformat(entry["timestamp"]), result_text(b.get("content")), bool(b.get("is_error")))
    steps = []
    for entry in entries:
        content = (entry.get("message") or {}).get("content")
        if entry.get("type") != "assistant" or entry.get("isSidechain") or not isinstance(content, list) or "timestamp" not in entry:
            continue
        at = datetime.fromisoformat(entry["timestamp"])
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "thinking" and str(b.get("thinking") or "").strip():
                steps.append(Step(at, "", output=b["thinking"]))
            elif b.get("type") == "tool_use":
                done, output, failed = results.get(str(b.get("id")), (None, "", False))
                steps.append(Step(at, str(b.get("name", "")), b.get("input") if isinstance(b.get("input"), dict) else {}, output, failed, done))
    return sorted(steps, key=lambda s: s.at)


@dataclass(frozen=True)
class Spent:
    """What a turn, or one piece of it, consumed and produced, as the model sees it: it consumes a
    prompt and a tool's result, and produces its text, its thinking and a tool's request. The
    tokens are the API's own count, the bytes the UTF-8 size of the text."""

    at: datetime
    consumed_tokens: int = 0  # every input token a request was billed for, the cached ones included
    produced_tokens: int = 0
    consumed_bytes: int = 0
    produced_bytes: int = 0

    def __add__(self, other: "Spent") -> "Spent":
        return Spent(min(self.at, other.at), self.consumed_tokens + other.consumed_tokens, self.produced_tokens + other.produced_tokens,
                     self.consumed_bytes + other.consumed_bytes, self.produced_bytes + other.produced_bytes)


def spent_of(entries: list[dict]) -> list[Spent]:
    """What each entry of the main transcript consumed and produced, oldest first: a user entry's
    bytes, an assistant entry's bytes, and each reply's tokens once. Claude Code writes each block
    of one reply as an entry of its own, each repeating the reply's usage as it stood then, so the
    reply's last entry holds its count."""
    out, usage = [], {}
    for entry in entries:
        message, at = entry.get("message") or {}, entry.get("timestamp")
        if entry.get("isSidechain") or at is None or not isinstance(message, dict):
            continue
        at = datetime.fromisoformat(at)
        content = message.get("content")
        blocks = content if isinstance(content, list) else [{"type": "text", "text": content}] if isinstance(content, str) else []
        size = sum(len(block_text(b).encode()) for b in blocks if isinstance(b, dict))
        if entry.get("type") == "user":
            out.append(Spent(at, consumed_bytes=size))
        elif entry.get("type") == "assistant":
            out.append(Spent(at, produced_bytes=size))
            if isinstance(message.get("usage"), dict):
                reply = message.get("id") or id(entry)
                usage[reply] = (usage.get(reply, (at,))[0], message["usage"])
    for at, u in usage.values():
        count = lambda key: u.get(key) if isinstance(u.get(key), int) else 0
        out.append(Spent(at, consumed_tokens=count("input_tokens") + count("cache_creation_input_tokens") + count("cache_read_input_tokens"),
                         produced_tokens=count("output_tokens")))
    return sorted(out, key=lambda s: s.at)


def block_text(block: dict) -> str:
    """A message block's text as the model reads or writes it: a tool's request as compact JSON."""
    kind = block.get("type")
    if kind == "tool_use":
        return request_text(block.get("input"))
    if kind == "tool_result":
        return result_text(block.get("content"))
    return str(block.get("text") or block.get("thinking") or "") if kind in ("text", "thinking") else ""


def request_text(request: object) -> str:
    """A tool's request as the log sizes it, the same JSON the page's `JSON.stringify` writes."""
    return json.dumps(request if request is not None else {}, ensure_ascii=False, separators=(",", ":"))


def result_text(content: object) -> str:
    """A tool result as text: its text blocks, and a line standing in for each image."""
    if not isinstance(content, list):
        return content if isinstance(content, str) else ""
    return "\n".join(b.get("text", "") if b.get("type") == "text" else f"[{b.get('type')}]" for b in content if isinstance(b, dict))


# The words a step's line opens with, by its tool, and the input field it names what it acted on by.
SUMMARIES = {
    "Bash": ("ran", ("description", "command")),
    "Read": ("read", ("file_path",)),
    "Write": ("wrote", ("file_path",)),
    "Edit": ("edited", ("file_path",)),
    "MultiEdit": ("edited", ("file_path",)),
    "NotebookEdit": ("edited", ("notebook_path",)),
    "Agent": ("subagent", ("description", "prompt")),
    "Task": ("subagent", ("description", "prompt")),
    "Skill": ("skill", ("skill",)),
    "Grep": ("searched", ("pattern",)),
    "Glob": ("listed", ("pattern",)),
    "WebSearch": ("searched the web", ("query",)),
    "WebFetch": ("fetched", ("url",)),
    "ToolSearch": ("tools", ("query",)),
}
# What kind of step a tool's call is, which picks the icon its line shows.
KINDS = {"Bash": "command", "Read": "read", "Grep": "read", "Glob": "read", "Write": "write", "Edit": "write",
         "MultiEdit": "write", "NotebookEdit": "write", "Agent": "subagent", "Task": "subagent", "WebSearch": "web", "WebFetch": "web"}


def summary(step: Step) -> tuple[str, str]:
    """A step's line: the words it opens with, and the first line of what it acted on."""
    if not step.tool:
        return "thought", step.output.strip().splitlines()[0]
    verb, fields = SUMMARIES.get(step.tool, (step.tool.removeprefix("mcp__").split("__")[-1], ()))
    values = [step.input.get(f) for f in fields] or list(step.input.values())
    subject = next((str(v) for v in values if isinstance(v, (str, int, float)) and str(v).strip()), "")
    return verb, subject.strip().splitlines()[0] if subject.strip() else ""


def shown(step: Step) -> dict:
    """A step as the page's log reads it."""
    verb, subject = summary(step)
    return {"kind": KINDS.get(step.tool, "other") if step.tool else "thinking", "tool": step.tool, "verb": verb,
            "subject": subject, "input": step.input, "output": step.output, "failed": step.failed,
            "at": step.at.isoformat(), "done": step.done.isoformat() if step.done else None}
