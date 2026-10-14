// What several test files ask of a tool's result and of the inbox.

import { setTimeout as sleep } from "node:timers/promises";
import { inbox } from "../src/inbox.ts";

/** A tool result's text. */
export const resultText = (result: { content: { type: string; text?: string }[] }) => result.content.map((c) => c.text ?? "").join("");

/** The pings that wait in `store`'s inbox, as the hypervisor gets them, left there. */
export async function waitingPings(store: string): Promise<string[]> {
	let pings: string[] = [];
	await inbox(store).takePings((offered) => ((pings = offered), false));
	return pings;
}

/** The pings that wait, once `count` do, or after `within` ms. */
export async function pinged(store: string, { count = 1, within = 5000 } = {}): Promise<string[]> {
	for (const end = Date.now() + within; Date.now() < end; await sleep(20)) {
		const pings = await waitingPings(store);
		if (pings.length >= count) return pings;
	}
	return waitingPings(store);
}

/** Resolves once `check` holds, looking every 10 ms; rejects after `within` ms. */
export async function until(check: () => boolean, within = 5000): Promise<void> {
	for (const end = Date.now() + within; !check(); await sleep(10)) if (Date.now() > end) throw new Error(`not within ${within} ms: ${check}`);
}
