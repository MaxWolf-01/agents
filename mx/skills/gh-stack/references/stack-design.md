# Designing a stack

## Contents

- [Plan the layers before writing code](#plan-the-layers-before-writing-code)
- [Branch naming](#branch-naming)
- [Staging changes deliberately](#staging-changes-deliberately)
- [When to add a layer](#when-to-add-a-layer)
- [One stack, one story](#one-stack-one-story)

## Plan the layers before writing code

A stack is a dependency chain. If code in one layer depends on code in another, the dependency must
live in the same branch or a lower one. That constraint is much cheaper to satisfy by planning than
by restructuring later, because there is no non-interactive in-place reorder — fixing the order
means`unstack` and `init` again.

Decide the layers first, then write code into them:

```
(main) <- todo-app/models <- todo-app/api <- todo-app/frontend <- todo-app/integration
```

- `todo-app/models` — shared types and schema
- `todo-app/api` — routes that use the models
- `todo-app/frontend` — components that call the routes
- `todo-app/integration` — tests exercising the whole feature

This is illustrative. Infer the stack topic and layer names from the actual task; do not reuse
`todo-app` or these layer names literally.

## Branch naming

Prefer a shared topic prefix plus the layer's concern:
`<topic>/<concern>` — for example, `billing/schema`, `billing/api`, `billing/ui`.
This keeps related branches recognizable without using generic names that could belong to any
stack. **User and repository branch naming conventions take precedence; follow them instead.**

If you pass `-m` without a branch name, the name is generated from the commit message in
date-and-slug form (for example `03-24-add_api_routes`). Prefer naming the branch yourself.

## Staging changes deliberately

Use `git add` and `git commit` directly rather than the `add -Am` shortcut. The point is control
over which changes land in which branch.

Multiple commits per branch are fine. What matters is that every commit in a branch serves the same
concern, and that a change belonging to a different concern goes in a different branch.

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

**Start a separate stack** for unrelated work — a different feature, an unrelated bug fix, an
independent refactor. Do not mix efforts into one stack just because you happened to work on both.

A trivial incidental fix can ride along in the current stack. Once it grows into its own project, it
deserves its own stack.
