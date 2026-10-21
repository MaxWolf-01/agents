# The living report

One report per tracker, `retro/report.md` in its agent repo, over every repo the tracker plans, rewritten whole by every run; git history holds every run's copy. Runs read it as markdown; max reads the page built from it, `retro/report.html`. Sessions write max's verdicts into it between runs, so a run reads them there.

## Rules

- **Every finding quotes its evidence**: the session (its id's first 8 characters), the commit (its short sha) or the report it comes from, with an absolute date, `2026-10-07`. Never "last week", never a session's offset.
- **Every proposal names what it deletes or narrows.** One that adds a mechanism also names the recurrence behind it and what keeping it costs.
- **An id lives as long as its finding**: `F<n>` for a finding, `A<n>` for a candidate, of any code lens. A finding keeps the id the run that raised it gave it; a new one takes the next number after the highest the `ids:` line records, and an id is never given twice, a dropped one included.
- **A dismissal holds**: a finding or candidate max dismissed stays under Dismissed, with his verdict and its date, and returns only on evidence dated after his verdict, which it names.
- **The report proposes; it files nothing and changes no ticket.** What max rules on a finding, in a session, becomes tickets there.

## max's verdicts

A session that hears max rule on a finding or candidate writes the verdict into the report, quoting him with the date, and commits it in the agent repo's main checkout, where runs read it, with `git commit -- retro/report.md`: the pathspec commits that file alone and leaves whatever else is staged there. The page is left as it is; the next run rebuilds it.

Just before that commit, look for a run in flight, `pgrep -af '[r]etro_run'`: it read the report when it began, and leaves its own uncommitted when the report changes under it. While one runs, hold the verdicts and wait for it to end, then write them into the report as it stands.

- **Dismissed**: the finding leaves Findings, or the candidate Candidates, for a line under Dismissed.
- **Amended**: the finding is rewritten as he said, and its History gains `amended by max <date>: "<his words>"`.
- **Taken up**: its State becomes `taken up as <ticket>`, and its History gains `taken up as <ticket> <date>`, one entry per ticket filed.
- **A candidate the report lacks**, ruled in a session's own architecture review, enters it with its verdict under the next id: `A<n+1>` for the `ids:` line's `A<n>`. The session raises the `ids:` line to that id.

What changed is the next run's to write. A verdict's commit carries no `Retro-until:` trailer: that trailer marks a run's commit, and the next run's period starts where the last such commit's ended.

## The weighing

What orders the findings and decides what a run reports, loosely, on four things together:

1. **What the friction costs**: time and energy, max's first.
2. **What preventing it costs to keep**: code, prose and workflow machinery carry upkeep for as long as they live; a one-time cost amortizes.
3. **How often it happens**, and is expected to.
4. **How robust the available fix is**: whether it simplifies or adds, and whether mechanism can fix it at all, or a better model or the harness's makers will fix the quirk first.

Deletions and narrowings come first. A defect class that recurs gets the shape of the code that would make it impossible to write, where one would, and otherwise the check a tool could make, weighed like any other fix. A correction of a fact, an agent lacking what max had to tell it, enters as a finding once its class recurs; seen once, it goes under Watched. A pattern rooted in the model's own habit, with no line to delete, is reported as that, with what was tried. A count backs a finding and is never a number a later run tries to move.

A candidate is weighed the same way; its **Weighing**, or an architecture candidate's impact, orders the Candidates section.

### What is already written

Before a finding or candidate enters the report, look for the guidance that already covers its case: a skill, a `CLAUDE.md`, a doc or a rule the agent reads, in the repos and skills the run can read. What is there decides:

- **Guidance that covers the case clearly, where the agent reads it as it acts**, makes it an execution problem. Seen once, it proposes nothing, and goes under Watched as one line. Once it recurs (a Watched line seen again, or the same miss in two sessions), or once it costs max significant time, attention or tokens, it is a finding, and its proposal moves the guidance up a rung of the agents repo's `PRINCIPLES.md` #1, as high as will hold: the code shaped so the mistake cannot be written; then a lint, type, test or script that goes red on it; then a line of a reviewer's checklist. The written line is retired once the mechanism covers it.
- **Guidance that covers it where the agent does not read it as it acts** (buried in a long file, under a heading about something else, behind a pointer that does not fire) gets a placement fix: the proposal moves the guidance to where the agent acts, and writes no second copy of it.
- **A skill the model invokes itself that held the guidance and did not fire** in the sessions gets a proposal to tune its description, the trigger that decides when it fires.

## Shape, in this order

A repo retro's report has no Versions.

```markdown
# <Workflow retro | Repo retro>: <the project>

Run <date of the period's end>, over <start> to <end>. ids: F<highest>, A<highest>

## What changed since <the last run's date>

One line per finding or candidate added, sharpened, amended, dropped or whose state moved (taken up, fix landed, held, back), with its id and why.

## Top recommendation

The one proposal to act on first, and why it wins the weighing.

## Findings

In order of the weighing.

### F<n> <what the friction is, in plain words>

- **Lens**: max | agents | mechanism
- **State**: live | taken up as <ticket> | fix landed <sha>, <date> | held | back since <date>
- **Evidence**: two or three quotes, each `"<verbatim>"` (<source>, <date>)
- **Cause**: what produces it, by path and line where it is a file (`mx/skills/dispatch/SKILL.md:42`), or the habit
- **Proposal**: the smallest fix: what it deletes or narrows, and where it lands (a deletion, a check, a line of the reviewer's baseline, a skill line, a tool)
- **Weighing**: cost of the friction, upkeep of the fix, how often, how robust
- **History**: first seen <date>; held in the runs of <dates>; taken up as <ticket> <date>; landed <sha> <date>; held or back

## Candidates

What the lens pass proposes for the code, every code lens's together, in order of impact. Each `### A<n> <the change it proposes>`:

- **Code lens**: the section of `stages/lens-pass.md`'s The code lenses it came from
- **Files**, **Problem** with its evidence, **Proposal** and **Weighing**, as a finding's; an architecture candidate carries `/mx:improve-codebase-architecture`'s fields beside them, its **Proposal** standing for the solution (benefits, invariant, dependency category, strength, impact, ADR conflict, related candidates)
- **Pointed at by**: the commits, proposed tickets, friction or corrections of max's that pointed the pass at it, each with its date
- **State** and **History**, as a finding's

## Proposed tickets

The repo's proposed tickets, as `proposed.md` names them, grouped by the cause they share. Each group: its slugs, the cause in a sentence, and the finding or candidate it is (`F<n>`, `A<n>`), or "no finding". A ticket that shares its cause with no other stays out.

## Watched

Each execution problem, and each correction of a fact, seen once, as one line: `- <what the agent missed>: <the guidance that covers it, by path, or the fact it lacked>. "<verbatim>" (<source>, <date>)`. A run that sees one again makes it a finding, weighed as a repeat, both sightings its evidence. A line no run has seen again in the eight weeks after its date leaves.

## Versions

A few lines on what changed with the mx releases, Claude Code versions and models in the period, stated as differences that came with them, never as their causes.

## Dismissed

Each finding or candidate max dismissed: id, title, a candidate's code lens, his verdict quoted with its date. A line here is the whole of it, until newer evidence brings it back.
```

A dropped finding leaves the report: the line in What changed that drops it is its last mention, and the `ids:` line keeps its number from being given again.
