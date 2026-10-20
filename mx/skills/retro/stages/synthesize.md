# A {{kind}}: synthesize

You run the last stage of a {{kind}} of `{{repo}}`, over the period from {{since}} to {{until}}. Its job is the living report: rewritten whole from the earlier reports and this run's stages, so that the newest report already holds what the earlier runs found and max, after weeks away, sees in its first section what moved. max reads the page built from it, when he wants; nothing waits on him.

{{focus}}

The run directory, `{{run}}`, is your working directory and the only place you write. Read, in full:

- `{{skills}}/retro/REPORT.md`, the report's shape, its rules and the weighing;
- `previous/`: `current.md`, the report as it stands now with max's verdicts since the last run; `<date>.md`, the last runs' reports; `seed/`, where it exists, the reports a first run takes as its previous ones, with max's verdicts on them; `folded/<name>.md`, where it exists, the report a listed repo kept of its own, which this run takes in;
- `follow-up.md`, what the period did to each standing finding, candidate and Watched line; `lens-pass/`, the candidates of every code lens; `proposed.md`;
- `notes/`, stage 2's fresh reading of the period, max's corrections with their causes among it, and in `notes/sample-*.md` of the older sample, from before it;
- in a workflow retro, also `deep/`, the deep-dives, the leading words' search (`leading-words.md`) and the permissions' reading (`permissions.md`); and `versions.md`.

`git/`, and the digests in `sessions/` and `sample/`, are there to check a quote against.

You may read the agent repo `{{agent}}`, and the repos below, and run git's read commands in those as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Write `report.md` whole, in REPORT.md's shape for a {{kind}}. A standing finding or candidate keeps its id and gains this run's evidence: sharpened where the period confirms it, amended where it shows it was wrong, dropped where it went quiet or no longer holds. A new one takes the next id. A verdict of max's in `current.md` holds over the runs' reports, and a dismissed one stays dismissed unless `follow-up.md` names evidence newer than his verdict. A seed's findings that max ruled out of scope go under Dismissed with his words; those he called real get ids. A folded report's standing findings and candidates enter under new ids, each History opening `taken in from <name>'s <id> <date>`, and its Dismissed lines join Dismissed. A count backs a finding or candidate as its evidence; it is never a number a later run tries to move.
   - The findings: friction from the fresh notes seen once and at low cost stays out, since the report holds what recurs or costs much. An execution problem or a correction of a fact seen once goes under Watched, and a Watched line `follow-up.md` saw again becomes a finding, weighed as a repeat. In a workflow retro, an answer `deep/leading-words.md` gives to a question LEADING-WORDS.md asks once goes into the report under Findings whatever the weighing, as a finding of its own under that question, so later runs find it there.
   - Every finding and candidate, in both kinds, is held to REPORT.md's What is already written before it enters: search for the guidance its case already has, and let what you find put it under Watched, move its proposal up a rung, make it a placement fix, or make it a description tune.
   - The candidates: two code lenses that found the same change make one candidate. One a ticket in flight takes up has that ticket in its State, `taken up as <ticket>`, and is proposed nowhere else in the report; one a proposed ticket asks for stays a candidate, and its ticket goes under Proposed tickets.
2. Group the proposed tickets for the report's Proposed tickets section: read each ticket `proposed.md` names, in `proposed/`, for the cause behind it, handing them to subagents in groups of about ten where there are many, each returning a line per ticket: its slug and its cause in a sentence. Then group the tickets that share a cause and name the finding or candidate each group is. Reading a ticket is all the report does with it.
3. Check `report.md` against REPORT.md's rules, entry by entry: every quote verbatim from its source, with the source and an absolute date; every proposal, an architecture candidate's included, naming what it deletes or narrows; every check an escaped-defects candidate proposes naming the past commit it would have failed on; every finding and candidate whose case has guidance already written naming that guidance, by path, in its Cause or Proposal; every Watched line quoted and dated, none more than eight weeks old unless seen again; ids unique, and the `ids:` line holding the highest; every slug under Proposed tickets one `proposed.md` names.
4. Spawn one subagent to build `report.html` from `report.md`, with this brief: "Build `{{run}}/report.html`, one self-contained page with no file or network beside it, from `{{run}}/report.md`, in the house style of `{{skills}}/house-style/SKILL.md`. It shows the report's content whole, in its order; a finding's figure (a timeline of its history across runs, the cause and where the fix lands) and a candidate's before and after diagram, as `{{skills}}/improve-codebase-architecture/REPORT.md` draws them, carry what a paragraph would. `{{skills}}/show/SVG-FIGURES.md` is how figures are drawn. Reply with the page's path alone."

The stage is done when `report.md` passes step 3's check and `report.html` exists.
