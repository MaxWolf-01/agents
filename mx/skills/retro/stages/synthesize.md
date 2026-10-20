# A {{kind}}: synthesize

You run the last stage of a {{kind}} of `{{repo}}`, over the period from {{since}} to {{until}}. Its job is the living report: rewritten whole from the earlier reports and this run's stages, so that the newest report already holds what the earlier runs found and max, after weeks away, sees in its first section what moved. max reads the page built from it, when he wants; nothing waits on him.

{{focus}}

The run directory, `{{run}}`, is your working directory and the only place you write. Read, in full:

- `{{skills}}/retro/REPORT.md`, the report's shape, its rules and the weighing;
- `previous/`: `current.md`, the report as it stands now with max's verdicts since the last run; `<date>.md`, the last runs' reports; `seed/`, where it exists, the reports a first run takes as its previous ones, with max's verdicts on them;
- `follow-up.md`, what the period did to each standing finding and candidate; `lens-pass/`, the candidates of every code lens; `proposed.md`;
- in a workflow retro, also `notes/`, stage 2's fresh reading of the period, and in `notes/sample-*.md` of the older sample, from before it; `deep/`, the deep-dives, the leading words' search (`leading-words.md`) and the permissions' reading (`permissions.md`); and `versions.md`;
- in a repo retro, also `corrections.md`, max's corrections in the period's sessions worked in the repo.

`git/`, and the digests in `sessions/` (and in a workflow retro `sample/`), are there to check a quote against.

You may read the agent repo `{{agent}}`, and the repos below, and run git's read commands in those as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Write `report.md` whole, in REPORT.md's shape for a {{kind}}. A standing finding or candidate keeps its id and gains this run's evidence: sharpened where the period confirms it, amended where it shows it was wrong, dropped where it went quiet or no longer holds. A new one takes the next id. A verdict of max's in `current.md` holds over the runs' reports, and a dismissed one stays dismissed unless `follow-up.md` names evidence newer than his verdict. A seed's findings that max ruled out of scope go under Dismissed with his words; those he called real get ids. A count backs a finding or candidate as its evidence; it is never a number a later run tries to move.
   - The findings, in a workflow retro: friction from the fresh notes seen once and at low cost stays out, since the report holds what recurs or costs much. An answer `deep/leading-words.md` gives to a question LEADING-WORDS.md asks once goes into the report under Findings whatever the weighing, as a finding of its own under that question, so later runs find it there.
   - Every finding and candidate, in both kinds, is held to REPORT.md's What is already written before it enters: search for the guidance its case already has, and let what you find reject it, move its proposal up a rung, make it a placement fix, or make it a description tune.
   - The candidates: two code lenses that found the same change make one candidate. A correction group `corrections.md` shows in two or more sessions is quoted in the candidate it points at, each correction with its session and date. One a ticket in flight takes up has that ticket in its State, `taken up as <ticket>`, and is proposed nowhere else in the report; one a proposed ticket asks for stays a candidate, and its ticket goes under Proposed tickets.
2. Group the proposed tickets for the report's Proposed tickets section: read each ticket `proposed.md` names, in `proposed/`, for the cause behind it, handing them to subagents in groups of about ten where there are many, each returning a line per ticket: its slug and its cause in a sentence. Then group the tickets that share a cause and name the finding or candidate each group is. Reading a ticket is all the report does with it.
3. Check `report.md` against REPORT.md's rules, entry by entry: every quote verbatim from its source, with the source and an absolute date; every proposal, an architecture candidate's included, naming what it deletes or narrows; every check an escaped-defects candidate proposes naming the past commit it would have failed on; every finding and candidate whose case has guidance already written naming that guidance, by path, in its Cause or Proposal; ids unique, and the `ids:` line holding the highest; every slug under Proposed tickets one `proposed.md` names.
4. Spawn one subagent to build `report.html` from `report.md`, with this brief: "Build `{{run}}/report.html`, one self-contained page with no file or network beside it, from `{{run}}/report.md`, in the house style of `{{skills}}/house-style/SKILL.md`. It shows the report's content whole, in its order; a finding's figure (a timeline of its history across runs, the cause and where the fix lands) and a candidate's before and after diagram, as `{{skills}}/improve-codebase-architecture/REPORT.md` draws them, carry what a paragraph would. `{{skills}}/show/SVG-FIGURES.md` is how figures are drawn. Reply with the page's path alone."

The stage is done when `report.md` passes step 3's check and `report.html` exists.
