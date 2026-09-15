---
status: claimed
blocked-by: [01]
---

# Review reports stay on disk; the user gets the page and their calls

## What to build

The code-review skill stops producing the one standalone chat message that carries every finding verbatim. The reviewers write their reports to `agent/reviews/<fixed7>..<head7>/<axis>.md`, the range being the one they reviewed, and the reports are not deleted after reading. The per-brief word caps (400 per axis, 600 in light mode) go; the three filters in the Correctness brief, the hard-violation versus judgment split in the Standards brief, and the per-finding shape (scenario, file:line, fix) bound length instead. The Standards brief receives the prose catalogue of ticket 01 by absolute path, for every diff.

What the caller does with the reports is the aggregation rule, stated once for every caller: the session or worker that owns the branch reads the reports, applies accepted findings as `Workflow-stage: review` commits, writes declined findings as anchored `Assumptions` entries (the ticket's existing A-id mechanism) so the review page projects them onto their lines, and writes a finding index into its closing comment: one line per finding, fixed → commit, declined → assumption id, under the review range. What reaches the user, in chat and on the page: the review page; the calls only they can make (declined findings, assumptions, open questions); next steps and blockers. No findings verbatim, no verification list, no per-axis summary. The chat message has the landing shape the spec's Decisions define: one outcome line, the demo, "I need from you" as a numbered list of the user's calls each tagged `[Dn]`, then "Details, if you want them" tagged in the same numbering; a reply naming a tag expands that entry. A standalone "review this branch" with nothing fixed anchors its findings on the page as notes and lists in chat only those needing a ruling.

The project-setup skill adds `agent/reviews` to the project's own ignore file beside `agent/research`, since a worker host clones the repo and has no global ignore.

## Acceptance criteria

- [ ] Reviewers write to the range-named directory and nothing deletes the reports; the skill's step 5 describes aggregation by the branch owner and what reaches the user, in place of the standalone message.
- [ ] No word cap remains in any brief; the filters and the per-finding shape are what bound a report.
- [ ] The Standards brief lists the catalogue by path among its standards sources.
- [ ] Light mode follows the same delivery rule.
- [ ] project-setup ignores `agent/reviews` in the project's ignore file.
- [ ] Property, reviewed: no finding a worker already fixed reaches the user; the user reads a review as a page plus the calls they must make.
- [ ] Demo in the closing comment: a light review run on this ticket's own branch, showing the report files on disk and the closing message the user would read.
