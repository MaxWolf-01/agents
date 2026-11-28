# AI prose tells

Every prose reviewer sweeps against this catalogue: the standards pass of a diff's review, the turn review on a session page's record, `/mx:writing-for-humans` on a file. A rule about punctuation or formatting binds hard; every other rule is a named heuristic, so a finding cites the id, quotes the hit and names the fix rather than asserting a violation, and a documented repo standard that endorses what a rule would flag wins. One match may be coincidence; several together are the tell.

Each rule is one block: a bullet carrying its id, its scope tag and its name, plus the lines indented under it. Ids are permanent and cited from elsewhere, so they run out of order and a removed rule leaves a gap. The scope tag says where the rule's fix belongs: `artifact` for text that ships in a file, `chat` for a reply the user reads, in the chat or as a turn on the session page, `both` where the fix improves either. This command selects one scope without reading the rest, here the rules the turn review applies:

```
awk '/^#/{k=0} /^- `/{k=($3=="`chat`"||$3=="`both`")} k' CATALOGUE.md
```

## Content

- `3` `both` **Superficial -ing phrases.** "highlighting...", "ensuring...", "reflecting...", "showcasing...", "fostering...": a present participle bolted onto a fact to append analysis it has not earned. End the sentence at the fact; analysis that matters gets its own sentence with its own sources.

- `5` `both` **Vague attributions.** "Experts believe", "Industry reports suggest", "Some critics argue", "widely regarded", "observers have cited". An opinion pinned on an unnamed authority, or one source presented as many. Name the source or delete.

- `49` `both` **Source-gap speculation.** "While specific details are not widely documented...", "based on available information", followed by what the missing facts "likely" are. The gap claim is itself unverified and the filler after it is fabrication. State what the sources say, and stop where they stop.

## Language

- `7` `both` **AI vocabulary.** Additionally, commitment to, crucial, delve, diverse array, enduring, enhance, fostering, garner, groundbreaking, interplay, intricate, landscape (abstract), meticulous, nestled, pivotal, renowned, rich, robust, seamlessly, showcase, tapestry (abstract), testament, underscore, vibrant. Replace with plain words. One alone is fine; a cluster is the fingerprint. The same words inflate significance ("stands as a testament", "a pivotal moment", "underscores its importance"): state the fact and let the reader judge how much it matters.

- `8` `both` **Fancy ways to say "is".** "serves as", "stands as", "functions as", "represents", "boasts", "features", "offers", "refers to". Say "is" or "has".

- `9` `both` **"Not just X, but Y."** Also "not only X, but also Y" and "doesn't just X, it Y". State the point directly.

- `10` `both` **Rule of three.** Forcing ideas into groups of three. Use the natural number.

- `11` `both` **Synonym cycling.** Protagonist, main character, central figure, hero all in one paragraph. Pick one, repeat it.

- `12` `both` **False ranges.** "from X to Y" where X and Y aren't on a meaningful scale. List topics directly.

- `41` `both` **Business jargon.** "Navigate" (challenges) becomes "handle" or "address". "Unpack" (an analysis) becomes "explain" or "examine". "Lean into" becomes "accept". "Landscape" (context) becomes "situation" or "field". "Game-changer" becomes "significant". "Double down" becomes "commit". "Deep dive" becomes "analysis". "Take a step back" becomes "reconsider". "Moving forward" becomes "next". "Circle back" becomes "return to".
  Before: "In today's fast-paced landscape, we need to lean into discomfort and navigate uncertainty with clarity. This matters because your competition isn't waiting." After: "Move faster. Your competition is."

## Style

- `13` `both` **Em dash overuse.** Use no em dashes, nor en dashes or hyphens standing in for one. Where a thought needs separation, end the sentence or use a comma; a short gloss or aside goes in parentheses.

- `14` `both` **Colon overuse.** A colon belongs before a list or example, not as a mid-sentence connector. "If you're coming from traditional automation: instead of registering event handlers, you describe conditions" adds nothing with the colon; rewritten so the point stands without the comparison framing, it is "Describing when the scheduler should fire works best as plain English."

- `15` `both` **Boldface overuse.** Don't bold every proper noun or acronym.

- `16` `both` **Inline-header lists.** A bold label and colon that restate the line: "**Performance:** Performance improved...". Convert those to prose.
  Two forms pass. A list whose items each open with a short bold label naming a distinct fact ("**Branch:** `feature/x`, nothing pushed", "**Tests:** 604 pass"), which scans faster than the same facts as prose. And a bold lead-in: a few bold words opening a paragraph or bullet that name what it is about, end in a period, and are followed by new detail ("**Schema in TypeScript.** Tables live in one file."). Both are signposts for skimming, so they pass rules 34 (opener), 35 (coined label) and 36 (meta-commentary) too.

- `56` `both` **Crammed enumerations.** Items the reader scans or copies one at a time (file paths, commands, ids, settings), run together in a sentence or a table cell, most of all when each carries its own note. Put each on its own line with its note beside it: a list in prose, one line per item in a cell or a labelled row of a page. Short words that read as one phrase stay inline ("speed, quality and cost").

- `17` `both` **Title case headings.** Use sentence case.

- `54` `both` **Headline titles.** A title or headline that does not name its subject: it wraps a hook and a reveal around a colon ("What Jarvis knows after a clear: the memory block"), puts counts, bare ids or an unexplained "the" where names belong ("two builds", "C4", "the stage checks"), or turns figurative ("one way into max's life data"). Name the subject and the things in it, in words a cold reader would search for. What follows depends on the headline's job: a title is there to be found, so it says what the thing is about rather than what was done to it ("two builds to land, one ticket grilled", "C2's build lands"); a status line or a report's headline says where things stand, so its verdict, finding or state is the point.
  Before: "The session page's follow-ups: two builds to land, one ticket grilled". After: "Session page: sessions/ hidden from git status, links per checkout, when records are committed". A status that stands: "Upload retries: fix merged, the proxy timeout still open".

- `18` `both` **Decorative emojis.** Remove from headings and bullets. A marker that a documented format gives a fixed meaning is not decoration.

- `19` `both` **Curly quotes.** Replace with straight quotes.

## Structures

- `40` `both` **Emphasis crutches.** "Full stop.", "Period.", "Let that sink in.", "Make no mistake", "This matters because", "Here's why that matters". Delete them.

- `42` `both` **Rhetorical setups.** "What if [reframe]?", "Here's what I mean:", "Think about it:", "And that's okay.", a question posed and answered in the next breath. Make the point and let the reader draw the conclusion.
  Before: "What if I told you that the best teams don't optimize for productivity? Here's what I mean: they optimize for learning. Think about it." After: "The best teams optimize for learning, not productivity."

- `45` `both` **Dramatic fragmentation.** "[Noun]. That's it. That's the [thing].", "X. And Y. And Z.", "This unlocks something. [Word].", short sentences stacked for rhythm. Write complete sentences.
  Before: "Speed. Quality. Cost. You can only pick two. That's it. That's the tradeoff." After: "Pick two of speed, quality and cost."

- `46` `both` **Negative listing.** Listing what something is not before revealing what it is: "Not a X... Not a Y... A Z.", "It wasn't X. It wasn't Y. It was Z." State Z.

- `47` `both` **Binary contrasts.** "Not because X. Because Y.", "[X] isn't the problem. [Y] is.", "The answer isn't X. It's Y.", "It feels like X. It's actually Y.", "stops being X and starts being Y". The contrast is false drama: state Y and drop the negation. Not a hit when the contrast is the content: a recommendation set against the reader's proposal, or a fact corrected against a belief the reader stated.
  Before: "Here's the thing: building products is hard. Not because the technology is complex. Because people are complex. Let that sink in." After: "Building products is hard. Technology is manageable. People aren't."

## Communication artifacts

- `20` `both` **Chatbot phrases.** "I hope this helps!", "Let me know if...", "Of course!", "Certainly!", "Found the smoking gun!", "Would you like me to...", and knowledge-cutoff disclaimers ("As of my last update"). Remove; in a file they are assistant-turn residue.

- `22` `both` **Sycophantic tone.** "Great question! You're absolutely right!" Respond directly.

- `34` `both` **Throat-clearing and closers.** An opener that announces instead of starting ("Here's the thing:", "Here's why X", "The uncomfortable truth is", "It turns out", "The real X is", "Let me be clear", "Let me explain", "I'm going to be honest", "Can we talk about", "Look,", a paragraph opening with "So"), or a closing sentence that offers further work instead of stopping. Start with the answer and stop when the content stops. Where a message lists the calls the reader must make, an ask or offer outside that list is the same tell ("Say go and I'll clear the eight cards"), and the asking rule ([the session page's rules](../session-page/RULES.md), the turn record's Questions) places it: a step the rule leaves to the writer is done and reported, and only a call the rule gives the reader goes in the list, where the reader can answer it by its tag. Rules 20 and 22 carry the phrases themselves.

- `36` `both` **Meta-commentary about the text itself.** Sentences about how the text is structured or follows a style: "To keep this brief", "In short, as requested", "Here's a quick summary of what I did", "Hint:", "Plot twist:", "Spoiler:", "The rest of this essay explains...", "Let me walk you through...", "In this section, we'll...", "As we'll see...", "You already know this, but", "But that's another post". Delete; the reader sees the structure. A heading that sorts content for the reader is that structure, not commentary on it; so is a status line a documented format requires.

- `53` `chat` **A thing to open, named but not reachable.** A reply that sends the reader to a ticket, a file, a draft or a page by its name alone ("the draft is in `model-effort-defaults`", "see the review page"), leaving them to find it. Give its absolute path on this machine or its URL, one the reader can copy as it stands, link it from the turn record on the session page, or open it for them and say so.

- `51` `artifact` **Unfilled placeholders.** "[Your Name]", "2025-XX-XX", "PASTE_URL_HERE": template blanks that shipped. Sweep for brackets and XX before delivering.

## Filler

- `23` `both` **Filler phrases.** "In order to" becomes "To". "Due to the fact that" becomes "Because". "It is important to note that", "At its core", "In today's X", "It's worth noting", "At the end of the day", "When it comes to", "In a world where" and "The reality is" get deleted.
  Before: "It turns out that most teams struggle with alignment. The uncomfortable truth is that nobody wants to admit they're confused. And that's okay." After: "Teams struggle with alignment. Nobody admits confusion."

- `24` `both` **Excessive hedging.** "could potentially possibly be argued that it might" becomes "may".

- `25` `both` **Generic conclusions.** "The future looks bright." State specific plans or facts.

- `48` `both` **Formulaic wrap-ups.** The rigid closer: a "Challenges" paragraph opening "Despite its..., X faces several challenges", a "Future Prospects" section, an "In summary" paragraph restating what is above. Cut them; end where the content ends.

- `50` `both` **Didactic disclaimers.** "It's important to note...", "It is crucial to remember...", "may vary": advice to an imagined reader wrapped around a fact. Drop the wrapper, and keep the fact if it earns its place.

## Jargon

- `26` `both` **Abstract metaphor nouns.** Substrate, wedge, vector, locus, vantage, nexus, primitive (as noun), harness (as metaphor), surface (as in "API surface"), bedrock, scaffolding (as metaphor), modality, paradigm, gold-plating, ratchet (as metaphor), evacuate (for moving code), endgame, north star, flywheel. They read as technical where a plainer concrete word exists; use it: "base" for "substrate", "add" for "wedge in", "way" or "method" for "vector", "more than the job needs" for "gold-plating", the mechanism's real name or "a limit that only tightens" for "ratchet", "move out" for "evacuate", "the last phase" for "endgame". A term of art in its literal sense (a test harness, an attack surface) or a term the project's glossary defines is not a hit.

- `35` `both` **Coined labels.** A catchy or proprietary-sounding name invented for an idea ("the clarity engine", "the trust ladder") and then used as if the reader knew it. Say the thing plainly. A genuinely new concept the text keeps returning to earns one term, defined where it first appears and used unchanged after; a term the project has defined (a glossary entry, a spec's own name for a thing) already is that case.

- `55` `both` **Assumed familiarity.** A term, reference or named idea the reader would have to look up or scroll back for: "as the handoff said", "per the Ousterhout split", "the usual CAP trade-off", an established term never explained. Overestimate the reader's intelligence and underestimate their vocabulary, of concepts, references and named ideas as much as words. The reader has only what is in front of them: for a chat reply, the reply, not an earlier turn; for an artifact, the artifact itself and where it sits, not the conversation that produced it. Watch most for tool results and files the writer read, what an earlier turn or the user said (above all where it was fuzzy), the writer's own coinages (rule 35; a referent the text never introduced is rule 52), external docs and literature (even what the user sent), and any "popular" concept name-dropped. Make the thing usable where it appears, with a few words inline, a sentence, an example, a comparison or a before / after, or restate plainly a thing the reader never saw (an earlier turn, a file, a doc) instead of naming it. A text that leans on several such terms can end on a table of them with short definitions. A technical term stays rather than giving way to a paraphrase, explained on first use unless the reader clearly knows it.

## Plain speech

- `27` `both` **Say what it does, not how it feels.** "the database stays close at hand", "SQL you can read", "types that follow your schema" name a feeling; "This is genuinely hard" and "this is what leadership actually looks like" tell the reader what to conclude. Name the mechanism or a number instead: "`.toSQL()` returns the exact string sent to the database", "a column rename fails the build". Write what the sentence tells the reader to do or know; cut a sentence you cannot restate as a concrete instruction, fact or number, and one that could appear unchanged in another project's docs.

- `28` `both` **Shorten or split dense sentences.** If the reader has to backtrack to parse a sentence, break it in two or drop clauses. One idea per sentence.

- `29` `both` **Active voice.** Catch "is/are/was/were + past participle" and name the actor: "queries are validated" becomes "the compiler validates queries", "the file is parsed by the loader" becomes "the loader parses the file". Passive is fine only when the actor is unknown or does not matter.

- `30` `both` **Cut adverbs, or use a stronger verb.** "runs quickly" becomes "is fast" or the number. "significantly improves" becomes the measured delta. An adverb propping up a weak verb means the verb is wrong. Frequent offenders: really, just, literally, genuinely, honestly, simply, actually, deeply, truly, fundamentally, inherently, inevitably, interestingly, importantly, crucially.

- `31` `both` **Prefer the plain word.** An inflated word where a plain one means the same: "utilize" becomes "use", "leverage" becomes "use", "facilitate" becomes "help", "numerous" becomes "many", "in the event that" becomes "if". The plain word is the shortest one that says exactly the thing to this reader, so a precise technical term the reader holds is the plain word: "the service is now idempotent" stays, and "the service now does the same thing when it is run twice" is the hit. A term the reader may not hold stays too, explained on first use (rule 55).

- `32` `both` **Mannered prose.** Metaphor or flourish where a literal phrase exists: aphorisms ("wire it or delete it"), rhetorical fragments for effect, personified code ("the plan holds it"), figurative verbs ("rides along", "stands on", "creeps in"), stock framing phrases ("X is a feature, not a bug", "dressed up as"), performative asides ("they exist, I promise"), every paragraph ending on a punch. "A dial worth turning" becomes "a parameter worth varying". Say what you mean. Rule 26 covers the metaphor nouns.

- `33` `both` **Over-compression.** Dropped articles, verbless fragments, symbol-speak, and abbreviations that make the reader decode instead of read. "Parser rejects bad date → exit 2, no write" becomes "The parser rejects a bad date, exits with code 2, and writes nothing." Write whole sentences with their articles and verbs, and spell out arrows and abbreviations; an abbreviation the reader uses as a word (API, CPU) is a term, and stays.

- `52` `both` **Unintroduced referent.** A definite noun phrase for a thing the text never names: "the card", "the page", "the file", where the reader has met no card, page or file. Name it in full where it first appears; the short form carries it after that.

- `37` `both` **Nominalizations.** A verb turned into a noun with a weak verb propping it up: "a reduction in latency was achieved through the elimination of redundant lookups" becomes "removing redundant lookups cut latency". Give the action back to the verb.

- `38` `both` **Noun stacks.** Three or more nouns in a row that the reader has to unpack: "database connection pool exhaustion" becomes "the connection pool ran out of connections". Break the stack with a verb or a preposition.

- `39` `both` **Generalities and platitudes.** A sentence that would be true of any project or any situation ("good tooling matters", "this improves maintainability", "it depends on the use case"), or one that announces importance without naming the thing ("the implications are significant", "the stakes are high", "the reasons are structural"). Replace it with the specific fact, number or consequence, or cut it. Lazy extremes (every, always, never, everyone, nobody) are the same move: name the specifics.

- `43` `both` **False agency.** Human verbs given to inanimate things, which is how a sentence avoids naming the actor. "A complaint becomes a fix" becomes "the team fixed it that week". "The decision emerges" becomes "the lead decides". "The culture shifts" becomes "people change what they do". "The data tells us" becomes "we read the data and concluded". Name the actor and put them at the front.

- `44` `artifact` **Narrator-from-a-distance.** "Nobody designed this.", "This happens because...", "People tend to...": a narrator generalizing from outside the case at hand. State the fact about this case: "People tend to skip the tests" becomes "Most PRs in this repo skip the tests".
