# Chat review hook

## Question

Can a Stop hook that has a small model read the turn's final message against the tells catalogue, and block once with the hits, deliver a cleaner reply at a latency and a nag rate the user accepts? (one-flow spec, Q5.)

## What was tried

A command hook read the Stop input, skipped the re-entry after its own block, sent the message plus a copy of the rules to a nested `claude -p` (Haiku, no tools, no settings, no plugins, no MCP servers, thinking off) and printed a block decision whose reason listed each hit as rule number, verbatim quote and fix. It failed open and logged every decision as a JSON line. A settings file wired it; `try` drove it through a real print-mode session.

The hook shipped from this: [`mx/skills/writing-for-humans/chat_review.py`](../../../mx/skills/writing-for-humans/chat_review.py), registered in `mx/hooks/hooks.json` and reading the chat-scoped rules of the catalogue beside it. The prototype's script, rules copy and settings file went with it; `try` drives the shipped hook and fails when the hook never reached the reviewer, and the measurements below are what this directory is kept for. The last row is the shipped hook; the rows above it are the prototype's.

Measured on 2026-09-14, Claude Code 2.1.270, Haiku 4.5:

| Message | Decision | Latency | Hits |
| --- | --- | --- | --- |
| a deliberately slop-laden ORM pitch | block | 5.3 s | 13, all real (opener, closer, em dash, "not just X but Y", "boasts", "serves as", "bedrock", "paradigm shift", "leverages", "in order to", "vibrant") |
| a short status reply | allow | 2.3 s | none |
| the agent's own round-1 opening in this grilling | block | 3.7 s | 3: two bold lead-ins misread as throat-clearing and meta-commentary, one genuinely dense sentence |
| live loop via `try`: outer Haiku session, sloppy prompt | block, rewrite, allow | 4.5 s for the review | 6; the rewrite dropped the opener, the closer and three of four em dashes |
| the same loop through the shipped hook, 2026-09-15, Claude Code 2.1.243 | feedback, rewrite, allow | 5.2 s for the review | 9; every quoted tell was gone from the rewrite |
| the same prompt in an interactive session driven through tmux, 2026-09-15, Claude Code 2.1.272, whose print-mode sessions the hook skips, so `try` no longer reaches the reviewer; hits carry a note and the feedback the text of each cited rule | feedback, revision, allow | 5.0 s for the review | 6; the revision reworded all six, the closing offer kept its shape, and the opening compliment, which no hit quoted, survived |

## Findings

- **Thinking must be off for the reviewer.** With it on, Haiku spent 14,608 output tokens and 131 s on a 300-token answer, at low effort too. `--settings '{"alwaysThinkingEnabled": false}'` brings the whole call to 2 to 5 s. `--bare` is not usable: it skips keychain reads, so the nested call is not logged in.
- **A prompt hook cannot carry the catalogue.** Prompt hooks read no files, so the rules would have to be inlined into settings, a second home. A command hook that calls `claude -p` keeps the catalogue file as the one home and lets the script decide the model, the flags and the once-per-turn rule.
- **Bold lead-ins get misflagged.** The catalogue's rule 16 permits a bold lead-in ending in a period; the chat additions 34 and 36 do not repeat that exception, and the reviewer flagged two lead-ins under them. The merged catalogue's chat rules need the carve-out stated once where it binds.
- **One block per turn leaves residue.** The reviewer quotes one instance per tell, the rewrite fixes what was quoted, and the re-entry is not checked. The reviewer could list every instance (amended 2026-09-15, was "or a second check is allowed before the re-entry passes", which the user ruled out: the review runs once per turn, and the session decides which hits to act on).
- **Startup, not the model, is the other cost.** The nested call must skip user settings, plugins, hooks and MCP servers (`--setting-sources "" --strict-mcp-config`), else startup alone is 4 s and the plugin's own Stop hook would recurse. The `CHAT_REVIEW_NESTED` guard covers recursion regardless.
- **The user sees the draft, the feedback and the rewrite.** A Stop hook runs after the reply has streamed to the screen; continuing the turn appends the corrected reply below it. The hook now returns the hits as `additionalContext` (the transcript labels it "Stop hook feedback") instead of `decision: block` (labelled a hook error); both continue the turn the same way. The only mechanism that changes text before it is shown is MessageDisplay, which is display-only, holds the screen per batch of lines while the hook runs, and would have a small model rewrite prose unchecked; rejected for the prototype. Within a session the feedback stays in the model's context, so later replies should come out cleaner before any hook runs; whether that holds is what a week of the log will show.
- **Sessions nobody reads should skip it.** A dispatched worker's chat is read by no one, so the hook should return early there; which marker in the environment says so was left to the build. Not built into the prototype.

## Verdicts

Ruled by the user in round 3 and round 4 of the one-flow grilling, and built as [The chat reviewer ships with the mx plugin](../../tickets/one-flow/03-chat-reviewer.md):

- The reviewer as a command hook calling a bare, non-thinking Haiku is the shape to keep.
- Its production home is the mx plugin's own hooks, so every machine gets it with the plugin; one environment variable turns it off.
- The chat additions belong in the merged catalogue, scoped `chat`, with rule 16's exception stated beside them.
