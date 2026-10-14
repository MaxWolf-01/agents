# Workflow retro, stage 4 of 5: go deep

You run stage 4 of a workflow retro over max's Claude Code sessions from {{since}} to {{until}}, for the repo `{{repo}}`. Its job is depth: a few patterns traced to the lines that produce them, with the smallest fix for each, and an architecture pass over the agents repo's code that the period's friction touched. max found a broad, ranked list of findings mostly noise; what he used from the first retro, run by hand in October 2026, was its two deep-dives.

{{focus}}

The run directory, `{{run}}`, is your working directory and the only place you write. It holds `notes/` (stage 2's fresh reading of the period, and in `notes/sample-*.md` of the older sample, from before it), `follow-up.md` (stage 3: what the period did to each standing finding), `previous/` (the earlier reports), the digests in `sessions/` and `sample/`, `git/<repo>.md` and `versions.md`. What the retro looks for and how it weighs is `{{skills}}/retro/LENSES.md`; the report's rules are `{{skills}}/retro/REPORT.md`. Read both, then `follow-up.md` and every file in `notes/`.

You may read the repos below and run git's read commands in them as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Pick the patterns: one to three, by the weighing, from the fresh notes and the standing findings that recurred or came back. A focus max named is one of them. A pattern stage 2 saw in several of the period's sessions outranks one seen once, and one the older sample shows too is no new one, and one that cost max outranks one that cost an agent the same.
2. Spawn one subagent per pattern and one for the architecture pass, in parallel, each with its brief below and the paths it needs.
3. When they return, check each wrote its file; spawn a fresh one for any that did not.

The stage is done when `deep/` holds a file per pattern and `deep/architecture.md`.

## A deep-dive's brief

Pattern: <the pattern, and the notes and follow-up sections it comes from>. Write `{{run}}/deep/<a slug for the pattern>.md`.

Read the sources qualitatively, past the notes: the digests the pattern shows in, the git history of what produces it, the skill text and scripts in the agents repo. Find where it happens and where it does not, and what differs. Trace it to its cause: the skill line, script, check, hook or config that produces it, by path and line, with the commit that added it and the failure that commit names, or the habit when no line produces it. Then propose the smallest fix: a deletion or a narrowing first; a mechanism only where the pattern recurs and nothing smaller would hold, with its upkeep named. Weigh it as LENSES.md says.

The file: the pattern in a sentence; how often and where, with quotes, each with its source and absolute date; the cause; the proposal, naming what it deletes or narrows and where it lands; the weighing; and what you could not settle. Reply with the file's path alone.

## The architecture pass's brief

Write `{{run}}/deep/architecture.md`.

Run the scan of `{{skills}}/improve-codebase-architecture/SKILL.md`, its step 1 alone, on the agents repo `{{repo}}`, with this direction as the user's: the code the period's friction touched, which the notes, `follow-up.md` and the git records point at. Its vocabulary is `{{skills}}/codebase-design/SKILL.md`. Read the agent repo's open tickets in `{{repo}}/agent/tickets/`, so a candidate already in flight cites its ticket rather than being proposed again, and the architecture candidates in `previous/`, so a standing one is rechecked under its id rather than raised anew.

The file: each candidate with every field the scan names, in order of impact, and for each the friction that pointed at it, quoted with its date. Reply with the file's path alone.
