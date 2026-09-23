---
status: proposed
priority: 2
size: S
blocked-by: [02, 03]
---

# The Stop hook renders the pages as each turn ends, and sends back what does not belong

## Brief

One hook renders the pages as each turn ends, and sends the agent back when its record does not parse or its answer went to the chat instead of the page.

Slice of `spec.md`, building on its Decisions under Producing the pages (the Stop hook, one fixed renderer, the main session waits for its artifacts, created lazily, where it lives), and on its Properties.

## What to build

One Stop hook in the plugin that, as a turn ends in a session that has a session directory: sends the agent back with the reason when the turn's record does not parse; sends it back when it put its answer in the chat and wrote no record (a reply longer than three lines with no record written this turn); and otherwise renders the session page, and the spec page when the session record names a spec. A session with no directory is left alone and nothing is written for it. The hook is keyed by the session id it receives and stays out of a dispatched worker's session and of a print-mode session, as `chat_review.py` does today. It takes over `chat_review.py`'s place in the plugin's hooks: the chat-reply review stops running here, and 05 moves the reviewer onto the turn record.

`agent/sessions` joins the global git ignore list in dotfiles (`nix/home/common.nix`, beside `agent/handoffs`). That file is outside every worktree, so the session holding the branch makes that edit as loose work before this ticket lands, and the closing comment says whether it has.

How an open tab learns to reload stays open, as the spec leaves it: the page must be right on a manual reload.

## Acceptance criteria

- [ ] The Stop hook's two properties from 01 pass, their expected failures lifted.
- [ ] The plugin registers this hook and no longer registers the chat-reply review; `make check` passes.
- [ ] A dispatched worker's session and a print-mode session are left alone, as `chat_review.py` leaves them today.
- [ ] Demo: a scratch session directory driven through the hook's three outcomes: rendered, sent back for a broken record, sent back for an answer left in the chat, each with the hook's output; then a session without a directory, with nothing written.
