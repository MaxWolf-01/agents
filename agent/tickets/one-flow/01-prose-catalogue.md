---
status: done
diff: [3479b32a6f9e1fd4e35752d0d4617f1aacaa5243..ee286e0105a253dc214b9790016e9d5e3813e0da]
---

# One prose catalogue with rule ids and scope tags

## What to build

The unslop skill and writing-for-humans become one skill. The catalogue of tells is one companion file of writing-for-humans, carrying every rule with a stable id and a scope tag (`artifact`, `chat`, or `both`); the skill body keeps only what a catalogue cannot hold (the cold reader, one home per fact, referencing by title) and points at the catalogue for the sweep. The unslop skill directory is deleted and every pointer to it or to the old patterns file is repointed (the README's skills table, the orient skill's standalone list).

The catalogue's content: unslop's numbered rules as they are, keeping their numbers; the rules from the old patterns file that have no id (throat-clearing openers, emphasis crutches, business jargon, rhetorical setups, false agency, narrator-from-a-distance, dramatic fragmentation, negative listing, binary contrasts, formulaic wrap-ups, chat residue, source-gap speculation, didactic disclaimers, unfilled placeholders) get ids continuing the sequence; the three rules the output style stopped carrying (nominalizations, noun stacks, generalities and platitudes) and the bold lead-in carve-out come in from the prototype's rules file at `agent/prototypes/chat-review-hook/CHAT-RULES.md`, which shows their wording. Any rule that exists twice across the sources is one rule with one id. Each rule keeps its before/after example where the source had one.

A reader of the catalogue (a reviewer, the chat hook) must be able to select the rules for a scope without reading the others: the tag is machine-readable and uniform.

## Acceptance criteria

- [x] One catalogue file beside writing-for-humans' SKILL.md; the old patterns file and the unslop skill directory are gone; no pointer in the repo names either.
- [x] Every rule has an id that never changes and a scope tag; ids from unslop are preserved; a removed rule leaves a gap rather than renumbering.
- [x] Rules 37 to 39 and the bold lead-in carve-out from the prototype's rules file are in, under the same numbers.
- [x] writing-for-humans' SKILL.md carries the cold-reader, one-home and referencing sections and a pointer to the catalogue, nothing the catalogue holds.
- [x] Property, reviewed: a rule about prose lives in one catalogue; every prompt that needs it points there.
- [x] Demo in the closing comment: the command that lists the chat-scoped rules from the catalogue, and its output.

## Comments

### Closing, worker on `ticket/one-flow/01-prose-catalogue`

Three files held overlapping copies of the same tells: the unslop skill (ids 3 to 33), writing-for-humans' `PATTERNS.md` (no ids), and the chat-review prototype's `CHAT-RULES.md` (ids 34 to 39 on top of a verbatim copy of unslop). They are now one file, `mx/skills/writing-for-humans/CATALOGUE.md`: 46 rules, each a bullet carrying its permanent id, its scope tag and its name.

**Demo.** The chat reviewer's selection, run from the repo root:

```
$ awk '/^#/{k=0} /^- `/{k=($3=="`chat`"||$3=="`both`")} k' mx/skills/writing-for-humans/CATALOGUE.md
- `3` `both` **Superficial -ing phrases.** "highlighting...", "ensuring...", ...
- `5` `both` **Vague attributions.** "Experts believe", "Industry reports suggest", ...
- `49` `both` **Source-gap speculation.** "While specific details are not widely ...
- `7` `both` **AI vocabulary.** Additionally, commitment to, crucial, delve, ...
  [...]
- `43` `both` **False agency.** Human verbs given to inanimate things, which is ...

$ ... | grep -c '^- `'
44                 # of 46 rules; 44 narrator-from-a-distance and 51 unfilled
                   # placeholders are tagged `artifact` and drop out
```

Each rule's block comes out whole: the indented continuation lines (rule 16's bold lead-in carve-out, the before/after examples on 23, 41, 42, 45, 47) ride with their rule, and the section headings do not leak.

**Where the content went.** Unslop's ids 3 to 33 are unchanged, gaps 1, 2, 4, 6, 21 included. 34 to 39 are the prototype's, under its numbers. 40 to 51 are the patterns file's id-less headings, in the order this ticket lists them: emphasis crutches 40, business jargon 41, rhetorical setups 42, false agency 43, narrator-from-a-distance 44, dramatic fragmentation 45, negative listing 46, binary contrasts 47, formulaic wrap-ups 48, source-gap speculation 49, didactic disclaimers 50, unfilled placeholders 51. Rules that existed twice became one: the patterns file's throat-clearing openers joined 34, its chat residue joined 20, its adverb and filler lists joined 30 and 23, and the Wikipedia distillation folded into 3, 5, 7, 8, 9, 11 and 15 to 18. The skill body kept the cold reader, one home per fact and referencing by title; its Style bullets dissolved into rules 28, 29, 34, 35, 36 and 39 rather than being copied anywhere.

**Action items.**

- Rule on A4, the scope partition. It is the one call here with a real alternative and it sets what the chat hook gets.
- Rule on A3, whether the dropped rule comes back as id 52.
- For ticket 03: the chat selection is 44 rules; the prototype measured its reviewer against 34. Ten rules it never saw are now in scope, several of them longform-shaped (48's "Future Prospects", 46's negative listing). Its latency and false-positive numbers do not carry over unchanged.
- For ticket 04: `mx/skills/code-review/SKILL.md:42` already names the catalogue beside the skill (see S1 below), which overlaps that ticket's "Standards brief lists the catalogue by path".

**Assumptions.**

- A1 `mx/skills/writing-for-humans/CATALOGUE.md:1`: the file is named `CATALOGUE.md`, beside `SKILL.md`, the way `SMELLS.md` and `TEST-SMELLS.md` sit beside code-review's. Tickets 03 and 04 say "the catalogue file of ticket 01", so this path is what they will hardcode.
- A2 `mx/skills/writing-for-humans/CATALOGUE.md:72` (rule 20): chat residue took no new id. This ticket lists it among the id-less rules that get one, and also says any rule existing twice is one rule with one id; rule 20 already banned the same phrases, so 20 absorbed it and gained the knowledge-cutoff disclaimer example. Reverse by cutting a new id off the end.
- A3 `mx/skills/writing-for-humans/CATALOGUE.md:76` (rule 34): the patterns file's ban on sentences opening with a question word is dropped rather than numbered. It contradicts rule 33, which asks for whole sentences with their subordinate clauses, and would fire on most correct prose ("When the parser fails, it exits 2"); its siblings in the same source block ("Look,", a paragraph opening with "So") are in 34, and "What if..." is in 42. Both reviewers that saw it want it back as id 52.
- A4 `mx/skills/writing-for-humans/CATALOGUE.md:5`: the scope partition is 44 `both`, 2 `artifact`, 0 `chat`, on the test that the tag says where the rule's **fix** belongs. Rule 51 tells a writer to sweep a document for template blanks before delivering, and rule 44 asks for essay voice ("put the reader in the room"); applying either to a chat reply makes it worse. The spec's own criterion for the chat reviewer is wider, "every rule checkable from the message alone", and both rules are checkable from a message; read that way, all 46 are `both` and the column is constant. The alternative is one line of edits and a tag that does nothing; a third option is to cut the chat scope to what the prototype measured (3 to 39), which is grounded in a measurement but not in any principle. Both reviewers flagged this partition, from opposite directions.

**Findings.** Review of `bf5d4aa` against `3479b32`, three axes (no test files, so no Tests axis). Fixes are in `7238dff`.

- C1 dropped question-word rule → declined, A3.
- S1 the Standards reviewer loses the rules: code-review passes writing-for-humans' `SKILL.md` as a per-diff standards source because "its rules bind all artifact text", and the rules had moved to the companion file → fixed, that bullet now names the catalogue too, and the skill's own pointer no longer reads as conditional.
- S2 the catalogue said nothing about how hard a rule binds, where `SMELLS.md` states two binding rules → fixed, the header now says punctuation and formatting bind hard, the rest are named heuristics, and a repo document that endorses what a rule flags wins.
- S3 no rule carries the `chat` tag, so the selector has a dead branch → declined, A4.
- S4 rules 20, 22 and 34 listed the same phrases → fixed, 34 now carries the shape and points at 20 and 22 for the phrases.
- S5 ordered-list syntax renumbers the ids when rendered (Content's 3, 5, 49 came out 3, 4, 5), so every cited id was wrong on the page → fixed, the rules are bullets opening with the id as a code span, matching the two baselines beside code-review; the selector changed with them.
- S6 the skill's pass sentence was a verbless fragment and counted its own sections → fixed.
- S7 `agent/prototypes/chat-review-hook/CHAT-RULES.md:3` still names the deleted unslop skill → declined here, ticket 03 retires that file.
- S8 three phrases from the patterns file ("X is a feature, not a bug", "dressed up as", "You already know this, but") had landed in no rule → fixed, into 32 and 36.
- P1 no demo and no closing comment → fixed, this comment.
- P2 the scope tags partition almost nothing → declined, A4.
- P3 the chat selection grew past what the prototype measured → passed to ticket 03, above.
- P4 the selector in the header is a second home for the parse ticket 03's script must implement → declined: this ticket's demo criterion asks for that command, and the header is where the format contract is stated; 03's script implements the same contract.
- P5 the header names the chat reviewer, which does not exist until ticket 03 → declined: it lands in this feature, behind this ticket.

**Friction.**

- This ticket's repoint list ("the README's skills table, the orient skill's standalone list") describes a repo state that was not there: at the base commit, nothing outside `mx/skills/unslop/SKILL.md` itself named the skill, and only writing-for-humans' own `SKILL.md` named `PATTERNS.md`. The unslop skill was `disable-model-invocation: true` with no pointer anywhere, so it could only ever have been loaded by a human typing it. Deleting it costs nothing, which is worth knowing: the always-loaded prose rules the spec wants to retire were already not loading.
- The code-review skill in force deletes the axis reports after reading them, so the finding index above is the only surviving trace of three reviews. Ticket 04 fixes exactly this; working a ticket whose own feature has not landed yet means the old rule applies.
- No `python3` on this host, which is a fine constraint for text surgery (`sed`, `awk`, heredocs) but worth recording for whoever writes a script for a worker to run.
