---
name: wrap
description: "Is this session closable? Finish what is left, or clean up so it can close."
disable-model-invocation: true
---

The user is asking whether this session can be closed, often after time away from it. They no longer know where it stands; you do.

1. **Check what is left.** Look back over the session: work started and not landed, a ruling the user gave that is not acted on yet, something you said you would do. If anything is left, say what it is and do it, or put to the user what only they can decide. The session stays open, and the steps below wait until nothing is left. Where the rest is better done in a fresh session (the context is full, or the user is stopping for now), write the handoff (`/mx:handoff`).
2. **Nothing left: clean up.**
   - Stop what this session started: its worktrees, branches, tmux sessions, jobs, servers and workers. Report only those.
   - Move what only the chat holds and is worth keeping. Each loose end and open question goes to a ticket (`/mx:tracker`), each lesson to its home (`CLAUDE.md` or `AGENTS.md`, an ADR or the glossary through `/mx:domain-modelling`), and a script worth running again into the repo. A chore the session can do itself is done, not handed to the user.
   - Tell whoever runs on what shipped, such as a sibling session or a deployed agent: send it, or draft the message for the user to send.
3. **Answer verdict first.** The user often reads only the hub, which shows the newest turn's headline as the session's status, so the verdict opens the turn record's headline and its chat recap, in one of two fixed forms:
   - `Closable: <the session's subject>, <what landed>`, once nothing is left.
   - `Open: <what keeps it open>`, while step 1 left something only the user can settle, each such call also a question of the record.

   Its Details are three lines, in this order, each there even when it says "nothing": **Landed** (merged, pushed, released, with the commit or version), **Stopped** (what step 2 stopped or removed), **Waits on you** (nothing, or each item by its question tag).
