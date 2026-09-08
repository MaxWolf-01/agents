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

- "Publish to the issue tracker" → create a GitHub issue. A feature's spec is one issue; its tickets are **sub-issues** of the spec issue (`gh api` on the sub-issues endpoint; where sub-issues aren't enabled, a task list in the spec issue's body and `Part of #<spec>` at the top of the ticket body), with blocking edges as under Ticket state. Issues need ids before they can reference each other, so create the tickets first and wire the edges in a second pass.
- "Fetch the ticket" → `gh issue view <number> --comments`, **and** the spec issue it belongs to; tickets don't repeat the feature context, the spec carries it.

## Ticket state

- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write. An open, unassigned issue is unclaimed.
- **Type**: a decision ticket carries the label `type:<research|prototype|grilling|legwork>`; an unlabelled issue is a build ticket. It resolves with `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<ticket>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api -X GET repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the ticket body.
- **Unblocked**: every blocker closed (`issue_dependencies_summary.blocked_by` reports open blockers only).
- **Frontier**: the spec issue's open sub-issues (`gh issue list --state open`, scoped to them), minus any with an open blocker or an assignee; first by number wins.
- **Retire**: close the issue. Closed issues stay readable forever; no cleanup step.
- **Supersede** (`/mx:tracker`, Supersede): close the old issue with a comment naming its successor.
