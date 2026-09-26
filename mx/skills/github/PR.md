# A PR body

A PR body describes a change, so change narration ("now", "no longer", "before this"), which writing-for-humans treats as residue in an artifact, is its point here. Every other rule of writing-for-humans holds.

## Shape

Most PRs are the first two parts, and a PR that is one paragraph is one paragraph. Everything after them appears only when it exists, in this order:

1. **The change**: what behaviour changes and why it matters to someone. On most PRs this is the change summary, `git diff <base>...HEAD | change-summary`: a paragraph from a model that saw only the diff, so nothing from the session that made the change (ticket jargon, "as discussed") reaches it. Correct what it gets wrong; write the paragraph yourself where the point is something the diff cannot show.
2. **The issue link**, one line (`Closes #123`), when there is an issue. The body links it and leaves its content there.
3. **What the diff, the issue and CI cannot say**, a short paragraph each: a step someone must take around the merge, a merge order across PRs or repos, what went unverified where that is worth a reader's time. Shorter wins when in doubt. The commands that were run are CI's to report. Alternatives not taken appear only when the issue discussed them or max asks for them.
4. **A figure** sits beside the text it explains.
5. **`<details>` blocks** hold anything bigger that not every reader needs right away.

Headings are available, not owed.

## Publishing

After max's yes, the file he saw becomes the body: `gh pr create --body-file <file>` for a new PR, `gh pr edit <n> --body-file <file>` for one that exists, each PR `gh stack submit` opened included.
