#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Stop hook: a fresh small model reads the turn's final message against the chat-scoped rules
of CATALOGUE.md beside this file and hands its hits back as feedback: each hit quotes a passage,
names what is wrong with it and cites a rule, and the text of each cited rule the session has not
been shown yet comes along. The turn continues, and the session decides which hits to act on as
it revises the reply.

Reads the Stop hook JSON on stdin and selects the rules tagged `chat` or `both`, the selection
CATALOGUE.md's header states. Fails open: a reviewer that errors, times out or answers in
something other than JSON allows the turn. Every decision is one JSON line in the log, carrying
the session id, the skipped turns included, so a hook that never ran reads differently from one
switched off. A feedback line lists the rules whose text it carried, which is how later feedback
in the session cites them by id alone; a session that loses its context under the same id, as a
compaction does, keeps those ids without their text. A re-entry line keeps its reply; the first
one after a session's feedback line is the revision, so the log shows which flagged passages the
session kept. Any Stop hook's continuation logs a re-entry, so later ones in the same session are
other hooks' turns.

It skips the model when the message is empty, when the hook is re-entering after its own
feedback, which is what holds the review to once per turn, and in a session nobody reads:
CHAT_REVIEW_OFF set, DISPATCH_WORKLOG set (a dispatched worker), or CLAUDE_CODE_SESSION_ATTENDED
set to 0 (a print-mode session, which is how Claude Code marks one since 2.1.27x).

Env: CHAT_REVIEW_OFF (any value turns the hook off), CHAT_REVIEW_MODEL (default haiku),
CHAT_REVIEW_LOG (default ~/logs/chat-review/log.jsonl).
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CATALOGUE = Path(__file__).resolve().parent / "CATALOGUE.md"
LOG = Path(os.environ.get("CHAT_REVIEW_LOG", Path.home() / "logs/chat-review/log.jsonl"))
MODEL = os.environ.get("CHAT_REVIEW_MODEL", "haiku")
REVIEWER_TIMEOUT_S = 45
# Claude Code moves hook output past 10,000 characters into a file and shows the session a preview.
FEEDBACK_LIMIT = 9_500

PROMPT = """You are a prose editor. Review one chat message, written by a coding agent to its user, against the rules below.

Report only hits a careful human editor would flag, each quoted verbatim from the message. When in doubt, no hit. Code blocks, file paths, commands, identifiers, tables and quoted tool output are not prose: never flag them.

Answer with one JSON object and nothing else:
{"hits": [{"rule": "<rule id>", "quote": "<verbatim excerpt>", "note": "<what is wrong with it, in a few words>"}]}
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


def rules_by_id(rules: str) -> dict[str, str]:
    """The selected rule blocks keyed by id, each without its scope tag, which tells a reviewer
    where the rule binds and tells the session reading the feedback nothing."""
    blocks = re.split(r"^(?=- `)", rules, flags=re.M)
    return {
        block.split("`")[1]: re.sub(r"^(- `[^`]+`) `[^`]+`", r"\1", block.strip())
        for block in blocks
        if block.startswith("- `")
    }


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


def rule_id(hit: dict) -> str:
    """A hit's rule id as the catalogue writes it; a model may answer with a number or backticks."""
    return str(hit.get("rule")).strip("` ")


def feedback(hits: list[dict], rules: dict[str, str]) -> tuple[str, list[str]]:
    """What the session reads, and the ids of the rules whose text it carries: every hit under the
    id of the rule it cites, then the text of each cited rule found in `rules`, once. Past
    FEEDBACK_LIMIT the rule texts give way to the catalogue's path, which keeps the hits in front
    of the session."""
    flagged = [
        f'- rule {rule_id(h)}: "{h.get("quote")}"' + (f' ({h["note"]})' if h.get("note") else "") for h in hits
    ]
    explained = [i for i in dict.fromkeys(map(rule_id, hits)) if i in rules]
    head = [f"An automated review by {MODEL} flagged these passages of your last message against the chat prose rules:", *flagged]
    tail = ["", "Revise the message where the hits hold."]
    full = "\n".join(head + (["", "The rules they cite:", *(rules[i] for i in explained)] if explained else []) + tail)
    if len(full) <= FEEDBACK_LIMIT:
        return full, explained
    return "\n".join(head + ["", f"The rules they cite, by id, are in {CATALOGUE}."] + tail), []


def shown_rules(session_id: str | None) -> set[str]:
    """The ids of the rules whose text this session's earlier feedback carried, read from the log.

    A line cut short by a concurrent write is skipped; the cost is a rule text shown twice.
    """
    if not session_id or not LOG.exists():
        return set()
    shown = set()
    with LOG.open() as f:
        for line in f:
            if session_id not in line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("session_id") == session_id:
                shown.update(entry.get("explained", []))
    return shown


def log(session_id: str | None, **entry: object) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "session_id": session_id, **entry}) + "\n")


def review(message: str, rules: str) -> list[dict]:
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
    hook = json.load(sys.stdin)
    session = hook.get("session_id")
    # CHAT_REVIEW_NESTED marks the reviewer's own session, which loads no plugin and so should
    # never reach this hook; it is what keeps a mistake there from recursing. Logged like the
    # rest, because reaching it means a reviewer session is loading the plugin after all.
    if os.environ.get("CHAT_REVIEW_NESTED"):
        log(session, decision="skip", why="nested")
        return
    if os.environ.get("CHAT_REVIEW_OFF"):
        log(session, decision="skip", why="off")
        return
    if os.environ.get("DISPATCH_WORKLOG"):
        log(session, decision="skip", why="dispatched worker")
        return
    # Claude Code marks an attended session with 1 and a print-mode one (a diffview summary,
    # a script's nested call) with 0; older versions set nothing, and those run the review.
    if os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        log(session, decision="skip", why="unattended session")
        return
    message = (hook.get("last_assistant_message") or "").strip()
    if hook.get("stop_hook_active"):
        log(session, decision="allow", why="re-entry", message=message)
        return
    if not message:
        log(session, decision="allow", why="empty")
        return
    t0 = time.monotonic()
    try:
        rules = chat_rules(CATALOGUE.read_text())
        hits = review(message, rules)
    except Exception as e:  # noqa: BLE001  fail open: a broken reviewer never holds up the user
        log(session, decision="allow", why=f"reviewer failed: {e}", ms=int((time.monotonic() - t0) * 1000), message=message)
        return
    ms = int((time.monotonic() - t0) * 1000)
    if not hits:
        log(session, decision="allow", why="clean", ms=ms, message=message)
        return
    shown = shown_rules(session)
    context, explained = feedback(hits, {i: text for i, text in rules_by_id(rules).items() if i not in shown})
    log(session, decision="feedback", hits=hits, explained=explained, ms=ms, message=message)
    # additionalContext continues the turn like a block decision but shows in the transcript as
    # "Stop hook feedback" rather than as a hook error.
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": context}}))


if __name__ == "__main__":
    main()
