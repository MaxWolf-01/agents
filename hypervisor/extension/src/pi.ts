import path from "node:path";

/** pi's command line, as this package installs it. */
export const PI = path.resolve(import.meta.dirname, "../node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js");

/** The model the hypervisor runs on. */
export const MODEL = "anthropic/claude-opus-5-5";
