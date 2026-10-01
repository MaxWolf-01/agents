import type { ToolDefinition } from "@earendil-works/pi-coding-agent";
import type { Config } from "./index.ts";
import { NotImplemented } from "./not-implemented.ts";

/**
 * The explorer's read tools. A tool takes what it reads as `path`: absolute, under `~/`, or relative to `home`. It
 * throws on a path under a denied root (keys, credential stores, browser profiles and caches, as ruled under
 * `hypervisor-property-checks` D5), judged once `..` and symlinks are resolved, and a search or listing passes over
 * those roots.
 */
export function exploreTools(_config: Pick<Config, "home">): ToolDefinition[] {
	throw new NotImplemented("hypervisor-explore-mode");
}
