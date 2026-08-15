---
name: recap
description: Structured status report on the work in flight — findings, decisions (explicit vs implicit), open questions, next steps. Use when the user asks where things stand, has lost the thread mid-session, or another skill needs the current state laid out.
argument-hint: [focus-area]
---

# Status Report

Report where the work stands, so the reader can validate or correct it in one scan. Assume they lost the thread: give the context around each point, write in ASD-STE100 Simplified Technical English (short sentences, one idea each, plain words), and use the `CONTEXT.md` vocabulary.

Focus area, if given: $ARGUMENTS — otherwise cover the whole session.

## Structure

**Key Findings:** what you have learned so far

**Decisions:**
- Explicit — the user said it or confirmed it
- Implicit — you assumed it or decided it without confirmation; surface these first, this is where drift starts

**Open Questions:** what needs clarification before proceeding

**Next Steps:** what you would do next, so the user can approve or redirect

## Guidelines

- Bullet points, not paragraphs
- Reference the task file if the work has one
- Flag the architectural and strategic calls you made without user input

**After the recap:** ask the open questions with AskUserQuestion if any are worth asking. The user scans the recap and answers in the same pass, and escape dismisses it — err toward using it.
