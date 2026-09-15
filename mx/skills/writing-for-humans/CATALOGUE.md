# AI prose tells

The catalogue every prose reviewer sweeps against: the Standards axis on a diff, the chat reviewer on a reply, `/mx:writing-for-humans` on a file. A rule about punctuation or formatting binds hard; every other rule is a named heuristic, so a finding cites the id, quotes the hit and names the fix rather than asserting a violation, and a documented repo standard wins where it endorses what a rule would flag. One match may be coincidence; several co-occurring is the tell.

Each rule is one block: a bullet carrying its id, its scope tag and its name, plus the lines indented under it. Ids are permanent and cited from elsewhere, so they do not run in order, and a removed rule leaves a gap. The scope tag says where the rule's fix belongs: `artifact` for text that ships in a file, `chat` for a reply the user reads, `both` where the fix improves either. One scope is selectable without reading the rest, here the rules a chat reviewer applies:

```
awk '/^#/{k=0} /^- `/{k=($3=="`chat`"||$3=="`both`")} k' CATALOGUE.md
```

Credit: [Hardik Pandya](https://hvpandya.com), [github.com/hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop) (MIT), and [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing).

## Content

- `3` `both` **Superficial -ing phrases.** "highlighting...", "ensuring...", "reflecting...", "showcasing...", "fostering...": a present participle bolted onto a fact to append analysis it has not earned. End the sentence at the fact. Analysis that matters gets its own sentence with its own sources.

- `5` `both` **Vague attributions.** "Experts believe", "Industry reports suggest", "Some critics argue", "widely regarded", "observers have cited". An opinion inflated onto an unnamed authority, or one source presented as many. Name the source or delete.

- `49` `both` **Source-gap speculation.** "While specific details are not widely documented...", "based on available information", followed by what the missing facts "likely" are. The gap claim is itself unverified and the filler after it is fabrication. State what the sources say, stop where they stop.

## Language

- `7` `both` **AI vocabulary.** Additionally, commitment to, crucial, delve, diverse array, enduring, enhance, fostering, garner, groundbreaking, interplay, intricate, landscape (abstract), meticulous, nestled, pivotal, renowned, rich, robust, seamlessly, showcase, tapestry (abstract), testament, underscore, vibrant. Replace with plain words. Each is fine alone; a cluster is the fingerprint. The same words inflate significance ("stands as a testament", "a pivotal moment", "underscores its importance"): state the fact and let the reader judge how much it matters.

- `8` `both` **Fancy ways to say "is".** "serves as", "stands as", "functions as", "represents", "boasts", "features", "offers", "refers to". Just say "is" or "has".

- `9` `both` **"Not just X, but Y."** Including "not only X, but also Y" and "doesn't just X, it Y". State the point directly instead.

- `10` `both` **Rule of three.** Forcing ideas into groups of three. Use the natural number.

- `11` `both` **Synonym cycling.** Protagonist, main character, central figure, hero all in one paragraph. Pick one, repeat it.

- `12` `both` **False ranges.** "from X to Y" where X and Y aren't on a meaningful scale. List topics directly.

- `41` `both` **Business jargon.** "Navigate" (challenges) becomes "handle" or "address". "Unpack" (an analysis) becomes "explain" or "examine". "Lean into" becomes "accept". "Landscape" (context) becomes "situation" or "field". "Game-changer" becomes "significant". "Double down" becomes "commit". "Deep dive" becomes "analysis". "Take a step back" becomes "reconsider". "Moving forward" becomes "next". "Circle back" becomes "return to".
  Before: "In today's fast-paced landscape, we need to lean into discomfort and navigate uncertainty with clarity. This matters because your competition isn't waiting." After: "Move faster. Your competition is."

## Style

- `13` `both` **Em dash overuse.** Avoid em dashes entirely. Use periods or commas only (no parentheses, no en dashes, no hyphen-as-dash substitutes). If a thought needs separation, end the sentence or use a comma.

- `14` `both` **Colon overuse.** Colons are fine before a list or example. Not as mid-sentence connectors. "If you're coming from traditional automation: instead of registering event handlers, you describe conditions" adds nothing with the colon. Rewrite to let the point stand on its own without comparison framing. "Describing when the scheduler should fire works best as plain English." Same meaning, no crutch punctuation.

- `15` `both` **Boldface overuse.** Don't bold every proper noun or acronym.

- `16` `both` **Inline-header lists.** The tell is a bold label and colon that restates the line: "**Performance:** Performance improved...". Convert those to prose. A table carrying what three sentences carry is the same tell.
  A bold lead-in is the permitted form: a few bold words at the start of a paragraph or bullet that name what it is about, end in a period, and are followed by genuinely new detail ("**Schema in TypeScript.** Tables live in one file."). It is a signpost for skimming, not an opener (34), a coined label (35) or meta-commentary (36); do not report it under those rules either.

- `17` `both` **Title case headings.** Use sentence case.

- `18` `both` **Decorative emojis.** Remove from headings and bullets.

- `19` `both` **Curly quotes.** Replace with straight quotes.

## Structures

- `40` `both` **Emphasis crutches.** "Full stop.", "Period.", "Let that sink in.", "Make no mistake", "This matters because", "Here's why that matters". They add no meaning. Delete them.

- `42` `both` **Rhetorical setups.** "What if [reframe]?", "Here's what I mean:", "Think about it:", "And that's okay.", a question posed and answered in the next breath. Make the point and let the reader draw the conclusion.
  Before: "What if I told you that the best teams don't optimize for productivity? Here's what I mean: they optimize for learning. Think about it." After: "The best teams optimize for learning, not productivity."

- `45` `both` **Dramatic fragmentation.** "[Noun]. That's it. That's the [thing].", "X. And Y. And Z.", "This unlocks something. [Word].", short sentences stacked for rhythm. Write complete sentences and trust the content over the presentation.
  Before: "Speed. Quality. Cost. You can only pick two. That's it. That's the tradeoff." After: "Pick two of speed, quality and cost."

- `46` `both` **Negative listing.** Listing what something is not before revealing what it is: "Not a X... Not a Y... A Z.", "It wasn't X. It wasn't Y. It was Z." State Z. The reader doesn't need the runway.

- `47` `both` **Binary contrasts.** "Not because X. Because Y.", "[X] isn't the problem. [Y] is.", "The answer isn't X. It's Y.", "It feels like X. It's actually Y.", "stops being X and starts being Y". They create false drama. State Y directly and drop the negation.
  Before: "Here's the thing: building products is hard. Not because the technology is complex. Because people are complex. Let that sink in." After: "Building products is hard. Technology is manageable. People aren't."

## Communication artifacts

- `20` `both` **Chatbot phrases.** "I hope this helps!", "Let me know if...", "Of course!", "Certainly!", "Found the smoking gun!", "Would you like me to...", and knowledge-cutoff disclaimers ("As of my last update"). Remove. In a file they are assistant-turn residue: delete on sight.

- `22` `both` **Sycophantic tone.** "Great question! You're absolutely right!" Respond directly.

- `34` `both` **Throat-clearing and closers.** An opener that announces instead of starting ("Here's the thing:", "Here's why X", "The uncomfortable truth is", "It turns out", "The real X is", "Let me be clear", "Let me explain", "I'm going to be honest", "Can we talk about", "Look,", a paragraph opening with "So"), or a closing sentence that offers further work instead of stopping. Start with the answer, stop when the content stops. Rules 20 and 22 carry the phrases themselves.

- `36` `both` **Meta-commentary about the text itself.** Sentences about how it is structured or how it follows a style: "To keep this brief", "In short, as requested", "Here's a quick summary of what I did", "Hint:", "Plot twist:", "Spoiler:", "The rest of this essay explains...", "Let me walk you through...", "In this section, we'll...", "As we'll see...", "You already know this, but", "But that's another post". Delete; the reader sees the structure.

- `51` `artifact` **Unfilled placeholders.** "[Your Name]", "2025-XX-XX", "PASTE_URL_HERE": template blanks that shipped. Sweep for brackets and XX before delivering.

## Filler

- `23` `both` **Filler phrases.** "In order to" becomes "To". "Due to the fact that" becomes "Because". "It is important to note that", "At its core", "In today's X", "It's worth noting", "At the end of the day", "When it comes to", "In a world where" and "The reality is" get deleted.
  Before: "It turns out that most teams struggle with alignment. The uncomfortable truth is that nobody wants to admit they're confused. And that's okay." After: "Teams struggle with alignment. Nobody admits confusion."

- `24` `both` **Excessive hedging.** "could potentially possibly be argued that it might" becomes "may".

- `25` `both` **Generic conclusions.** "The future looks bright." State specific plans or facts.

- `48` `both` **Formulaic wrap-ups.** The rigid closer: a "Challenges" paragraph opening "Despite its..., X faces several challenges", a "Future Prospects" section, an "In summary" paragraph restating what is above. Cut them; end where the content ends.

- `50` `both` **Didactic disclaimers.** "It's important to note...", "It is crucial to remember...", "may vary": advice to an imagined reader wrapped around a fact. Drop the wrapper, keep the fact if it earns its place.

## Jargon

- `26` `both` **Abstract metaphor nouns.** Substrate, wedge, vector, locus, vantage, nexus, primitive (as noun), harness (as metaphor), surface (as in "API surface"), bedrock, scaffolding (as metaphor), modality, paradigm, gold-plating, ratchet (as metaphor), evacuate (for moving code), endgame, north star, flywheel. These read as technical but usually have a plainer concrete word. "Substrate" becomes "base". "Wedge in" becomes "add". "Vector" becomes "way" or "method". "Gold-plating" becomes "more than the job needs". "Ratchet" becomes the mechanism's real name or "a limit that only tightens". "Evacuate" becomes "move out". "Endgame" becomes "the last phase". Pick the concrete word.

- `35` `both` **Coined labels.** A catchy or proprietary-sounding name invented for an idea ("the clarity engine", "the trust ladder") and then used as if the reader knew it. Say the thing plainly. A genuinely new concept the text keeps returning to earns one term, defined where it first appears and used unchanged everywhere after, and a term the project has defined (a glossary entry, a spec's own name for a thing) is that case already.

## Plain speech

- `27` `both` **Say what it does, not how it feels.** "the database stays close at hand", "SQL you can read", "types that follow your schema" name a feeling. "This is genuinely hard" and "this is what leadership actually looks like" tell the reader what to conclude. The fix names the mechanism or a number: "`.toSQL()` returns the exact string sent to the database", "a column rename fails the build". Ask what the sentence tells the reader to do or know, then write that. If you can't restate it as a concrete instruction, fact, or number, cut it. One more check: if the sentence could appear unchanged in another project's docs, it says nothing about this one. Cut it.

- `28` `both` **Shorten or split dense sentences.** If the reader has to backtrack to parse a sentence, break it in two or drop clauses. One idea per sentence.

- `29` `both` **Active voice.** Prefer it. Catch "is/are/was/were + past participle" and name the actor: "queries are validated" becomes "the compiler validates queries", "the file is parsed by the loader" becomes "the loader parses the file". Passive is fine only when the actor is unknown or genuinely doesn't matter.

- `30` `both` **Cut adverbs, or use a stronger verb.** "runs quickly" becomes "is fast" or the number. "significantly improves" becomes the measured delta. An adverb propping up a weak verb means the verb is wrong. The frequent offenders: really, just, literally, genuinely, honestly, simply, actually, deeply, truly, fundamentally, inherently, inevitably, interestingly, importantly, crucially.

- `31` `both` **Prefer the plain word.** "utilize" becomes "use", "leverage" becomes "use", "facilitate" becomes "help", "numerous" becomes "many", "in the event that" becomes "if". The fancier synonym is rarely clearer.

- `32` `both` **Mannered prose.** Metaphor or flourish where a literal phrase exists: aphorisms ("wire it or delete it"), rhetorical fragments for effect, personified code ("the plan holds it"), figurative verbs ("rides along", "stands on", "creeps in"), stock framing phrases ("X is a feature, not a bug", "dressed up as"), performative asides ("they exist, I promise"), every paragraph ending on a punch. "A dial worth turning" becomes "a parameter worth varying". Say what you mean. Rule 26 covers the metaphor nouns.

- `33` `both` **Over-compression.** Dropped articles, verbless fragments, symbol-speak, and abbreviations that make the reader decode instead of read. "Parser rejects bad date → exit 2, no write" becomes "The parser rejects a bad date, exits with code 2, and writes nothing." Write whole sentences with their articles and verbs, and spell out arrows and abbreviations.

- `37` `both` **Nominalizations.** A verb turned into a noun with a weak verb propping it up: "a reduction in latency was achieved through the elimination of redundant lookups" becomes "removing redundant lookups cut latency". Give the action back to the verb.

- `38` `both` **Noun stacks.** Three or more nouns in a row that the reader has to unpack: "database connection pool exhaustion" becomes "the connection pool ran out of connections". Break the stack with a verb or a preposition.

- `39` `both` **Generalities and platitudes.** A sentence that would be true of any project or any situation ("good tooling matters", "this improves maintainability", "it depends on the use case"), or one that announces importance without naming the thing ("the implications are significant", "the stakes are high", "the reasons are structural"). Replace it with the specific fact, number or consequence, or cut it. Lazy extremes (every, always, never, everyone, nobody) are the same move: name the specifics.

- `43` `both` **False agency.** Human verbs given to inanimate things, which is how a sentence avoids naming the actor. "A complaint becomes a fix" becomes "the team fixed it that week". "The decision emerges" becomes "the lead decides". "The culture shifts" becomes "people change what they do". "The data tells us" becomes "we read the data and concluded". Name the actor and put them at the front.

- `44` `artifact` **Narrator-from-a-distance.** "Nobody designed this.", "This happens because...", "People tend to...". Put the reader in the room: "You don't sit down one day and decide to..." beats "Nobody designed this."
