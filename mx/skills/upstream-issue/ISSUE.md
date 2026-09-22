# The issue body

Load `/mx:writing-for-humans` first; an issue is read cold by a person deciding
whether it is worth their afternoon. Load `/mx:writing-for-agents` after it, since
their agents read it too.

## Shape

**The first screen carries the finding.** Whatever the shape, it opens with
expected against actual, or, for a request, with the ask itself. The evidence a
reader checks only if they doubt you, the repro's files, commands and output, a
stack, a probe of the cause, goes inside `<details>` blocks whose summaries say
what each holds. Done: a maintainer who skims that first screen and stops there
has the finding.

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

## Disclaimer

The first line of every issue, verbatim:

```markdown
> **Disclaimer:** AI-drafted, verified by me before filing. I answer follow-ups.
```

Three claims, each load-bearing: where the text came from, that its content was
checked, and that a person is on the other end. Maintainers are being flooded with
unverified AI reports, and this says which kind this is. Keep it to the one line;
length reads as legalese and invites dismissal.

## Voice

Describe what happened. Let the reader judge how bad it is: "the connection closes
after one byte" survives scrutiny, where a severity claim invites an argument about
whether the severity is right. The value judgements that belong in an issue are the
ones only max can make: expected against actual, and why it cost him something.

Say what was checked and what was inferred. An untested corner is cheap to flag and
expensive to be caught on.
