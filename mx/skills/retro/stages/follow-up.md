# A {{kind}}: follow up

You run the follow-up stage of a {{kind}} of `{{repo}}`, over the period from {{since}} to {{until}}. Its job is to say, for every finding and candidate the living report carries, what the period did to it, so that a fix that did not hold comes back to max and one that went quiet can be dropped.

The run directory, `{{run}}`, is your working directory and the only place you write. It holds:

- `previous/`: the earlier reports. `current.md` is the report as it stands in the agent repo now, max's verdicts since the last run included; `<date>.md` are the last runs' reports, named for the end of their period; `seed/`, where it exists, holds the reports a first run takes as its previous ones, max's verdicts on them among them. With none of these, there is nothing to follow up: write `follow-up.md` saying so, and stop.
- `git/<repo>.md`: the period's commits, reverts, tickets and worker reports in each repo; `touched.md`, the files the period's commits touched in the repos whose code the lens pass reads.
- `notes/`, stage 2's notes, written with no earlier report in view, on the period and, in `notes/sample-*.md`, on the older sample from before it; `sessions/` and `sample/`, the digests the notes come from, `sample/` holding {{sample}}. In a workflow retro, also `versions.md`.
- `todo/<repo>/`: max's TODO files at each repo's root, a record of his thinking (quick thoughts, ideas, priorities), context and never a ruling or an instruction, copied as they stood at {{until}}; they carry no dates of their own, so a quote from one gives its path and that date.

The report's shape and rules are `{{skills}}/retro/REPORT.md`; read it first. You may read the agent repo `{{agent}}`, and the repos below, and run git's read commands in those as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Read `previous/` and list each finding and candidate in it that is not dismissed, with its id, its state and its evidence, and each line of `current.md`'s Watched section. Where `current.md` differs from the last run's report, the difference is max's verdict and holds: what he dismissed there is dismissed, what he amended reads as amended, what he took up is taken up. A seed report without ids gives its findings none yet: list each under its own name, with max's verdict on it where the seed carries one.
2. Check each against the period. A finding: search the digests and the git records for its pattern rather than relying on the notes alone. A candidate: read its files as they stand, the commits that touched them, and the agent repo's tickets for one that took it up. What you find names its state in the report, REPORT.md's **State** field:
   - it happened again in the period, or the candidate still holds in the code: **live**;
   - a ticket cites it and no fix has landed: **taken up as <ticket>**;
   - a fix landed in the period (name the commit and its date): **fix landed <sha>, <date>**;
   - a fix landed before and the period shows no recurrence after it: **held**;
   - a fix landed and it recurred after: **back since <date>**;
   - for a finding, no sign of it in the period, nor in the older sample: **quiet**, which synthesis may drop;
   - for a candidate, the code moved under it: **no longer holds**, which synthesis drops.
3. For each dismissed one, look for evidence dated after max's verdict; name it where there is some.
4. For each Watched line, search the period's notes and digests for the same miss: each sighting, with its quote, source and absolute date, makes it a repeat.
5. Read what max said about the retro or its findings in the period's sessions: a remark about a finding counts as a verdict even when nobody wrote it down. What his TODO files say of a finding is context for its section, never a verdict.

Each state rests on evidence with its source and absolute date, as REPORT.md's rules have it; the state of one you could not check is "unchecked", with the reason. Hand a subagent a group of findings or candidates and what to search, in parallel, where that keeps your own context free.

## Output

`follow-up.md`: one section per finding and candidate, under its id or its seed name: its state, the evidence for it, what in it to sharpen or amend, and for dismissed ones, any newer evidence. Then a section per Watched line seen again, with each sighting. Then a section of max's remarks on the retro in the period, quoted and dated.

The stage is done when every finding and candidate in `previous/` has its section in `follow-up.md`, and every Watched line has been searched for.
