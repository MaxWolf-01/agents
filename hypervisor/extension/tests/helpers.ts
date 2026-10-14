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

/** Resolves once `check` holds, looking every 10 ms, or after `within` ms with whether it held. */
export async function until(check: () => boolean | Promise<boolean>, within = 5000): Promise<boolean> {
	for (const end = Date.now() + within; ; await sleep(10)) {
		if (await check()) return true;
		if (Date.now() > end) return false;
	}
}

/** The pings that wait, once `count` do, or after `within` ms. */
export async function pinged(store: string, { count = 1, within = 5000 } = {}): Promise<string[]> {
	await until(async () => (await waitingPings(store)).length >= count, within);
	return waitingPings(store);
}
