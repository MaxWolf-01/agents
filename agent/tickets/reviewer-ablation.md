---
status: open
size: M
priority: 4
---

# Ablate the prose reviewer against labelled replies

## Brief

The turn-record prose reviewer ships on one model at one effort with nothing measured. One command runs the matrix over labelled texts and reports validity, recall, cost and time, so a new model can be re-measured.

Asked for by max on 2026-09-23, at low priority, while the session-page spec moved the prose review from the chat reply onto the turn record (`session-page/spec.md`, Producing the pages). The turn review ships with Opus 5.5 at medium effort and without an ablation; this ticket measures what the choice of model, effort, prompt and context actually buys, and gives a way to re-measure when a new model ships.

Max 23-09-26;1900: I think we prlly should just use opus everywhere by default, just yk use the thinking budget for steering the cost/test time compute. Tho for session index and diffview summary, sonnet might be fine. tho idk, if 5.5 can write / communicate better... why not opus low effort... we can do a cost comparison too. prlly it's not that much, and like prices and plan limits keep getting better anyways? kinda. idk.

## What to build

One command that runs a matrix of reviewer configurations over a labelled set of texts and reports, per configuration and per catalogue rule, the share of findings that are valid, marginal and false, recall against the labelled faults, the cost and the time. The axes are the model, the reasoning effort from low to max, the prompt's version, and the context the reviewer sees (the text alone, or with the session's earlier turns and the user's messages). The set is the chat-review audit's, extended with turn records once the session page produces them.

The audit's material is in `/var/tmp/wf-analysis/proto/`: its scripts, prompts and labels, from 603 live chat-review decisions (15 to 22 September), 9 reviewer configurations run on the same 151 replies, and 1,030 findings labelled by blind Opus judges. `/var/tmp` is not backed up, so the material moves first, to `~/logs/agent/agents/`, where retired research already goes. The judges were never calibrated: max labels a sample by hand before their labels are trusted.

What the audit found, all of it on uncalibrated labels:

- The live hook (Haiku, the catalogue's chat rules) was 9% valid and 80% false, mostly by flagging the structure the output style requires ("I need from you", bold lead-ins, tagged items) through rules 16, 34 and 36.
- The model mattered more than the prompt. On the same prompt Haiku reached at most 19% valid and Sonnet 23%; Opus 5.5 reached 47% on the reply alone, and 49% valid, 13% false and 59% recall with the conversation as context, at about $0.02 against $0.10 per review and 8 to 9 seconds either way.
- Rule 52 (an unintroduced referent) is judgeable only with the conversation, and only Opus used the conversation well: Haiku and Sonnet used it to flag more of what the user had in fact already met.
- Rules that earned their place: asks and offers outside the questions list, mannered prose (32), session bookkeeping (36), and 52 with context. Rules that did not: 16 (a labelled list of distinct facts scans better than prose), 8, 23, 37, 38, 43; coined labels (35) stayed weak.
- Faults outside the catalogue mattered as much: a reply that ignores the user's latest message, a tag reused within a session, a count that does not match its list ("the three calls" followed by four).
- Wording in a skill gets copied into prose: `dispatch/SKILL.md`'s "tags renumbered to continue this session's" came back in live replies as "tags continuing this session's".

Not in it: mechanical checks for punctuation such as em dashes or curly quotes, which max ruled out on 2026-09-23.

## Acceptance criteria

- [ ] The audit's material is moved out of `/var/tmp` and the command reads it from there.
- [ ] One command runs a named matrix of configurations and writes one report comparing them, per configuration and per rule.
- [ ] Max has labelled a sample by hand, and the report says how far the judges' labels agree with his.
- [ ] The closing comment recommends the turn review's model, effort and context from the numbers, and says what the recommendation would change in `session-page`'s reviewer.
- [ ] Demo: the command run on a small matrix, the report opened.
