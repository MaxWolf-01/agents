import { readdir } from "node:fs/promises";

/**
 * A path the model sent, made absolute: `~` and `~/` start at `home`, and so does a relative path. It is not
 * normalized, so a `..` after a symlink leaves from where the link points once the kernel resolves it.
 */
export function absolute(home: string, spelled: string): string {
	return spelled === "~" ? home : spelled.startsWith("~/") ? `${home}/${spelled.slice(2)}` : spelled.startsWith("/") ? spelled : `${home}/${spelled}`;
}

/** The Claude Code config directories in `home`, by name: `.claude`, and any `.claude-<profile>` beside it. */
export async function claudeConfigs(home: string): Promise<string[]> {
	return (await readdir(home).catch(() => [] as string[])).filter((name) => name === ".claude" || name.startsWith(".claude-"));
}

/** Whether `real` is `root` or lies below it. */
export const inside = (real: string, root: string) => real === root || real.startsWith(`${root}/`);

/** A resolved path as the model reads it: under `~/` when it is in `home`. */
export function shown(home: string, real: string): string {
	return inside(real, home) ? `~${real.slice(home.length)}` : real;
}
