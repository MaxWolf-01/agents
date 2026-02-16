---
name: implement
description: Pre-implementation gate and coding guidelines. Load before writing code — verifies readiness and sets the implementation lens.
---

# Implement

Conditions for implementing:
- The task is clear. Intent is aligned, constraints are known, open questions are clarified, and "done" is defined.
- You have a concrete plan for how to implement. All design / architecture decisions are made.
- The user told you to implement. You have their explicit approval on the concrete plan.

If that's not the case, STOP, clarify with the user, get their explicit approval on the concrete plan before proceeding.


During implementation: escalate issues to the user before resorting to hacks, "quick fixes", breaking assumptions, or deviating from intent.


## Coding Guidelines

- Write **lean, pragmatic code** that trusts both your environment and your readers. Favor clarity through simplicity over defensive programming and excessive documentation.
- Avoid over-engineering. Only make changes that are directly requested or clearly necessary. Keep solutions simple and focused.
- Don't create helpers, utilities, or abstractions for one-time operations. Don't design for hypothetical future requirements. The right amount of complexity (and abstraction) is the minimum needed for the current task. Reuse existing abstractions where possible and follow the DRY principle (but NOT dogmatically).
- Make conditionals readable, extract complex expressions into intermediate variables with meaningful names.
- Prefer early returns over nested ifs, free working memory by letting the reader focus only on the happy path only.
- Composition >>> inheritance
- Don't write shallow methods/classes/modules (complex interface, simple functionality). An example of shallow class: `MetricsProviderFactoryFactory`. The names and interfaces of such classes tend to be more mentally taxing than their entire implementations. Having too many shallow modules can make it difficult to understand the project. Not only do we have to keep in mind each module responsibilities, but also all their interactions.
- Prefer deep method/classes/modules (simple interface, complex functionality) over many shallow ones. 
- Don’t overuse language featuress, stick to the minimal subset. Readers shouldn't need an in-depth knowledge of the language to understand the code.
- Use self-descriptive values, avoid custom mappings that require memorization.
- Don’t abuse DRY, a little duplication is better than unnecessary dependencies.
- Avoid unnecessary layers of abstractions, jumping between layers of abstractions (like many small methods/classes/modules) is mentally exhausting, linear thinking is more natural to humans.
- **Organize files top-down (newspaper style):** Structure code for progressive disclosure — readers should get the big picture first, details as they scroll. Put main/public functions at the top, followed by their helpers in call order. Group related functions: Function A, then A's helpers, then Function B, then B's helpers, etc. Each "unit" reads top-to-bottom without jumping around. Especially critical for AI agents that may only read the first ~100 lines. Proactively refactor existing code to follow this pattern when working in a file.
- Access attributes directly / avoid unnecessary indirection via temporary variable assignments.
- Generally, don't put comments in __init__ files that could otherwise be empty (docs go in readmes on request, or for complex functions / modules / classes they can be handy). Similarily, inline code comments should be used sparingly, only when the code itself cannot be made clearer.
- Trust Your Environment: Assume known invariants. Don't add defensive checks for guaranteed conditions. Only validate at system boundaries (user input, external APIs).
- Don't use backwards-compatibility shims when you can just change the code (which you can, almost always, if not, you will be explicitly told / that should be made clear in the task definition). If you have doubts, escalate to the user instead of silently adding complexity.
- Assert in production, crash on violation. An assertion violation means the component already failed — crash it, let higher layers compensate. Fail fast, fail loudly.
    ```python
    config = config_store.get(user_id)
    assert config is not None, f"Expected config for {user_id}"
    # or: let KeyError propagate
    handler = HANDLERS[event_type]
    ```
    Don't silently swallow violations with fallback defaults or no-ops.
- Internalize style, conventions, and abstractions of the codebase before implementing new features or abstractions.

