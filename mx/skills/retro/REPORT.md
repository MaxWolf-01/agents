# The living report

One report per repo, `retro/report.md` in that repo's agent repo, rewritten whole by every run; git history holds every run's copy. Runs read it as markdown; max reads the page built from it, `retro/report.html`. Sessions write max's verdicts into it between runs, so a run reads them there.

## Rules

- **Every finding quotes its evidence**: the session (its id's first 8 characters), the commit (its short sha) or the report it comes from, with an absolute date, `2026-10-07`. Never "last week", never a session's offset.
- **Every proposal names what it deletes or narrows.** One that adds a mechanism also names the recurrence behind it and what keeping it costs.
- **An id lives as long as its finding**: `F<n>` for a finding, `A<n>` for an architecture candidate. A finding keeps the id the run that raised it gave it; a new one takes the next number after the highest the `ids:` line records, and an id is never given twice, a dropped one included.
- **A dismissal holds**: a finding or candidate max dismissed stays under Dismissed, with his verdict and its date, and returns only on evidence dated after his verdict, which it names.
- **The report proposes; it files nothing and changes no ticket.** What max rules on a finding, in a session, becomes tickets there.

## max's verdicts

A session that hears max rule on a finding or candidate writes the verdict into the report, quoting him with the date, and commits it in the agent repo's main checkout, where runs read it, with `git commit -- retro/report.md`: the pathspec commits that file alone and leaves whatever else is staged there. The page is left as it is; the next run rebuilds it.

- **Dismissed**: the finding leaves Findings, or the candidate Architecture candidates, for a line under Dismissed.
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

Deletions and narrowings come first. A defect class that recurs and that a tool could catch gets its check proposed, weighed like any other fix. A pattern rooted in the model's own habit, with no line to delete, is reported as that, with what was tried. A count backs a finding and is never a number a later run tries to move.

## Shape, in this order

```markdown
# Workflow retro: <repo>

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

## Architecture candidates

In order of impact. Each `### A<n> <the deepening it proposes>`, with `/mx:improve-codebase-architecture`'s fields (files, problem, solution, benefits, invariant, dependency category, strength, impact, ADR conflict, related candidates), the friction that pointed at it with its date, its state and its history as a finding's.

## Proposed tickets

The agents repo's proposed tickets, as `proposed.md` names them, grouped by the cause they share. Each group: its slugs, the cause in a sentence, and the finding or candidate it is (`F<n>`, `A<n>`), or "no finding". A ticket that shares its cause with no other stays out.

## Versions

A few lines on what changed with the mx releases, Claude Code versions and models in the period, stated as differences that came with them, never as their causes.

## Dismissed

Each finding or candidate max dismissed: id, title, his verdict quoted with its date. A line here is the whole of it, until newer evidence brings it back.
```

A dropped finding leaves the report: the line in What changed that drops it is its last mention, and the `ids:` line keeps its number from being given again.
