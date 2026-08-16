---
name: upstream-issue
description: Report a finding to a project max doesn't maintain. Use when a dependency, tool or service turns out to be broken, undocumented or wrong and the maintainers should hear about it.
argument-hint: [what's wrong, and where]
---

Turn a finding into an issue its maintainers can act on. Filing runs on max's
GitHub account, so every issue needs his explicit yes before it goes out.

Load `writing-for-humans` first — an issue is read cold by a person deciding
whether it is worth their afternoon. Load `writing-for-agents` after it, since
their agents read it too.

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

Some findings resist it — a race, something that needs the real data, a crash you
saw once. Then the report is the observation plus its log or stack trace, said
plainly as a single occurrence.

**Read the body as a stranger would, for what it discloses.** Hostnames, paths,
usernames, tokens, internal URLs, a stack trace carrying any of those — and the
subtler kind, where the shape of a setup or the reason for a question says more
about max than he'd choose to publish. Redact to the minimum that still
reproduces.

## Shape

Where a template exists, fill **its** fields. The maintainers wrote it to get what
they need, and a foreign structure laid over it reads as not having looked.

Where none exists, use this order — the same information a good template asks for:

- **What happens** — one plain sentence, then expected against actual.
- **Why it matters** — what it costs someone. A bug: what breaks, and what a
  caller can do about it. A gap: what it made you believe that was untrue.
- **How to reproduce** — exact steps on a stated version. A table of inputs
  against results carries a boundary better than prose does.
- **Cause** — only with evidence in hand: a log line, a traced code path. Anything
  short of that stays out.

One report per problem. Several one-line corrections to the same document are one
report; a crash and a documentation gap are two.

These headings are available, not owed. A section you have nothing behind is a
section to drop — inventing a cause or a consequence to fill one is the failure
this skill exists to prevent, and a maintainer spots it immediately.

## Fix direction

Report the finding and leave the fix to the maintainer. They know the codebase,
they have their own agents, and they will find a better fix than an outsider
working from one afternoon of reading.

It earns a place only when the finding admits several plausible fixes, one of them
clearly better for max and the difference invisible from where the maintainer
sits. Then say which and why, because nobody else can supply that.

Where the fix follows from the report — correct the sentence, return the error —
naming it says nothing the maintainer had not already worked out by the end of the
first paragraph.

## Disclaimer

The first line of every issue, verbatim:

```markdown
> **Disclaimer:** AI-drafted, verified by me before filing. I answer follow-ups.
```

Three claims, each load-bearing: where the text came from, that its content was
checked, and that a person is on the other end. Maintainers are being flooded with
unverified AI reports, and this says which kind this is. Keep it to the one line —
length reads as legalese and invites dismissal.

## Voice

Describe what happened. Let the reader judge how bad it is: "the connection closes
after one byte" survives scrutiny, where a severity claim invites an argument about
whether the severity is right. The value judgements that belong in an issue are the
ones only max can make — expected against actual, and why it cost him something.

Say what was checked and what was inferred. An untested corner is cheap to flag and
expensive to be caught on.

## Filing

Drilling down is slow and mostly mechanical, so hand it to a subagent and carry on
with the session's real work. Give it the finding, the repo, and this skill; it
comes back with a body, not a filed issue.

The main session then owns three gates, in order:

1. **Sanity check** the body against what the session actually knows — the
   subagent worked from a brief and can have drifted.
2. **Show max**: write the body to a file and `xdg-open` it, or paste it, so he
   reads what would be published.
3. **His explicit yes.** Then `gh issue create -R <repo>` with the label the
   template assigns, and report the URL back.

A gate that does not pass sends it round again: another subagent round when the
gap is real work, a direct edit and a fresh yes when it is wording. A finding the
session later invalidates, or max judges not worth filing, is dropped — the work
already paid for itself by being understood.
