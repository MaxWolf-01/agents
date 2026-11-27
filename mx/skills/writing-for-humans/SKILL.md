---
name: writing-for-humans
description: "Writing artifact text for cold readers: docs, READMEs, docstrings, comments, UI copy, commit messages, ticket prose. Use when drafting or editing artifact text, when asked to de-slop a file, or when a review needs prose standards."
---

This skill covers text that explains or records, read cold by whoever finds it, human or agent; `/mx:writing-for-agents` covers documents that instruct an agent's process. A document that does both (a spec, an ADR) loads both.

The tells are in [`CATALOGUE.md`](CATALOGUE.md) beside this file, each with a stable id a finding can cite and a tag saying which media it binds. Invoked on a file or diff, this skill is a pass: read every sentence against every rule of the catalogue and against the sections below, and fix or report each hit. Then ask what still makes the text read as AI generated, and cut every sentence whose deletion would cost the reader nothing. Empty is a valid result.

## The cold reader

The artifact's reader never saw the conversation that produced it, so every sentence stands on the artifact alone. **Conversation residue** is text that means something only relative to the session that wrote it:

- **Decisions-against**: "never X", "we don't use Y", where the reader never had X on the table. Home: the commit message, the ticket's Out of scope section, or an ADR.
- **Change narration**: "now uses Z", "no longer does W". The artifact states what *is*; history lives in the commit message and the changelog.
- **Reviewer reassurance**: "correctly handles", "as requested", "this ensures", addressed to whoever asked for the change. Delete.

The test: does a stranger reading only this artifact learn something from the sentence? A sentence that needs the chat to make sense moves to its home or is deleted.

## One home per fact

Every fact has one authoritative home, usually the code, config, `--help` output or schema itself. Text restating it elsewhere is a **cache**, which goes stale the moment the home changes and then lies to the reader.

- A vocabulary enumerated in a docstring *and* defined in code below → the code is the home; the docstring names the concept and points.
- A version number or flag list hardcoded in a README → derive it: a command the reader runs, a generated include.
- Prose describing what the adjacent five lines of code plainly show → delete.
- One fact in two places in the same document, once where it belongs and once in passing → keep the one the reader meets in context, delete the other.

Cache only when the lookup is genuinely expensive, and then name the home so the reader can check it.

## Referencing by title

Refer to a ticket, issue or ADR by its title, in chat as in a file, with the id inside the link: `[Decide the ticket vocabulary](agent/tickets/ticket-vocabulary.md)`. A bare `#42` or `03` in place of the name is illegible in a list; the title reads at a glance and the id stays one click away.
