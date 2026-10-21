# A {{kind}}: read fresh

You run the read-fresh stage of a {{kind}} of `{{repo}}`, over {{sessions}}, from {{since}} to {{until}}. Its job is to read the period with fresh eyes: what went wrong for max and for the agents, and the cause behind each of max's corrections, quoted and dated, before anyone looks at what earlier retros found. The later stages compare your notes with the standing findings; your notes are worth most when they come from the sessions alone.

The retro's repos, whose git `git/` records:

{{repos}}

Everything you read and write is in the run directory, `{{run}}`, your working directory:

- `batches.json`: the session digests in batches, each a name, a list of digest paths and its size in characters. The period's batches are `batch-01`, `batch-02`, …; the older sample's, where there is one, are `sample-01`, `sample-02`, …, and hold {{sample}}.
- `sessions/` and `sample/`: one digest per session.
- `git/<repo>.md`: each repo's commits in the period, its reverts, and where it has an agent repo, the tickets filed, every status change, the tickets deleted and the worker reports committed.

## Steps

1. Read `batches.json`. Spawn one subagent per batch and one for `git/`, in parallel, each given the reader's brief below: the path of this prompt, `{{run}}/prompts/read-fresh.md`, the section to follow, its batch's name and digest paths (or `git/`), and the file to write: `notes/<batch name>.md`, or `notes/git.md`. Reading the digests is theirs: your own context stays free for the batches.
2. When they return, check that every batch and `git/` has its notes file and that each holds a section per digest. Spawn a fresh subagent for any that is missing or cut short.

The stage is done when `notes/` holds a file for every batch in `batches.json` and one for `git/`.

## The reader's brief

You read part of a {{kind}}'s period, from {{since}} to {{until}}, to find the friction worth fixing and the cause behind each of max's corrections. A batch named `sample-…` holds older sessions instead, from before the period, read the same way: what they show tells the later stages whether a pattern is older than the period. Read every file you were given in full, in order, before you write; a digest longer than one read is read in parts, to its end. Then write your notes file, once.

### What to look for

Two sides, alike in weight. What cost max time, attention or nerves, read from his own messages and from what he was shown. What made an agent slower, costlier or less successful.

Read every correction of max's for its cause. A correction is a message of his that sets right what an agent did, said, was about to do or showed him: he rejects an approach, points at a mistake, restates a rule, redirects the work, supplies a fact, or asks what he is looking at. `MAX INTERRUPTED` followed by his next message is one, as is `MAX REWOUND and re-sent`, whose abandoned turn is what he corrected. Read it in both directions, what made the agent go wrong and what made the agent hard for him to follow, and name the cause as one of:

- **workflow**: a skill, a prompt, a hook or the harness steered the agent there;
- **codebase**: a shape of the code invited the mistake;
- **environment**: the obvious way was not to be seen from the repo, its commands or its tools;
- **shown**: how the work was shown to max left him unable to tell what was built, what was decided, or what he had to do;
- **guidance**: guidance covering it existed, and the agent missed it or could not follow it;
- **fact**: the agent lacked a fact max had to supply.

In a repo retro, a session read may have worked on other repos too: its notes hold the friction and corrections of the work in the retro's repos, those whose cause is the workflow among them, with the skill named in their Cause.

### The digest

One file per session. Its header names the session id, title, project, profile, span, how many messages max wrote, and the models and Claude Code versions it ran. Then, under a heading per day, each line carries its time, UTC:

- `MAX:` what max typed, verbatim, pasted text clipped in the middle. `(queued while the agent worked)`: he typed while the agent was busy. `MAX REWOUND and re-sent`: he rewound to before his previous message and sent a new version; what the abandoned turn did is often why. `MAX INTERRUPTED`: he stopped the agent mid-turn.
- `A:` the model's text. `→ <tool> <input>`: a tool call and its full input, `[classifier allowed]` after the tool where auto mode's classifier judged it and let it run; tool output is left out.
- `! ERROR`, `! DENIED`: a failed or refused tool call, in full. `! HOOK → agent`, `! STOP HOOK`: a hook that sent the turn back. `! API ERROR`.
- `(turn took 4m12s)`, `(context compacted)`, and `(left out: …)` where a long session's days before the period were cut.
- `## Session page: …` closes a digest that has them: the session page's records, what max was shown of the session.

A git record lists commits with their messages, reverts, ticket changes and worker reports.

### The notes

```markdown
# Notes: <batch name>

## <session id, first 8 characters> · <project, short> · <date> · <what the session was about, one line>

Outcome: done | partial | abandoned | unclear, and what came out, in one clause.

- **[max|agents] <what happened, in a few words of the session's own>** (low|med|high) What happened and what it cost, in one or two sentences. Evidence: "<verbatim quote>" (<session id, 8 characters>, <date>). Cause: <the skill line, script, config or habit that produced it, where you can tell>.
- **[correction · workflow|codebase|environment|shown|guidance|fact] <what he corrected, in a few words>** (low|med|high) What the agent did before it, with the call or text that drew it, and what max said. Evidence: "<his words, verbatim>" (<session id, 8 characters>, <date>). Cause: <the skill line, file, shape, command, guidance or missing fact, by path where it is a file>.
- **[works]** Something that clearly worked and is worth keeping, with its quote. At most two per session.

## Patterns in this batch

Friction that recurs, and corrections that share a cause, across two or more of these sessions, naming each session and the date.
```

Each finding carries a verbatim quote and its absolute date, copied from the digest; a finding you cannot quote stays out. Cost is your estimate of what it cost: `high` for many minutes or much nerve lost, `med` for a detour, `low` for a papercut. A session with no friction gets its heading and its outcome line alone. The concrete beats the general: "max pasted the board's URL by hand three times because the Stop hook printed no link" carries the fix; "observability could be better" carries nothing. For `git/`, the sections are the repos, and the quotes are commit subjects and report lines with their short sha or ticket and date.

Write the notes file at the path you were given, then reply with that path alone.
