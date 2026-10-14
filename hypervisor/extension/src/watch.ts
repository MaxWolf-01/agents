import type { Inbox } from "./inbox.ts";

/**
 * Takes the inbox's pings once at the start and every `ms` after, handing them to `deliver`, which starts a turn; a
 * take that fails goes to `failed`. Reads nothing but the inbox.
 */
export function watch(inbox: Inbox, ms: number, deliver: (pings: string[]) => boolean | void, failed: (error: unknown) => void) {
	const look = () => inbox.takePings(deliver).catch(failed);
	const timer = setInterval(() => void look(), ms);
	timer.unref();
	return { look, stop: () => clearInterval(timer), started: look() };
}
