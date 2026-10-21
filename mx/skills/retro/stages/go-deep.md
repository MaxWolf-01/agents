# A workflow retro: go deep

You run the go-deep stage of a workflow retro over max's Claude Code sessions from {{since}} to {{until}}, for the repo `{{repo}}`. Its job is depth: a few patterns traced to the lines that produce them, with the smallest fix for each; a search of the whole period for the retro's leading words; and a reading of what auto mode's classifier blocked that max wanted, and let through that he did not. max found a broad, ranked list of findings mostly noise; what he used from the first retro, run by hand in October 2026, was its two deep-dives.

{{focus}}

The run directory, `{{run}}`, is your working directory and the only place you write. It holds `notes/` (stage 2's fresh reading of the period, and in `notes/sample-*.md` of the older sample, from before it), `follow-up.md` (what the period did to each standing finding), `previous/` (the earlier reports), the digests in `sessions/` and `sample/`, `git/<repo>.md`, `versions.md` and `permissions/`. The report's rules and the weighing are `{{skills}}/retro/REPORT.md`. Read it, then `follow-up.md` and every file in `notes/`.

You may read the repos below and run git's read commands in them as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Pick the patterns: one to three, by the weighing, from the fresh notes and the standing findings that recurred or came back. A focus max named is one of them. A pattern stage 2 saw in several of the period's sessions outranks one seen once, and one the older sample shows too is no new one, and one that cost max outranks one that cost an agent the same.
2. Spawn, in parallel, one subagent per pattern, one for the leading words and one for the permissions, each with its brief below and the paths it needs.
3. When they return, check each wrote its file; spawn a fresh one for any that did not.

The stage is done when `deep/` holds a file per pattern, `deep/leading-words.md`, `deep/permissions.md` and `deep/critique.md`.

## A deep-dive's brief

Pattern: <the pattern, and the notes and follow-up sections it comes from>. Write `{{run}}/deep/<a slug for the pattern>.md`.

Read the sources qualitatively, past the notes: the digests the pattern shows in, the git history of what produces it, the skill text and scripts in the agents repo. Find where it happens and where it does not, and what differs. Trace it to its cause: the skill line, script, check, hook or config that produces it, by path and line, with the commit that added it and the failure that commit names, or the habit when no line produces it. Then propose the smallest fix: a deletion or a narrowing first; a mechanism only where the pattern recurs and nothing smaller would hold, with its upkeep named. Weigh it as REPORT.md's weighing says.

The file: the pattern in a sentence; how often and where, with quotes, each with its source and absolute date; the cause; the proposal, naming what it deletes or narrows and where it lands; the weighing; and what you could not settle. Reply with the file's path alone.

## The leading words' brief

Write `{{run}}/deep/leading-words.md`.

`{{skills}}/retro/LEADING-WORDS.md` holds the retro's leading words and max's questions, which the readers of stage 2 were not given. Search the whole period for what each word names and for each question's answer, in the data the question names: read every file in `notes/`, and search the digests in `sessions/`, the older sample's in `sample/` and the records in `git/` for their signs, reading the passages a search finds rather than every digest whole. A word or a question is a lead, never a quota: report what the period shows and leave out one it does not show.

The file: a section per word and per question the period shows, a question's under its number and its text, each instance with what happened, a quote with its source and absolute date, and its cause where you can tell; whether the older sample shows it too; and, last, what recurs across words and questions. Reply with the file's path alone.

## The permissions' brief

Write `{{run}}/deep/permissions.md`, and `{{run}}/deep/auto-mode.json` for the critique, which writes `{{run}}/deep/critique.md`.

Read `{{skills}}/retro/PERMISSIONS.md`: the permission data, the two directions the classifier errs in, and the shape of an entry. Then:

1. Find the period's false blocks and false allows. Read every `! DENIED` line in `sessions/`, each with the turns around it, so what max did next is in view; then the `[classifier allowed]` calls max's next turn stopped, undid or corrected, and the incidents nothing blocked, found in what he said after them. Read each profile's `rules.json` and `auto-mode.json`.
2. Group the false blocks by what the classifier lacked (the rule that fired, the fact it did not have) and the false allows by the class of action, and word an entry per group. Done when every event you found is in a group, or named as one a single entry would overfit to.
3. Write the entries into `deep/auto-mode.json` in the shape a settings file's `autoMode` takes, `{"allow": [...], "soft_deny": [...]}`, each section a list of entries: without `$defaults`, which the critique adds itself, and without a section you have no entry for, `{}` where you have none at all. Then run `{{critique}}`, written exactly so, which is the one command besides git's reads you may run. It writes what `claude auto-mode critique` found into `deep/critique.md`. Rework an entry the critique shows too wide, too narrow or unclear, and run it again; where it printed no critique, run it once more.

The file: a section per direction, each entry with its section of `autoMode`, its text whole, the events it would have changed (each with a quote, its source and absolute date), how often, and what the critique found of it and what you changed in answer; then the events left out of any entry, and why. Where the critique printed none, say the entries go to max unchecked. What max takes up, he applies in a session. Reply with the file's path alone.
