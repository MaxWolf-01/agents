---
name: upstream-issue
description: Report a finding to a project max doesn't maintain. Use when a dependency, tool or service turns out to be broken, undocumented or wrong and the maintainers should hear about it.
argument-hint: [what's wrong, and where]
---

Turn a finding into an issue its maintainers can act on. Filing runs on max's
GitHub account, so every issue needs his explicit yes before it goes out.

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

**Read the body as a stranger would, for what it discloses.** Hostnames, paths,
usernames, tokens, internal URLs, a stack trace carrying any of those, and the
subtler kind, where the shape of a setup or the reason for a question says more
about max than he'd choose to publish. Redact to the minimum that still
reproduces.

## Filing

Drilling down is slow and mostly mechanical, so hand it to a subagent and carry on
with the session's real work. Give it the finding, the repo, and this skill, and
name the file it writes to, `agent/research/upstream-<repo>-<slug>.md`, holding
the body, written per [ISSUE.md](ISSUE.md), the duplicate search, and whatever it
could not verify. It writes that file; it never files the issue.

The main session then owns three gates, in order:

1. **Sanity check** the body against what the session actually knows; the
   subagent worked from a brief and can have drifted.
2. **Show max** what would be published, rendered the way its destination
   renders it, opened with `claude-browser` where it exists, else `xdg-open`:

   ```console
   gh api -X POST /markdown -f mode=gfm -f context=<owner/repo> \
       -f text="$(cat <file>)" > <file>.html
   ```

   `mode=gfm` with the repo as `context` is what resolves `#123` and `@name`;
   the default mode leaves them as text. A `<details>` block shows up collapsed,
   the way a maintainer meets it.
3. **His explicit yes.** Then `gh issue create -R <repo>` with the label the
   template assigns, and report the URL back.

A gate that does not pass sends it round again: another subagent round when the
gap is real work, a direct edit and a fresh yes when it is wording. A finding the
session later invalidates, or max judges not worth filing, is dropped; the work
already paid for itself by being understood.
