---
status: proposed
parent: session-page
blocked-by: [session-stop-hook]
priority: 3
size: S
---

# The turn record's prose gets a light review before the page renders

## Brief

A turn record's prose gets a light review against the writing catalogue before the page renders, and the chat-reply reviewer it replaces retires.

Slice of `session-page`, building on its Decisions under Producing the pages: Review, and The reviewer's harness.

## What to build

The Stop hook reviews a newly written turn record before rendering it. The reviewer is Opus 5.5 at medium effort, reading the record against the writing-for-humans catalogue's rules for chat, and seeing what the page's reader has seen: the session's earlier turn records and the user's messages, never tool calls. It runs with its own system prompt instead of Claude Code's persona, gets the record fenced in tags and the turn record's shape with the structure that shape requires exempt by name, answers against a JSON schema, and hands at most three findings back; a finding whose quote is not a substring of the record is dropped. The agent revises the record and the next stop renders it. The review runs once per turn, fails open when the model is unavailable, and logs each decision, as `chat_review.py` does. `chat_review.py`'s chat-reply mode is retired with this slice: whatever of it the turn review reuses moves, the rest is deleted.

## Acceptance criteria

- [ ] At the hook's seam, with the reviewer stubbed as `chat_review.py`'s tests stub it: a record with findings goes back with at most three, a finding quoting text absent from the record is dropped, and a failing or slow reviewer lets the page render.
- [ ] The reviewer's input carries the earlier turn records and the user's messages, and no tool call.
- [ ] Nothing in the plugin still reviews the chat reply, and no file describes that review as current.
- [ ] Demo: one sloppy turn record and one clean one run through the hook with the real reviewer, the findings it returned, and the page after the revision.
