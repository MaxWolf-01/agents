# An issue upstream

Turn a finding into an issue its maintainers can act on. Load `/mx:writing-for-agents` beside writing-for-humans, since their agents read it too.

## Earn the filing

**Reproduce every claim.** A report whose assertions were never run costs the
maintainer more than it saves them, and it spends max's reputation. State the
version you ran.

**Search the tracker, closed issues included.** A fixed bug means the answer is
"upgrade"; a rejected one means the behaviour is intended. `gh search issues` and
`gh issue list --state all` both take a repo.

**Read the project's rules.** `CONTRIBUTING`, the issue templates, any policy on
AI-assisted reports. Where a project rejects those, that decision is theirs and it
is max's account that would break it.

**Check what the templates allow.** `blank_issues_enabled: false` means the listed
forms are the only route. A required checkbox is a statement the filer makes: a
documentation gap goes on the form that fits it, which is rarely the one asking
you to affirm you found a bug.

**Drill down to a minimal reproduction.** The state you happened to hit it in is
the starting point, not the report. Strip the setup one piece at a time until only
what triggers it remains, and each removal that keeps the bug alive is one less
thing the maintainer has to rule out. This mostly settles the privacy question on
its own: a minimal case rarely contains anything of max's.

The files in the report are the files you ran: build the repro in an empty
directory, run it there, and paste that directory and its output. A repro
assembled afterwards out of a larger project reports numbers its own code cannot
produce.

Some findings resist it: a race, something that needs the real data, a crash you
saw once. Then the report is the observation plus its log or stack trace, said
plainly as a single occurrence.

## Filing

Drilling down is slow and mostly mechanical, so hand it to a subagent and carry on
with the session's real work. Give it the finding, the repo, this skill and this
file, and name the file it writes to, `agent/research/upstream-<repo>-<slug>.md`,
holding the body, written per [The body](#the-body), the duplicate search, and
whatever it could not verify. It writes that file; it never files the issue.

The main session then **sanity checks** the body against what the session actually
knows, since the subagent worked from a brief and can have drifted, and takes it
through the skill's publishing gate. After max's yes: `gh issue create -R <repo>
--body-file <file>` with the label the template assigns.

A gate that does not pass sends it round again: another subagent round when the
gap is real work, a direct edit and a fresh yes when it is wording. A finding the
session later invalidates, or max judges not worth filing, is dropped; the work
already paid for itself by being understood.

## The body

It opens with the disclaimer, then the finding: expected against actual, or, for a
request, the ask itself. The evidence a reader checks only if they doubt you, the
repro's files, commands and output, a stack, a probe of the cause, goes inside
`<details>` blocks.

Where a template exists, fill **its** fields. The maintainers wrote it to get what
they need, and a foreign structure laid over it reads as not having looked.

Where none exists, use this order, the same information a good template asks for:

- **What happens**: one plain sentence.
- **Why it matters**: what it costs someone. A bug: what breaks, and what a
  caller can do about it. A gap: what it made you believe that was untrue.
- **How to reproduce**: exact steps on a stated version. A table of inputs
  against results carries a boundary better than prose does.
- **Cause**, only with evidence in hand: a log line, a traced code path. Anything
  short of that stays out.

One report per problem. Several one-line corrections to the same document are one
report; a crash and a documentation gap are two.

These headings are available, not owed. A section you have nothing behind is a
section to drop; inventing a cause or a consequence to fill one is the failure
this skill exists to prevent, and a maintainer spots it immediately.

The value judgements that belong in an issue are the ones only max can make:
expected against actual, and why it cost him something.

## Fix direction

Report the finding and leave the fix to the maintainer. They know the codebase,
they have their own agents, and they will find a better fix than an outsider
working from one afternoon of reading.

It earns a place only when the finding admits several plausible fixes, one of them
clearly better for max and the difference invisible from where the maintainer
sits. Then say which and why, because nobody else can supply that.

Where the fix follows from the report (correct the sentence, return the error),
naming it says nothing the maintainer had not already worked out by the end of the
first paragraph.

Dont ever add "happy to PR" or bs like that unless the user explicitly asks!
