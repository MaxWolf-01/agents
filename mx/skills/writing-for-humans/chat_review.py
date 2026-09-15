#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Stop hook: a fresh small model reads the turn's final message against the chat-scoped rules
of CATALOGUE.md beside this file, and hands the hits back as feedback, so the turn continues
with a corrected reply.

Reads the Stop hook JSON on stdin and selects the rules tagged `chat` or `both`, the selection
CATALOGUE.md's header states. Fails open: a reviewer that errors, times out or answers in
something other than JSON allows the turn. Every decision is one JSON line in the log, the
skipped turns included, so a hook that never ran reads differently from one switched off.

It skips the model when the message is empty, when the hook is re-entering after its own
feedback, which is what holds the review to once per turn, and in a session nobody reads:
CHAT_REVIEW_OFF set, or DISPATCH_WORKLOG set, which marks a dispatched worker whose chat has
no reader.

Env: CHAT_REVIEW_OFF (any value turns the hook off), CHAT_REVIEW_MODEL (default haiku),
CHAT_REVIEW_LOG (default ~/.cache/chat-review/log.jsonl).
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CATALOGUE = Path(__file__).resolve().parent / "CATALOGUE.md"
LOG = Path(os.environ.get("CHAT_REVIEW_LOG", Path.home() / ".cache/chat-review/log.jsonl"))
MODEL = os.environ.get("CHAT_REVIEW_MODEL", "haiku")
REVIEWER_TIMEOUT_S = 45

PROMPT = """You are a prose editor. Review one chat message, written by a coding agent to its user, against the rules below.

Report only hits a careful human editor would flag, each quoted verbatim from the message. When in doubt, no hit. Code blocks, file paths, commands, identifiers, tables and quoted tool output are not prose: never flag them.

Answer with one JSON object and nothing else:
{"hits": [{"rule": "<rule id>", "quote": "<verbatim excerpt>", "fix": "<the rewrite, in a few words>"}]}
No hits: {"hits": []}

# Rules

<<RULES>>

# Message

<<MESSAGE>>
"""


def chat_rules(catalogue: str) -> str:
    """The catalogue's rule blocks tagged `chat` or `both`, whole, headings dropped.

    An empty selection is a broken catalogue, not a clean reviewer: it would let every reply
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


def hits_from(answer: str) -> list[dict]:
    """The hits out of a reviewer's answer, which may wrap its JSON object in prose.

    Anything shaped unlike a hit is dropped rather than formatted: the caller is past the
    point where an exception would fail open.
    """
    match = re.search(r"\{.*\}", answer, re.S)
    if not match:
        raise RuntimeError(f"no JSON in reviewer output: {answer[:300]}")
    hits = json.loads(match.group(0)).get("hits")
    return [h for h in hits if isinstance(h, dict)] if isinstance(hits, list) else []


def log(**entry: object) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}) + "\n")


def review(message: str) -> list[dict]:
    rules = chat_rules(CATALOGUE.read_text())
    prompt = PROMPT.replace("<<RULES>>", rules).replace("<<MESSAGE>>", message)
    env = {**os.environ, "CHAT_REVIEW_NESTED": "1"}
    # No settings, plugins, hooks or MCP servers: a bare reviewer starts in ~2s, and this hook
    # cannot recurse into itself. Thinking off: with it on, Haiku spends ~14k output tokens and
    # two minutes on a 300-token answer.
    proc = subprocess.run(
        ["claude", "-p", "--tools", "", "--no-session-persistence", "--setting-sources", "",
         "--strict-mcp-config", "--settings", '{"alwaysThinkingEnabled": false}',
         "--model", MODEL, "--output-format", "json", prompt],
        capture_output=True, text=True, timeout=REVIEWER_TIMEOUT_S, env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    out = json.loads(proc.stdout)
    final = next(m for m in out if m.get("type") == "result") if isinstance(out, list) else out
    return hits_from(final["result"])


def main() -> None:
    # CHAT_REVIEW_NESTED marks the reviewer's own session, which loads no plugin and so should
    # never reach this hook; it is what keeps a mistake there from recursing.
    if os.environ.get("CHAT_REVIEW_NESTED"):
        return
    if os.environ.get("CHAT_REVIEW_OFF"):
        log(decision="skip", why="off")
        return
    if os.environ.get("DISPATCH_WORKLOG"):
        log(decision="skip", why="dispatched worker")
        return
    hook = json.load(sys.stdin)
    message = (hook.get("last_assistant_message") or "").strip()
    if hook.get("stop_hook_active") or not message:
        log(decision="allow", why="re-entry" if hook.get("stop_hook_active") else "empty")
        return
    t0 = time.monotonic()
    try:
        hits = review(message)
    except Exception as e:  # noqa: BLE001  fail open: a broken reviewer never holds up the user
        log(decision="allow", why=f"reviewer failed: {e}", ms=int((time.monotonic() - t0) * 1000), message=message)
        return
    ms = int((time.monotonic() - t0) * 1000)
    if not hits:
        log(decision="allow", why="clean", ms=ms, message=message)
        return
    log(decision="feedback", hits=hits, ms=ms, message=message)
    lines = "\n".join(f'- rule {h.get("rule")}: "{h.get("quote")}" becomes: {h.get("fix")}' for h in hits)
    feedback = (
        "A prose reviewer read your last message against the chat rules and found these tells. "
        "Rewrite the message with the same content and the hits fixed, then stop.\n" + lines
    )
    # additionalContext continues the turn like a block decision but shows in the transcript as
    # "Stop hook feedback" rather than as a hook error.
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": feedback}}))


if __name__ == "__main__":
    main()
