# Workflow retro, stage 4 of 5: go deep

You run stage 4 of a workflow retro over max's Claude Code sessions from {{since}} to {{until}}, for the repo `{{repo}}`. Its job is depth: a few patterns traced to the lines that produce them, with the smallest fix for each; an architecture pass over the agents repo's code that the period's friction touched; a search of the whole period for the retro's leading words; and a reading of its permission prompts, denials and near misses. max found a broad, ranked list of findings mostly noise; what he used from the first retro, run by hand in October 2026, was its two deep-dives.

{{focus}}

The run directory, `{{run}}`, is your working directory and the only place you write. It holds `notes/` (stage 2's fresh reading of the period, and in `notes/sample-*.md` of the older sample, from before it), `follow-up.md` (stage 3: what the period did to each standing finding), `previous/` (the earlier reports), the digests in `sessions/` and `sample/`, `git/<repo>.md`, `versions.md` and `permissions/`. The report's rules and the weighing are `{{skills}}/retro/REPORT.md`. Read it, then `follow-up.md` and every file in `notes/`.

You may read the repos below and run git's read commands in them as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Pick the patterns: one to three, by the weighing, from the fresh notes and the standing findings that recurred or came back. A focus max named is one of them. A pattern stage 2 saw in several of the period's sessions outranks one seen once, and one the older sample shows too is no new one, and one that cost max outranks one that cost an agent the same.
2. Spawn, in parallel, one subagent per pattern, one for the architecture pass, one for the leading words and one for the permissions, each with its brief below and the paths it needs.
3. When they return, check each wrote its file; spawn a fresh one for any that did not.

The stage is done when `deep/` holds a file per pattern, `deep/architecture.md`, `deep/lenses.md` and `deep/permissions.md`.

## A deep-dive's brief

Pattern: <the pattern, and the notes and follow-up sections it comes from>. Write `{{run}}/deep/<a slug for the pattern>.md`.

Read the sources qualitatively, past the notes: the digests the pattern shows in, the git history of what produces it, the skill text and scripts in the agents repo. Find where it happens and where it does not, and what differs. Trace it to its cause: the skill line, script, check, hook or config that produces it, by path and line, with the commit that added it and the failure that commit names, or the habit when no line produces it. Then propose the smallest fix: a deletion or a narrowing first; a mechanism only where the pattern recurs and nothing smaller would hold, with its upkeep named. Weigh it as REPORT.md's weighing says.

The file: the pattern in a sentence; how often and where, with quotes, each with its source and absolute date; the cause; the proposal, naming what it deletes or narrows and where it lands; the weighing; and what you could not settle. Reply with the file's path alone.

## The architecture pass's brief

Write `{{run}}/deep/architecture.md`.

Run the scan of `{{skills}}/improve-codebase-architecture/SKILL.md`, its step 1 alone, on the agents repo `{{repo}}`, with this direction as the user's: the code the period's friction touched, which the notes, `follow-up.md` and the git records point at. Its vocabulary is `{{skills}}/codebase-design/SKILL.md`. Read the agent repo's open tickets in `{{repo}}/agent/tickets/`, so a candidate already in flight cites its ticket rather than being proposed again, and the architecture candidates in `previous/`, so a standing one is rechecked under its id rather than raised anew.

The file: each candidate with every field the scan names, in order of impact, and for each the friction that pointed at it, quoted with its date. Reply with the file's path alone.

## The leading words' brief

Write `{{run}}/deep/lenses.md`.

`{{skills}}/retro/LENSES.md` holds the retro's leading words, which the readers of stage 2 were not given. Search the whole period for what each names: read every file in `notes/`, and search the digests in `sessions/`, the older sample's in `sample/` and the records in `git/` for each word's signs, reading the passages a search finds rather than every digest whole. A word is a lead, never a quota: report what the period shows and leave out a word it does not show.

The file: a section per word the period shows, each instance with what happened, a quote with its source and absolute date, and its cause where you can tell; whether the older sample shows it too; and, last, what recurs across words. Reply with the file's path alone.

## The permissions' brief

Write `{{run}}/deep/permissions.md`.

Read `{{skills}}/retro/PERMISSIONS.md`, what to know about the permission data and the bar a proposed rule is held to. Then the period's permission friction, in three directions:

- prompts and blocks max approved unchanged, and auto mode classifier rejections that were overeager, the main friction now: a rule too cautious, or a harmless action shaped to trip one;
- blocks an agent got past by rephrasing the same action;
- incidents nothing blocked, git hygiene that nearly went wrong among them.

Read every `! DENIED` line in `sessions/`, each with the turns around it, so what max did next is in view, and the auto mode rejections above all; then `permissions/<profile>/scan.json`, the commands no allowlist rule covers; and each profile's rules, `rules.json` and `auto-mode.json`. For incidents, search the digests for what went wrong with no prompt in the way: a destructive command, a commit or push on the wrong branch, work lost.

The file: a section per direction, each item with its quotes, their source and absolute date, how often, and a proposal: the rule to add, narrow or delete, in which profile's settings file, with what it would have changed in the period. A proposed auto mode change names the critique max can run on it once it is applied, `claude auto-mode critique`. Nothing in the file changes a setting: what max takes up, he applies in a session. Reply with the file's path alone.
