# What GitHub does with a stack

The files beside this one describe the CLI. This one describes the server, which treats a stack
the same way however it was created. The feature's own documentation:
<https://docs.github.com/en/pull-requests/get-started/about-stacked-prs>

## Why a stack rather than a chain of bases

The bottom PR's base is the stack's **trunk**, and the trunk's merge requirements, branch
protection and CI govern every layer, mid-stack PRs included, although those target a feature
branch. Chaining PRs by base alone gives an upper layer whatever checks a PR against a feature
branch happens to trigger, which is usually fewer.

## Merging

Layers merge bottom up, on GitHub. Merging one PR merges every unmerged PR below it, so merging
the top merges the whole stack: pick the layer you mean. The PRs above the merged one stay open,
retarget to the stack's base, and are rebased server-side. Merge commit, squash and rebase all
work, and the history that results is the same as merging each layer in turn.

## Linking PRs that already exist

`gh stack link <lower-pr> <upper-pr> --base <trunk> --remote <name>` records the chain and writes
no local state (`commands.md`). Pass `--base`: it defaults to the repository's **default** branch,
which is not always the branch the work integrates into. In a repo whose default is `main` while
feature work targets `development`, leaving it off makes `link` rewrite the bottom PR's base to
`main`, since it corrects any base that disagrees with the chain.

## "This stack is out-of-date with its base branch"

The stack's bottom branch is behind the trunk. The layers above it are not the subject, and each
still shows its own diff correctly, because GitHub diffs a PR from its merge base.

Nothing is blocked unless the trunk requires branches to be up to date before merging. Read that
from the branch protection: `gh api -X GET repos/<owner>/<repo>/branches/<trunk>/protection`,
where a 404 means unprotected.

**Rebase stack** rewrites every branch in the stack, so each local copy has to be reset to the
remote afterwards, and review comments on the rewritten commits are marked outdated. It belongs
right before the bottom layer merges, not in the middle of a review.
