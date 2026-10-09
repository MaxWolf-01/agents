# Workflow retro, stage 3 of 5: follow up

You run stage 3 of a workflow retro over max's Claude Code sessions from {{since}} to {{until}}, for the repo `{{repo}}`. Its job is to say, for every finding and architecture candidate the living report carries, what the period did to it, so that a fix that did not hold comes back to max and a finding that went quiet can be dropped.

The run directory, `{{run}}`, is your working directory and the only place you write. It holds:

- `previous/`: the earlier reports. `current.md` is the report as it stands in the agent repo now, max's verdicts since the last run included; `<date>.md` are the last runs' reports, named for the end of their period; `seed/`, where it exists, holds the reports a first run takes as its previous ones, max's verdicts on them among them. With none of these, there is nothing to follow up: write `follow-up.md` saying so, and stop.
- `notes/`: stage 2's notes on the period, read with no earlier report in view.
- `sessions/`, `sample/`: the digests the notes come from; `sample/` holds {{sample}}. `git/<repo>.md`: the period's commits, reverts, tickets and worker reports in each repo. `versions.md`.

The report's shape and rules are `{{skills}}/retro/REPORT.md`; what the retro looks for and how it weighs, `{{skills}}/retro/LENSES.md`. Read both first. You may read the repos below and run git's read commands in them as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Read `previous/` and list each finding and candidate in it that is not dismissed, with its id, its state and its evidence. A seed report without ids gives its findings none yet: list each under its own name, with max's verdict on it where the seed carries one.
2. Check each against the period, searching the digests and the git records for its pattern rather than relying on the notes alone. What you find names its state in the report, REPORT.md's **State** field:
   - it happened again in the period: **live**;
   - a ticket cites it and no fix has landed: **taken up as <ticket>**;
   - a fix landed in the period (name the commit and its date): **fix landed <sha>, <date>**;
   - a fix landed before and the period shows no recurrence after it: **held**;
   - a fix landed and it recurred after: **back since <date>**;
   - no sign of it in the period, nor in the older sample: **quiet**, which synthesis may drop;
   - for a candidate, the code moved under it: **no longer holds**, which synthesis drops.
3. For each dismissed one, look for evidence dated after max's verdict; name it where there is some.
4. Read what max said about the retro or its findings in the period's sessions: a remark about a finding counts as a verdict even when nobody wrote it down.

Each state rests on quotes with their source and absolute date, as REPORT.md's rules have them; the state of a finding you could not check is "unchecked", with the reason. Reading the digests is the bulk of this stage: hand a subagent a group of findings and the digests to search, in parallel, where that keeps your own context free.

## Output

`follow-up.md`: one section per finding and candidate, under its id or its seed name: its state, the evidence for it, what in it to sharpen or amend, and for dismissed ones, any newer evidence. Then a section of max's remarks on the retro in the period, quoted and dated.

The stage is done when every finding and candidate in `previous/` has its section in `follow-up.md`.
