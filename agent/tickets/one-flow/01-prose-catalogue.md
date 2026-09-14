---
status: open
---

# One prose catalogue with rule ids and scope tags

## What to build

The unslop skill and writing-for-humans become one skill. The catalogue of tells is one companion file of writing-for-humans, carrying every rule with a stable id and a scope tag (`artifact`, `chat`, or `both`); the skill body keeps only what a catalogue cannot hold (the cold reader, one home per fact, referencing by title) and points at the catalogue for the sweep. The unslop skill directory is deleted and every pointer to it or to the old patterns file is repointed (the README's skills table, the orient skill's standalone list).

The catalogue's content: unslop's numbered rules as they are, keeping their numbers; the rules from the old patterns file that have no id (throat-clearing openers, emphasis crutches, business jargon, rhetorical setups, false agency, narrator-from-a-distance, dramatic fragmentation, negative listing, binary contrasts, formulaic wrap-ups, chat residue, source-gap speculation, didactic disclaimers, unfilled placeholders) get ids continuing the sequence; the three rules the output style stopped carrying (nominalizations, noun stacks, generalities and platitudes) and the bold lead-in carve-out come in from the prototype's rules file at `agent/prototypes/chat-review-hook/CHAT-RULES.md`, which shows their wording. Any rule that exists twice across the sources is one rule with one id. Each rule keeps its before/after example where the source had one.

A reader of the catalogue (a reviewer, the chat hook) must be able to select the rules for a scope without reading the others: the tag is machine-readable and uniform.

## Acceptance criteria

- [ ] One catalogue file beside writing-for-humans' SKILL.md; the old patterns file and the unslop skill directory are gone; no pointer in the repo names either.
- [ ] Every rule has an id that never changes and a scope tag; ids from unslop are preserved; a removed rule leaves a gap rather than renumbering.
- [ ] Rules 37 to 39 and the bold lead-in carve-out from the prototype's rules file are in, under the same numbers.
- [ ] writing-for-humans' SKILL.md carries the cold-reader, one-home and referencing sections and a pointer to the catalogue, nothing the catalogue holds.
- [ ] Property, reviewed: a rule about prose lives in one catalogue; every prompt that needs it points there.
- [ ] Demo in the closing comment: the command that lists the chat-scoped rules from the catalogue, and its output.
