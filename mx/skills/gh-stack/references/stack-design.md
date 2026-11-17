# Designing a stack

## Contents

- [Plan the layers before writing code](#plan-the-layers-before-writing-code)
- [Branch naming](#branch-naming)
- [Staging changes deliberately](#staging-changes-deliberately)
- [When to add a layer](#when-to-add-a-layer)
- [One stack, one story](#one-stack-one-story)

## Plan the layers before writing code

A stack is a dependency chain: what a layer depends on lives in the same branch or a lower one.
Plan that order up front, since there is no non-interactive in-place reorder and fixing the order
means `unstack` and `init` again.

```
(main) <- todo-app/models <- todo-app/api <- todo-app/frontend <- todo-app/integration
```

- `todo-app/models` — shared types and schema
- `todo-app/api` — routes that use the models
- `todo-app/frontend` — components that call the routes
- `todo-app/integration` — tests exercising the whole feature

The names are illustrative: take the stack topic and layer names from the actual task.

## Branch naming

Name a branch `<topic>/<concern>` (`billing/schema`, `billing/api`, `billing/ui`), so a stack's
branches read as related rather than as generic names that could belong to any stack. **User and repository branch
naming conventions take precedence.**

Passing `-m` without a branch name generates the name from the commit message in date-and-slug form
(`03-24-add_api_routes`); name the branch yourself.

## Staging changes deliberately

Use `git add` and `git commit` directly rather than the `add -Am` shortcut, to control which changes
land in which branch.

A branch may hold several commits, as long as every one serves its concern; a change belonging to a
different concern goes in a different branch.

## When to add a layer

Add a branch when you start a **different concern that depends on what you have built so far**.
Signals:

- Moving from backend to frontend, or from core logic to tests or documentation
- The next changes have a different reviewer audience
- The current branch's diff is already large enough to review on its own

A layer that cannot be described in one sentence is usually two layers.

## One stack, one story

A stack should read as a coherent progression: a reviewer walks the PRs bottom to top and sees the
feature being built.

**Use a single stack** when every branch serves the same feature or project, even if the layers span
different concerns.

**Start a separate stack** for unrelated work, even work you happened to do alongside: a different
feature, an unrelated bug fix, an independent refactor.

A trivial incidental fix can ride along in the current stack until it grows into its own project.
