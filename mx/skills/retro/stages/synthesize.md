# Workflow retro, stage 5 of 5: synthesize

You run the last stage of a workflow retro over max's Claude Code sessions from {{since}} to {{until}}, for the repo `{{repo}}`. Its job is the living report: rewritten whole from the earlier reports and this run's stages, so that the newest report already holds what the earlier runs found and max, after weeks away, sees in its first section what moved. max reads the page built from it, when he wants; nothing waits on him.

{{focus}}

The run directory, `{{run}}`, is your working directory and the only place you write. Read, in full:

- `{{skills}}/retro/REPORT.md`, the report's shape, its rules and the weighing;
- `previous/`: `current.md`, the report as it stands now with max's verdicts since the last run; `<date>.md`, the last runs' reports; `seed/`, where it exists, the reports a first run takes as its previous ones, with max's verdicts on them;
- `notes/`, stage 2's fresh reading of the period, and in `notes/sample-*.md` of the older sample, from before it; `follow-up.md`, what the period did to each standing finding; `deep/`, the deep-dives, the architecture pass, the leading words' search (`lenses.md`) and the permissions' reading (`permissions.md`);
- `versions.md` and `proposed.md`.

The digests (`sessions/`, `sample/`) and `git/` are there to check a quote against.

## Steps

1. Write `report.md` whole, in REPORT.md's shape. A standing finding keeps its id and gains this run's evidence: sharpened where the period confirms it, amended where it shows it was wrong, dropped where it went quiet across the period and the older sample. A new finding, from the notes or a deep-dive, takes the next id. A dismissed one stays dismissed unless `follow-up.md` names evidence newer than max's verdict. A seed's findings that max ruled out of scope go under Dismissed with his words; those he called real get ids. Fresh-notes friction seen once and at low cost stays out: the report holds what recurs or costs much. A count backs a finding as its evidence; it is never a number a later run tries to move.
2. Group the proposed tickets for the report's Proposed tickets section: read each ticket `proposed.md` names, at the commit it names, for the cause behind it, handing them to subagents in groups of about ten where there are many, each returning a line per ticket: its slug and its cause in a sentence. Then group the tickets that share a cause and name the finding or candidate each group is. Reading a ticket is all the report does with it.
3. Check `report.md` against REPORT.md's rules, finding by finding: every quote verbatim from its source, with the source and an absolute date; every proposal naming what it deletes or narrows; ids unique, and the `ids:` line holding the highest; every slug under Proposed tickets one `proposed.md` names.
4. Spawn one subagent to build `report.html` from `report.md`, with this brief: "Build `{{run}}/report.html`, one self-contained page with no file or network beside it, from `{{run}}/report.md`, in the house style of `{{skills}}/house-style/SKILL.md`. It shows the report's content whole, in its order; a finding's figure (a timeline of its history across runs, the cause and where the fix lands) and a candidate's before and after diagram, as `{{skills}}/improve-codebase-architecture/REPORT.md` draws them, carry what a paragraph would. `{{skills}}/show/SVG-FIGURES.md` is how figures are drawn. Reply with the page's path alone."

The stage is done when `report.md` passes step 3's check and `report.html` exists.
