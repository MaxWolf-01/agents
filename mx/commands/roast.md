---
description: Bird's-eye critical review of codebase architecture, coupling, code smells, and structural debt
---

High-level critical review. Architecture, coupling, code smells, structural debt, naming, abstraction quality. Default scope is the entire codebase unless the user narrows it.

## How to approach this

1. **Build the big picture yourself first.** Read project knowledge and documentation. Then read key code files — entry points, core abstractions, the things everything else depends on.

2. **Delegate depth to subagents.** Fan out subagents to review areas you haven't read directly. Give each one the context it needs (relevant docs, key interfaces, architectural constraints) so it can form a real opinion, not just pattern-match on isolated files. Codex subagents (via `/mx:codex`) have ~400k context — don't restrict them to narrow slices. Let them integrate larger areas; only split across multiple codex instances when the codebase genuinely exceeds what one can hold.

3. **Synthesize critically.** Subagents only see a subset — their conclusions can be outright wrong due to missing context, not just imprecise. You've read the core and higher-level knowledge yourself; use that to judge what's trustworthy and what's a misunderstanding.

## What to look for

- Architecture: is the structure serving the project or fighting it?
- Coupling: what's tangled that shouldn't be? What breaks when you touch X?
- Abstractions: too many layers? Too shallow? Missing ones that would simplify?
- Code smells: duplication, dead code, naming that lies, implicit conventions
- Debt: shortcuts that compound, patterns that don't scale, things the next developer will curse

Be specific. "The auth module is tightly coupled" is useless. "AuthService depends on 4 unrelated modules because it handles both session management and permission checks" is a roast.
