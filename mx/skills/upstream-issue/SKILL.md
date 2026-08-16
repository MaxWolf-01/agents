---
name: upstream-issue
description: Report a bug or a gap to a project you don't maintain. Use when something in a dependency, tool or service turns out to be broken, undocumented or wrong, and the finding should go to its maintainers.
argument-hint: [what's wrong, and where]
---

Report a finding to a project's maintainers. Filing happens on max's account, so it
needs his explicit yes — draft, show, wait.

## Before drafting

**Reproduce it.** A report whose claims were not run is worse than no report: it
costs the maintainer more than it saves them. Everything asserted is something you
observed, on a stated version.

**Search the tracker.** Closed issues too — a fixed bug means the answer is
"upgrade", and a rejected one means the behaviour is intended. `gh search issues`
and `gh issue list --state all` both take a repo.

**Read the project's rules.** A `CONTRIBUTING`, an issue template, a policy on
AI-assisted reports. Some projects reject those outright; that decision is theirs
and it is max's account that breaks the rule.

**Check the templates.** `.github/ISSUE_TEMPLATE/`. `blank_issues_enabled: false`
means the listed forms are the only route. Required checkboxes are statements the
filer makes — a documentation gap is not a bug, so it does not go on a form that
asks you to affirm it is one. Pick the form that is true, or ask where it belongs.

## Shape

With a template, fill *their* fields. They wrote it to get what they need, and a
foreign structure pasted over it reads as not having looked.

Without one, this order, which is the same information a good template asks for:

- **What happens** — one plain sentence, then expected against actual.
- **Why it matters** — what it costs someone. For a bug: what it breaks, what a
  caller cannot do about it. For a gap: what it made you believe that was untrue.
- **How to reproduce** — exact steps, on a stated version. A table of inputs
  against results carries a boundary better than prose.
- **Cause** — only with evidence in hand: a log line, a traced code path. An
  informed guess belongs nowhere near it.

One report per problem. Several one-line corrections to the same document are one
report; a crash and a documentation gap are never the same one.

## Fix direction

Leave it out. The maintainer knows the codebase, has their own agents, and will
find a better fix than an outsider working from one afternoon of reading.

Include it only when max says to, and only for a reason he holds: the shape of the
fix affects him, or he wants a specific behaviour. His call, not an inference from
his enthusiasm.

## Disclaimer

First line of every issue, verbatim:

```markdown
> **Disclaimer:** AI-drafted, verified by me before filing. I answer follow-ups.

___
```

Three claims, each load-bearing: the provenance, that the content was checked, and
that a person is on the other end. Maintainers are being flooded with unverified
AI reports; this says which kind this is. Do not expand it — length reads as
legalese and invites dismissal. Do not drop it either.

## Voice

Describe, do not characterise. "The connection closes after one byte" survives
scrutiny; "this is a serious flaw" invites an argument about whether it is. No
severity claims, no counts of how bad it is, no advice on priority.

Say what was checked and what was not. An unverified corner stated as one costs
nothing to admit and everything to get caught on.

## Filing

Show max the full body first and wait for a yes. Then `gh issue create -R <repo>`
with the matching label from the template. Report the URL back.
