import path from "node:path";

/** pi's command line, as this package installs it. */
export const PI = path.resolve(import.meta.dirname, "../node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js");

/** The model the hypervisor runs on. */
export const MODEL = "anthropic/claude-opus-5-5";

/**
 * The arguments that make pi the hypervisor: none of pi's own extensions, tools, skills, context files or prompt
 * templates, and the hypervisor's extension. `hv` starts pi's TUI with the same ones, which a check holds it to.
 */
export const HYPERVISOR = ["--no-extensions", "--no-builtin-tools", "--no-skills", "--no-context-files", "--no-prompt-templates", "-e", path.resolve(import.meta.dirname, "index.ts")];
