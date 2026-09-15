---
status: done
blocked-by: [01]
diff: [a9117ac7a51491b2ba3f5109064acf744f6d95b5..84d17c74fbb9235d174ce6d37c702e5f8c1a31ee]
---

# Review reports stay on disk; the user gets the page and their calls

## What to build

The code-review skill stops producing the one standalone chat message that carries every finding verbatim. The reviewers write their reports to `agent/reviews/<fixed7>..<head7>/<axis>.md`, the range being the one they reviewed, and the reports are not deleted after reading. The per-brief word caps (400 per axis, 600 in light mode) go; the three filters in the Correctness brief, the hard-violation versus judgment split in the Standards brief, and the per-finding shape (scenario, file:line, fix) bound length instead. The Standards brief receives the prose catalogue of ticket 01 by absolute path, for every diff.

What the caller does with the reports is the aggregation rule, stated once for every caller: the session or worker that owns the branch reads the reports, applies accepted findings as `Workflow-stage: review` commits, writes declined findings as anchored `Assumptions` entries (the ticket's existing A-id mechanism) so the review page projects them onto their lines, and writes a finding index into its closing comment: one line per finding, fixed → commit, declined → assumption id, under the review range. What reaches the user, in chat and on the page: the review page; the calls only they can make (declined findings, assumptions, open questions); next steps and blockers. No findings verbatim, no verification list, no per-axis summary. The chat message has the landing shape the spec's Decisions define: one outcome line, the demo, "I need from you" as a numbered list of the user's calls each tagged `[Dn]`, then "Details, if you want them" tagged in the same numbering; a reply naming a tag expands that entry. A standalone "review this branch" with nothing fixed anchors its findings on the page as notes and lists in chat only those needing a ruling.

The project-setup skill adds `agent/reviews` to the project's own ignore file beside `agent/research`, since a worker host clones the repo and has no global ignore.

## Acceptance criteria

- [x] Reviewers write to the range-named directory and nothing deletes the reports; the skill's step 5 describes aggregation by the branch owner and what reaches the user, in place of the standalone message.
- [x] No word cap remains in any brief; the filters and the per-finding shape are what bound a report.
- [x] The Standards brief lists the catalogue by path among its standards sources.
- [x] Light mode follows the same delivery rule.
- [x] project-setup ignores `agent/reviews` in the project's ignore file.
- [x] Property, reviewed: no finding a worker already fixed reaches the user; the user reads a review as a page plus the calls they must make.
- [x] Demo in the closing comment: a light review run on this ticket's own branch, showing the report files on disk and the closing message the user would read.

## Comments

### Closing, worker on `ticket/one-flow/04-review-delivery`

Review reports now live at `agent/reviews/<fixed7>..<head7>/<axis>.md` and nothing deletes them; code-review's step 5 is the caller's disposition rule and its delivery rule, in place of the standalone message; the word caps are gone from all five briefs; project-setup ignores `agent/reviews`. Two commits on `ticket/one-flow/04-review-delivery`, `8e0bf45` and `7d06283`, unmerged.

**Demo.** This comment is the output. A light review and a Spec axis ran against `8e0bf45`, wrote their reports to the range directory, and what you are reading is the closing message the new rule produces for them: eleven of the sixteen findings were fixed on the branch and none of them is here except as an index line under `[D4]`.

```
$ ls -l 'agent/reviews/a9117ac..8e0bf45/'
-rw-r--r-- 1 agent agent 13471 Sep 15 00:27 light.md
-rw-r--r-- 1 agent agent 17246 Sep 15 00:24 spec.md

$ git check-ignore -v 'agent/reviews/a9117ac..8e0bf45/light.md'
.gitignore:3:agent/reviews	agent/reviews/a9117ac..8e0bf45/light.md

$ git status --short        # the reports never enter the diff
```

The reports are readable at those paths in this worktree until it is cleaned up, and the review page for the two commits is the durable surface.

**I need from you**

1. `[D1]` Which generated agent artefacts a dispatched repo's own `.gitignore` carries. This ticket named `agent/reviews`; `agent/transcripts`, `agent/handoffs`, `agent/diffviews`, `agent/board.html` and its stamp are the same kind of thing, and `4f3d851` deleted the board entries from this repo's ignore file seven days ago on the grounds the global ignore covers them, which a cloned worker host does not have. Both reviewers flagged the gap. See `[D5]`, A4.
2. `[D2]` Whether the review range's left end is the fixed point or the merge-base. The spec settles the path as `<fixed7>..<head7>`, so it is written that way; when the fixed point is a branch that moved since the fork, the range in the finding index reconstructs a different change set than the one reviewed. One line to change if you want the merge-base. See `[D5]`, A2.
3. `[D3]` Whether `Filed` stays a third disposition beside fixed and declined. The spec's index has two. See `[D5]`, A1.

**Details, if you want them**

4. `[D4]` **Finding index**, reports under `agent/reviews/a9117ac..8e0bf45/`, fixes in `7d06283`.

   - light 1 / spec S1, `review-pr` still ordered the deleted aggregated message and an incoming PR had no disposition path → fixed.
   - light 2, the landing message handed the user report paths that `dispatch ctl cleanup` deletes at landing, on a possibly remote host → fixed, the range and the finding index go in the details slot instead.
   - light 3 / spec S5, nothing checked a report file existed, which is the failure ticket 02 recorded as friction → fixed, step 5 confirms the files before reading.
   - light 4, `Declined` stated its format but no entry criterion → fixed.
   - light 5, the assumption format was restated without the id rule that governs it → fixed, it points at `/mx:implement`.
   - light 6 / spec S6, project-setup listed five directories where the ticket named one, and this repo honoured two → narrowed to the two the ticket named; the rest is `[D1]`.
   - light 7, the range names the fixed point while the diff is three-dot → declined, A2.
   - light 8 / spec S2, the ticketless case covered declines but not the index → fixed.
   - light 9a, the first commit body used a binary contrast (catalogue rule 47) → noted, the commit is written.
   - light 9b, the Standards brief re-enumerated step 3's sources and the copy had already diverged → fixed, it names `CATALOGUE.md` and leaves the list to step 3.
   - light 9c, the landing shape's vocabulary lives in the output style and now here → declined, A3.
   - spec S3, nothing said the report directory is ephemeral, so a repo that never ran project-setup commits its reports → fixed, step 4 says gitignored, for the life of the worktree.
   - spec S4, the ticket's own bookkeeping → fixed, this comment.
   - spec S7, three dispositions where the spec's index names two → declined, A1.

5. `[D5]` **Assumptions.**

   - A1 `mx/skills/code-review/SKILL.md:85`: (amended 2026-09-15, ruled in: `ccc3cc7` put the three dispositions in the spec) `Filed` is a third disposition, where the spec's finding index named two. The path predates this ticket (it was the last line of the old step 5) and a filed finding needs a row or it disappears from the user's view. Fold it into `Declined` to reverse.
   - A2 `mx/skills/code-review/SKILL.md:21`: (amended 2026-09-15, reversed: `780944e` made the merge-base the left end, which is the alternative this call offered) the range directory was named after the fixed point's own sha, per the spec's `<fixed7>..<head7>`, not the merge-base the three-dot diff reads from. `git rev-parse --short=7 $(git merge-base <fixed-point> HEAD)` is the other end.
   - A3 `mx/skills/code-review/SKILL.md:92`: code-review names the landing message's section titles and its `[Dn]` tag, whose home is `claude/output-styles/max.md:10`. It maps the review's output onto the slots rather than restating the rule, because a worker carries the worker prompt and not the output style; ticket 06 is where the third site would appear.
   - A4 `mx/skills/project-setup/SKILL.md:14`: the ignore rule lists the two directories this ticket named and stops there, rather than every generated agent artefact. See `[D1]`.
   - A5 `mx/skills/review-pr/SKILL.md:19`: a PR review delivers its findings to the PR's comments or the reply, since a stranger's repo holds no ticket to anchor an assumption in and the branch is not the caller's to commit to. Written here because the alternative was leaving one caller instructed two ways.

6. `[D6]` **Friction.**

   - Working a ticket that rewrites the review skill means the installed plugin still carries the old rule: the loaded `/mx:code-review` would have had me delete the reports. I ran the review by hand from the branch's own text. Any ticket that edits a skill it must also run has this shape, and the worker has no way to load the skill from its worktree.
   - `git rev-parse --short=7 <a> <b>` takes a single revision, so the first draft of step 1's range command did not run. Running it caught that; a skill whose prose is the logic has no other check.
   - No `python3` on this host, as ticket 01 recorded. `sed`, `awk` and heredocs did the text surgery.
