import type { ToolDefinition } from "@earendil-works/pi-coding-agent";
import { NotImplemented } from "./not-implemented.ts";

/**
 * The explorer's read tools over the machine whose home directory is `home`. A tool takes what it reads as `path`,
 * absolute, under `~/`, or relative to `home`. It throws on a path under a denied root (`~/work`, secrets, keys,
 * credential stores, browser profiles), judged once `..` and symlinks are resolved, and a search or listing passes
 * over those roots.
 */
export function exploreTools(_config: { home: string }): ToolDefinition[] {
	throw new NotImplemented("hypervisor-explore-mode");
}
