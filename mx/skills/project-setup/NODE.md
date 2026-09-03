# Node / TypeScript

- pnpm throughout: its `node_modules` exposes only declared dependencies, so a phantom import (a package reachable only transitively) fails at once instead of in CI after a dependency bump. Existing repos keep their package manager; converting a lockfile is a decision, not a default.
- Toolchain from the flake: `nodejs` + `pnpm`, the two things npm cannot install. `.envrc` = `use flake` + `layout node` (puts `node_modules/.bin` on PATH).
- Node runs TypeScript directly; no build step for dev or tests. `tsc` typechecks and emits declarations, nothing else.
- tsconfig: `strict`, `module: "nodenext"`, `erasableSyntaxOnly: true`; the last makes tsc reject TS syntax node cannot strip (enum, parameter properties, namespaces), which is what keeps running `.ts` directly safe.
- Tests: `node --test`, built in, runs `.ts`, has watch and coverage. A test-runner dependency enters when a browser DOM does.
- biome for lint + format: one binary, one config. Exception, by availability not preference: frameworks whose lint rules exist only as eslint plugins (Angular, react-hooks) keep eslint.
- package.json: `"type": "module"`; scripts `check`, `test`, `build` are the source of truth; the Makefile delegates (`pnpm run <script>`) so the core targets stay the uniform door.
