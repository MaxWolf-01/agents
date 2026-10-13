// How much of max's weekly quota is used, read from the rate-limit headers Anthropic returns with each reply to a
// subscription's request, or from what Claude Code last handed its statusline, which the statusline keeps under
// `~/.cache/claude-statusline/<session id>.json`. Whichever reading is newer wins.

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

/** The week's quota at one moment: the share used, in percent, and when the week resets, both as their sources give them. */
export interface Week {
	/** Percent of the week's quota used, 0 to 100. */
	used: number;
	/** When the week resets, in ms since the epoch. */
	resets: number;
	/** When it was read, in ms since the epoch. */
	at: number;
}

/** The week from a reply's headers, whose names arrive lower-cased; none when the reply carries no weekly limit, as an API key's does not. */
export function weekFromHeaders(headers: Record<string, string>, at: number): Week | undefined {
	const used = Number(headers["anthropic-ratelimit-unified-7d-utilization"]);
	const resets = Number(headers["anthropic-ratelimit-unified-7d-reset"]);
	if (!headers["anthropic-ratelimit-unified-7d-utilization"] || !Number.isFinite(used) || !Number.isFinite(resets)) return undefined;
	return { used: used * 100, resets: resets * 1000, at };
}

/**
 * The newest week the statusline kept for the Claude Code account at `configDir`: its inputs carry the account's
 * `config_dir` and `written_at`, and `rate_limits.seven_day` as `used_percentage` and `resets_at`, in seconds. An
 * input of another account, or one that does not parse, is passed over.
 */
export function weekFromStatusline(cache: string, configDir: string): Week | undefined {
	let names: string[];
	try {
		names = readdirSync(cache).filter((name) => name.endsWith(".json"));
	} catch {
		return undefined;
	}
	let newest: Week | undefined;
	for (const name of names) {
		try {
			const input = JSON.parse(readFileSync(path.join(cache, name), "utf8"));
			const week = input?.rate_limits?.seven_day;
			if (path.resolve(String(input.config_dir)) !== path.resolve(configDir)) continue;
			if (![week?.used_percentage, week?.resets_at, input.written_at].every((n) => typeof n === "number")) continue;
			const read = { used: week.used_percentage, resets: week.resets_at * 1000, at: input.written_at * 1000 };
			if (!newest || read.at > newest.at) newest = read;
		} catch {}
	}
	return newest;
}

/** The newer of two readings. */
export function newer(a: Week | undefined, b: Week | undefined): Week | undefined {
	if (!a || !b) return a ?? b;
	return b.at > a.at ? b : a;
}
