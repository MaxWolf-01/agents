// How much of max's weekly quota is used, read from the rate-limit headers Anthropic returns with each reply to a
// subscription's request.

/** The week's quota at one moment: the share used, in percent, and when the week resets, both as the headers give them. */
export interface Week {
	/** Percent of the week's quota used, 0 to 100. */
	used: number;
	/** When the week resets, in ms since the epoch. */
	resets: number;
}

/** The week from a reply's headers, whose names arrive lower-cased; none when the reply carries no weekly limit, as an API key's does not. */
export function weekFromHeaders(headers: Record<string, string>): Week | undefined {
	const used = Number(headers["anthropic-ratelimit-unified-7d-utilization"]);
	const resets = Number(headers["anthropic-ratelimit-unified-7d-reset"]);
	if (!headers["anthropic-ratelimit-unified-7d-utilization"] || !Number.isFinite(used) || !Number.isFinite(resets)) return undefined;
	return { used: used * 100, resets: resets * 1000 };
}
