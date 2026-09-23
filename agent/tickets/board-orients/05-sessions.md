---
status: claimed
blocked-by: [04]
priority: 2
size: S
---

# The sessions behind a ticket

## Brief

An opened ticket lists the sessions whose commits changed it, each with its title and a button that copies the command resuming it; only sessions you can resume on this machine show.

Slice of `spec.md`, building on the Decision on sessions from `Session:` commit trailers.

## What to build

The board reads the `Session:` trailers of every commit that changed the ticket file, on every branch, and lists each session with its first and last commit. The title is the session's `/rename` name, else Claude Code's own title, and the working directory comes from its transcript on this machine; a session with no transcript here, a worker on another host, is left out. Each listed session has a button showing and copying `cd <dir> && claude --resume <id>`. With no trailers, the ticket lists no sessions and says nothing.

## Acceptance criteria

- [ ] The listed-session and render-without-transcripts checks from 01 pass and their annotations are gone.
- [ ] Property, reviewed: a copy button shows what it copies.
- [ ] `test_board.py` covers trailers across branches, a transcript present and absent, and a renamed session's title.
- [ ] Demo: the demo tracker's ticket with three sessions in its commits, two listed and the worker's left out, and a copied resume command run.
