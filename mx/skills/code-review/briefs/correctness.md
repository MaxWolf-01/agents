## Correctness: does the change work, without breaking callers, contracts or edge cases?

Trace the change end to end: touched files in full, callers of changed functions, changed types/protocols/contracts, related tests.

Report only findings that survive three filters: (a) it's a real problem, not an artifact of reading the diff in isolation: check surrounding code and existing patterns first; (b) you can name the concrete consequence (bug, security hole, data loss, perf regression, maintenance trap); no nameable consequence, no finding; (c) the codebase doesn't already handle it.

Not findings: style the change is internally consistent about, validation for inputs that can't arrive, API semantics that match existing conventions, "what if X" where the system prevents X.

Each finding: the scenario that breaks, file:line, fix.
