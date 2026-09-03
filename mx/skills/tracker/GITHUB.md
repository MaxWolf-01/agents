# Tracker backend: GitHub Issues

Specs and tickets for this repo live as GitHub issues. Use the `gh` CLI for all operations; it infers the repo from `git remote -v` inside a clone.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`.
- **List issues**: `gh issue list --state open --json number,title,body,labels` with `--label` / `--state` filters as needed.
- **Comment**: `gh issue comment <number> --body "..."`, the equivalent of a ticket file's `## Comments`.
- **Labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`.
- **Close**: `gh issue close <number> --comment "..."`.

## Publish / fetch

- "Publish to the issue tracker" → create a GitHub issue. A feature's spec is one issue; its tickets are sub-issues of the spec issue, with blocking edges via GitHub's native issue dependencies.
- "Fetch the ticket" → `gh issue view <number> --comments`, **and** the spec issue it belongs to; tickets don't repeat the feature context, the spec carries it.

## Ticket state

- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write. An open, unassigned issue is unclaimed.
- **Unblocked**: every blocker closed (`issue_dependencies_summary.blocked_by` reports open blockers only).
- **Retire**: close the issue. Closed issues stay readable forever; no cleanup step.

## Wayfinding operations

Used by `/mx:wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Destination / Notes / Decisions-so-far / Not-yet-specified / Out-of-scope body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api -X GET repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker or an assignee; first in map order wins.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
