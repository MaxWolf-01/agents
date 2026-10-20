# A workflow retro: read fresh

You run the read-fresh stage of a workflow retro over max's Claude Code sessions from {{since}} to {{until}}. Its job is to read the period with fresh eyes: what went wrong for max and for the agents, quoted and dated, before anyone looks at what earlier retros found. The later stages compare your notes with the standing findings; your notes are worth most when they come from the sessions alone.

Everything you read and write is in the run directory, `{{run}}`, your working directory:

- `batches.json`: the session digests in batches, each a name, a list of digest paths and its size in characters. The period's batches are `batch-01`, `batch-02`, …; the older sample's, where there is one, are `sample-01`, `sample-02`, …, and hold {{sample}}.
- `sessions/` and `sample/`: one digest per session.
- `git/<repo>.md`: each repo's commits in the period, its reverts, and where it has an agent repo, the tickets filed, every status change, the tickets deleted and the worker reports committed.

## Steps

1. Read `batches.json`. Spawn one subagent per batch and one for `git/`, in parallel, each given the reader's brief below: the path of this prompt, `{{run}}/prompts/read-fresh.md`, the section to follow, its batch's name and digest paths (or `git/`), and the file to write: `notes/<batch name>.md`, or `notes/git.md`. Reading the digests is theirs: your own context stays free for the batches.
2. When they return, check that every batch and `git/` has its notes file and that each holds a section per digest. Spawn a fresh subagent for any that is missing or cut short.

The stage is done when `notes/` holds a file for every batch in `batches.json` and one for `git/`.

## The reader's brief

You read part of a workflow retro's period, from {{since}} to {{until}}, to find the friction worth fixing. A batch named `sample-…` holds older sessions instead, from before the period, read the same way: what they show tells the later stages whether a pattern is older than the period. Read every file you were given in full, in order, before you write; a digest longer than one read is read in parts, to its end. Then write your notes file, once.

### What to look for

Two sides, alike in weight. What cost max time, attention or nerves, read from his own messages and from what he was shown. What made an agent slower, costlier or less successful.

### The digest

{{digest}}

A git record lists commits with their messages, reverts, ticket changes and worker reports.

### The notes

```markdown
# Notes: <batch name>

## <session id, first 8 characters> · <project, short> · <date> · <what the session was about, one line>

Outcome: done | partial | abandoned | unclear, and what came out, in one clause.

- **[max|agents] <what happened, in a few words of the session's own>** (low|med|high) What happened and what it cost, in one or two sentences. Evidence: "<verbatim quote>" (<session id, 8 characters>, <date>). Cause: <the skill line, script, config or habit that produced it, where you can tell>.
- **[works]** Something that clearly worked and is worth keeping, with its quote. At most two per session.

## Patterns in this batch

Friction that recurs across two or more of these sessions, naming each session and the date.
```

Each finding carries a verbatim quote and its absolute date, copied from the digest; a finding you cannot quote stays out. Cost is your estimate of what it cost: `high` for many minutes or much nerve lost, `med` for a detour, `low` for a papercut. A session with no friction gets its heading and its outcome line alone. The concrete beats the general: "max pasted the board's URL by hand three times because the Stop hook printed no link" carries the fix; "observability could be better" carries nothing. For `git/`, the sections are the repos, and the quotes are commit subjects and report lines with their short sha or ticket and date.

Write the notes file at the path you were given, then reply with that path alone.
