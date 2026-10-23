---
name: wrap
description: "Make the session closable, or say what keeps it open. Use when the user asks whether the session is done, can be closed, or has anything left."
---

The user is about to close this session, and whatever only the chat holds goes with it.

1. **Stop what this session started**: its worktrees, branches, tmux sessions, jobs, servers and workers, and report only those. Scratch files can stay, and so does anything the session page links to.
2. **Empty the chat.** Each loose end and open question goes to a ticket (`/mx:tracker`), each lesson to its home (`CLAUDE.md` or `AGENTS.md`, an ADR or the glossary through `/mx:domain-modelling`), and a script worth running again into the repo. A chore the session can do itself is done, not handed to the user.
3. **Tell whoever runs on what shipped**, such as a sibling session or a deployed agent: send it, or draft the message for the user to send.
4. **Answer in a line or two**, one of:
   - closable: what landed, and that nothing waits on the user;
   - continued in a fresh session: write the handoff (`/mx:handoff`);
   - not done: what is left, and whose move it is.
