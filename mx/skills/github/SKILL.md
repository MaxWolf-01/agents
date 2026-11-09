---
name: github
description: "Writing to GitHub under the user's name: issues to projects they don't maintain, PR titles and bodies. Use when a dependency, tool or service turns out broken, undocumented or wrong and its maintainers should hear about it; when opening a PR, at work or in open source; when closing out a PR's review; when rewriting the PRs `gh stack submit` opened."
argument-hint: "[what to write, and where]"
---

Everything written here goes out on max's account, to people who owe him no attention. Load `/mx:writing-for-humans` first: it is the sentence-level standard, and this skill holds what it doesn't, what a GitHub document carries, in what order, and the gate before it is published.

What each kind of document holds is in its companion:

- **An issue on a project max doesn't maintain**: [ISSUE.md](ISSUE.md), from earning the filing to the title and body.
- **A PR**, its title and body, and closing out its reviews: [PR.md](PR.md).

## The reader

The reader is cold: a maintainer or a colleague who was not in the session, deciding from the first screen whether the rest is worth their time. Five rules hold for every document:

- **The first screen carries the point.** An issue opens on its finding, a PR on what it changes, in plain words before any identifier. Done: a reader who skims the first screen and stops there has the point.
- **`<details>` holds what not every reader needs**: evidence, logs, a long table, a side finding. A block's summary names its contents plainly, the way a table caption does ("Reviewer request size, before and after"), never as a headline.
- **Describe; let the reader judge.** "The connection closes after one byte" survives scrutiny, where a severity claim invites an argument about the severity. Say what was checked and what was inferred: an untested corner is cheap to flag and expensive to be caught on.
- **A title states; it never teases**: no headline phrasing, no question, no pun, no emoji.
- **English**, whatever language the session ran in.

## Disclaimer

An issue or PR on a repo that is neither under max's account nor under an organization he belongs to opens with this line, verbatim:

```markdown
> **Disclaimer:** AI-drafted, verified by me before filing. I answer follow-ups.
```

`gh api user --jq .login` and `gh api user/orgs --jq '.[].login'` name the owners that carry none: his own repos, his employer's, his other organizations.

Three claims, each load-bearing: where the text came from, that its content was checked, and that a person is on the other end. Maintainers are being flooded with unverified AI reports, and this says which kind this is. Keep it to the one line; length reads as legalese and invites dismissal.

## Publishing

For most routine work filing an issue or PR is absolutely fine to do without the user's explicit yes beforehand; preferrably create draft PRs/issues on the remote and set them to ready once the user has seen them. Only irreversible actions like tagging someone in a PR, or putting sensitive information on a PR, require the user's explicit yes.
1. **Read the body as a stranger would, for what it discloses**, on any repo others can read. Hostnames, paths, usernames, tokens, internal URLs, a stack trace carrying any of those, and the subtler kind, where the shape of a setup or the reason for a question says more about the user than they'd choose to publish. Redact to the minimum that still makes the point.
2. **Show the user** by opening the draft PR/issue
   Alternatively, for edge cases / uncertain issues: `gh api -X POST /markdown -f mode=gfm -f context=<owner/repo> -f text="$(cat <file>)" > <file>.html`; `mode=gfm` with the repo as `context` is what resolves `#123` and `@name`; the default mode leaves them as text.

A wording change after the yes is a new text, and it goes through the gate again.
