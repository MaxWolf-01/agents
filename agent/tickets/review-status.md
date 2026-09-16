---
status: claimed
---

# A `review` status: a build waiting for the user's ruling has its own state and its own group on the board

Ruled by the user on 2026-09-16 while working the Helferline tracker, where five builds sat in the board's folded "done" group with nobody having ruled on them: since 0.1.58 a build waits on its ticket branch for the ruling, and the status set had no word for that wait, so `claimed` and `done` each covered two things.

## What to build

- `review` joins the status set (`/mx:tracker`, MARKDOWN.md): the worker's last act sets it instead of `done`; the orchestrator sets it on the feature branch when it renders the review page. `done` keeps one meaning: the user accepted and the branch merged. `review` unblocks nothing, as `claimed` does not.
- The board groups `review` tickets under **needs my review**, beside the needs-human queue; the queue then carries only what the user must do beyond reading the review page.
- A `gh` frontmatter field, a list of `owner/repo#number` references, holds the pull requests and issues a ticket produced or tracks, however many repositories they span; the board renders each as a link on the ticket's row. Resolving each reference's live state (open, merged, changes requested) is a later ticket.
- The four outcomes of a ruling read against the new state: accept writes `done`, amend takes the ticket back to `claimed` while the worker revises, redo resets it to `open`, reject deletes it.
- The dispatch scripts write the flips they own (`dispatch claim`, `dispatch review`, the runner's retry check), and the dispatch and tracker skills describe the flow in the new terms.

## Acceptance criteria

- [ ] The board renders a `review` ticket in a **needs my review** group placed right after the queue, in its own colour in rows and graph, and a ticket blocked on it stays blocked until it is `done`.
- [ ] A ticket with `gh: [owner/repo#1, other/repo#2]` shows both as links to GitHub on its row.
- [ ] `dispatch claim` takes a `review` ticket back to `claimed`; `dispatch review` writes `review` on an unmerged branch and `done` with the range on a merged one.
- [ ] The worker contract, the runner and the dispatch skill name `review` as the worker's last act, and no skill still describes `done` as the worker's flip.
- [ ] `make test` and `make check` pass.
- [ ] Demo in the closing comment: a board rendered with a `review` ticket and a `gh` list, and the two `dispatch review` flips in a throwaway repo.
