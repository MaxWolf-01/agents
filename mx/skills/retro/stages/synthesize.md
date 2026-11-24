# A {{kind}}: synthesize

You run the last stage of a {{kind}} of `{{repo}}`, over the period from {{since}} to {{until}}. Its job is the living report: rewritten whole from the earlier reports and this run's stages, so that the newest report already holds what the earlier runs found, and the run's commit says why each entry changed. max reads the page built from it, when he wants; nothing waits on him.

{{focus}}

The run directory, `{{run}}`, is your working directory and the only place you write. Read, in full:

- `{{skills}}/retro/REPORT.md`, the report's shape, its rules and the weighing;
- `previous/`: `current.md`, the report as it stands now with max's verdicts since the last run; `comments.md`, max's comments on its page that no run has answered yet; `<date>.md`, the last runs' reports; `seed/`, where it exists, the reports a first run takes as its previous ones, with max's verdicts on them;
- `follow-up.md`, what the period did to each standing finding, candidate and Watched line; `lens-pass/`, the candidates of every code lens; `proposed.md`;
- `notes/`, stage 2's fresh reading of the period, max's corrections with their causes among it, and in `notes/sample-*.md` of the older sample, from before it;
- `todo/<repo>/`, max's TODO files at each repo's root, a record of his thinking (quick thoughts, ideas, priorities), read as context, copied as they stood at {{until}}; they carry no dates of their own, so a quote from one gives its path and that date. A finding or candidate an item there already names quotes it as his note;
- in a workflow retro, also `deep/`, the deep-dives, the leading words' search (`leading-words.md`) and the permissions' reading (`permissions.md`) and the critique of the auto mode entries it proposes (`critique.md`); and `versions.md`.

`git/`, and the digests in `sessions/` and `sample/`, are there to check a quote against.

You may read the agent repo `{{agent}}`, and the repos below, and run git's read commands in those as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Write `report.md` whole, in REPORT.md's shape for a {{kind}}. A standing finding or candidate keeps its id and gains this run's evidence: sharpened where the period confirms it, amended where it shows it was wrong, dropped where it went quiet or no longer holds. A new one takes the next id. A verdict of max's in `current.md` holds over the runs' reports, and a dismissed one stays dismissed unless `follow-up.md` names evidence newer than his verdict. Each comment in `comments.md` is weighed and answered as REPORT.md's max's comments says. A seed's findings that max ruled out of scope go under Dismissed with his words; those he called real get ids. A seed's ids are its own report's: each finding or candidate of it that this report keeps takes this report's next id, its History naming the one it had there. A count backs a finding or candidate as its evidence; it is never a number a later run tries to move.
   - The findings: friction from the fresh notes seen once and at low cost stays out, since the report holds what recurs or costs much. An execution problem or a correction of a fact seen once goes under Watched, and a Watched line `follow-up.md` saw again becomes a finding, weighed as a repeat. In a workflow retro, an answer `deep/leading-words.md` gives to a question LEADING-WORDS.md asks once goes into the report under Findings whatever the weighing, as a finding of its own under that question, so later runs find it there.
   - A finding of permission friction proposes its auto mode entry word for word, with its section of `autoMode`, and what the critique found of it.
   - Every finding and candidate, in both kinds, is held to REPORT.md's What is already written before it enters.
   - The candidates: two code lenses that found the same change make one candidate. One a ticket in flight takes up has that ticket in its State, `taken up as <ticket>`, and is proposed nowhere else in the report; one a proposed ticket asks for stays a candidate, and its ticket goes under Proposed tickets.
2. Write `changes.md`, the body of the commit that lands the report, as REPORT.md's The run's changes says: one line per entry this report adds, sharpens, amends, drops or moves the state of, against `previous/current.md`, its id first and then why; and one per comment answered for an entry no longer in the report.
3. Group the proposed tickets for the report's Proposed tickets section: read each ticket `proposed.md` names, in `proposed/`, for the cause behind it, handing them to subagents in groups of about ten where there are many, each returning a line per ticket: its slug and its cause in a sentence. Then group the tickets that share a cause and name the finding or candidate each group is.
4. Check `report.md` against REPORT.md's rules, entry by entry: every quote verbatim from its source, with the source and an absolute date; every proposal, an architecture candidate's included, naming what it deletes or narrows; every check an escaped-defects candidate proposes naming the past commit it would have failed on; every finding and candidate whose case has guidance already written naming that guidance, by path, in its Cause or Proposal; every Watched line quoted and dated, none more than eight weeks old unless seen again; ids unique, and the `ids:` line holding the highest; every slug under Proposed tickets one `proposed.md` names; every comment in `comments.md` answered once, by its id; every entry that differs from `previous/current.md` named in `changes.md`.

The stage is done when `report.md` passes step 4's check and `changes.md` exists.
