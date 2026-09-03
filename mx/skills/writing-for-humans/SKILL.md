---
name: writing-for-humans
description: "Writing artifact text for cold readers: docs, READMEs, docstrings, comments, UI copy, commit messages, ticket prose. Use when drafting or editing artifact text, when asked to de-slop a file, or when a review needs prose standards."
user_invocable: true
---

Counterpart to `/mx:writing-for-agents`: that skill covers documents that instruct an agent's process; this one covers text that explains or records, read cold by whoever finds it, human or agent. A document that does both (a spec, an ADR) loads both.

Invoked on a file or diff, this is a pass: apply every rule below to every sentence, fix or report each hit. Empty is a valid result.

## The cold reader

The artifact's reader has no access to the conversation that produced it. Every sentence must stand on the artifact alone. **Conversation residue** is text that only means something relative to the session that wrote it:

- **Decisions-against**: "never X", "we don't use Y", where the reader never had X on the table. Home: the commit message, the spec's out-of-scope section, or an ADR.
- **Change narration**: "now uses Z", "no longer does W". The artifact states what *is*; history lives in the commit message and the changelog.
- **Reviewer reassurance**: "correctly handles", "as requested", "this ensures". Addressed to the person who asked for the change, noise to everyone after. Delete.

The test: does a stranger reading only this artifact learn something from the sentence? A sentence that needs the chat transcript to make sense moves to its home or gets deleted.

## One home per fact

Every fact has one authoritative home, usually the code, config, `--help` output, or schema itself. Text restating it elsewhere is a **cache**: a copy that goes stale the moment the home changes, then lies to the reader.

- A vocabulary enumerated in a docstring *and* defined in code below → the code is the home; the docstring names the concept and points.
- A version number or flag list hardcoded in a README → derive it: a command the reader runs, a generated include.
- Prose describing what the adjacent five lines of code plainly show → delete.

Cache deliberately or not at all: a copy earns its place only when the lookup is genuinely expensive, and then it names its home so the reader can check it.

## Style

- Lead with the point; supporting detail after.
- One idea per sentence. Active voice, named actors.
- State facts directly: no throat-clearing openers, no vague declaratives ("the implications are significant"; name the implication), no meta-commentary announcing the document's own structure.
- Plain words over coinage, but a genuinely new concept the text keeps returning to gets one term, defined once, used consistently everywhere (never rotated through synonyms).
- Cut every sentence whose deletion costs the reader nothing.

For a deep de-slop pass on longform prose, sweep against [`PATTERNS.md`](PATTERNS.md), the full catalogue of AI prose tells: phrase lists, formulaic structures, before/after examples.
