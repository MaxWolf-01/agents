# A repo retro: read corrections

You run the read-corrections stage of a repo retro of `{{repo}}`, over the period from {{since}} to {{until}}. Its job is to gather max's corrections from the period's sessions worked in the repo, each with what the agent did before it, so that the lens pass can trace a mistake that recurs to what in the repo invites it, and propose the check that would have caught it. Your notes come from the sessions alone, before anyone looks at what earlier retros found.

Everything you read and write is in the run directory, `{{run}}`, your working directory:

- `batches.json`: the session digests in batches, each a name, a list of digest paths and its size in characters, named `batch-01`, `batch-02`, ….
- `sessions/`: one digest per interactive session that, in the period, ran in `{{repo}}` or one of its worktrees, or made a tool call naming a path inside one. Such a session may have worked on other repos too.

## Steps

1. Read `batches.json`. With no batch in it, no session was worked in the repo in the period: write `corrections.md` saying so, and stop.
2. Spawn one subagent per batch, in parallel, each given the reader's brief below: the path of this prompt, `{{run}}/prompts/read-corrections.md`, the section to follow, its batch's name and digest paths, and the file to write, `corrections/<batch name>.md`. Reading the digests is theirs: your own context stays free for the merge.
3. When they return, check that every batch has its file and that each holds a section per digest. Spawn a fresh subagent for any that is missing or cut short.
4. Write `corrections.md` from the files in `corrections/`: every correction they hold, grouped by the mistake it corrects, two corrections in one group when one fix in the repo would have spared max both. A group seen in two or more sessions comes first, then the corrections seen once. Copy each correction's line as its batch file has it.

```markdown
# Corrections in the sessions worked in <repo>, <start> to <end>

## <the mistake, in a few words>

Seen in <n> sessions. <What the agents kept doing, in a sentence, and the part of the repo it concerns.>

- <the correction's line>

## Seen once

- <the correction's line>
```

The stage is done when `corrections/` holds a file for every batch in `batches.json` and `corrections.md` holds every correction those files hold.

## The reader's brief

You read part of the period's sessions worked in `{{repo}}`, from {{since}} to {{until}}, for max's corrections. Read every file you were given in full, in order, before you write; a digest longer than one read is read in parts, to its end. Then write your file, once.

### A correction

A message of max's that sets right what an agent did, said or was about to do in `{{repo}}`: he rejects an approach, points at a mistake, restates a rule the agent broke, or redirects the work. `MAX INTERRUPTED` followed by his next message is one, as is `MAX REWOUND and re-sent`, whose abandoned turn is what he corrected, and a `! DENIED` call whose message gives his reason. A correction of work on another repo stays out, as does a message that asks, approves or adds a request.

### The digest

{{digest}}

### The notes

```markdown
# Corrections: <batch name>

## <session id, first 8 characters> · <date> · <what the session was about, one line>

- **<the mistake, in a few words>** "<max's words, verbatim>" (<session id, 8 characters>, <date>). Before it: <what the agent did, with the call or text that drew the correction quoted>. Where: <the file, command or part of the repo it concerns>.
```

Each correction carries max's words verbatim and its absolute date, copied from the digest; one you cannot quote stays out. A session with no correction of work in the repo gets its heading and the line "No correction." alone.

Write the notes file at the path you were given, then reply with that path alone.
