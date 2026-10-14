// `hv offer`: about 12 hours before max's week resets, with more than a fifth of it unused, the hypervisor is asked
// to offer him an explore run, by a ping and a desktop notification; only the command he types starts one. A systemd
// user timer runs it every hour (dotfiles' `nix/home/timers.nix`), so the offer is made once per week whether or not
// the TUI runs, and waits in the inbox while it does not. The week is read from what Claude Code last handed its
// statusline, which keeps it under `~/.cache/claude-statusline/<session id>.json`.

import { execFile } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { append, lines } from "./journal.ts";
import type { Week } from "./quota.ts";

/** The offer: this long before the week resets, with more than this share of it unused, for up to this many steps. */
export const OFFER_AHEAD_MS = 12 * 3600_000;
export const OFFER_UNUSED = 20;
export const OFFER_STEPS = 50;
export const OFFER_UNTIL = 95;

export const USAGE = `usage: hv offer

Asks the hypervisor, with hv tell --ping and a desktop notification, to offer max an explore run, when his week resets
within ${OFFER_AHEAD_MS / 3600_000} hours with more than ${OFFER_UNUSED}% of it unused, and no offer was made for this week yet. Otherwise it says why
not and does nothing. A systemd user timer runs it hourly. The week is read from the statusline's cache of the account
~/.claude; the offer is recorded in $HV_STORE/explore.jsonl, which hv sets.`;

/** Whether the week, read at `now`, is due an offer: it resets within OFFER_AHEAD_MS, with more than OFFER_UNUSED% unused. */
export function offerDue(week: Week | undefined, now: number): boolean {
	return week !== undefined && week.resets > now && week.resets - now <= OFFER_AHEAD_MS && 100 - week.used > OFFER_UNUSED;
}

/** The offer's text, as the hypervisor reads it in the ping that starts its turn. */
export function offerText(week: Week): string {
	const command = `/explore ${OFFER_STEPS} --until-week ${OFFER_UNTIL} <direction>`;
	return (
		`Explore offer: max's week resets at ${new Date(week.resets).toISOString().slice(0, 16)}Z with ${Math.round(100 - week.used)}% of it unused. ` +
		`Ask him whether you should explore for up to ${OFFER_STEPS} steps until ${OFFER_UNTIL}% of the week is used, and suggest a direction. ` +
		`A run starts only when he types the command, \`${command}\`, so give it to him with your direction filled in. No answer means no run, and once that reset has passed, the offer has lapsed.`
	);
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

/**
 * Makes this week's offer, if it is due and not made yet: `tell` (a command and its first arguments) takes the text as
 * its last argument, then the offer is recorded and max notified. Resolves with what it did, or why it did nothing.
 * An offer `tell` failed to deliver is not recorded, so the next run tries again.
 */
export async function offer(store: string, tell: string[]): Promise<string> {
	const now = Date.now();
	const week = weekFromStatusline(path.join(homedir(), ".cache", "claude-statusline"), path.join(homedir(), ".claude"));
	if (!week) return "No offer: the statusline's cache holds no week of ~/.claude.";
	const state = `the week resets at ${new Date(week.resets).toISOString().slice(0, 16)}Z, ${Math.round(week.used)}% used`;
	if (!offerDue(week, now)) return `No offer: ${state}.`;
	// The one week whose reset is still ahead is this one, whatever its reset time reads to the second.
	const offers = await lines<{ offer?: number }>(store, "explore.jsonl");
	if (offers.some((line) => line.offer !== undefined && line.offer > now)) return `No offer: this week's was made already; ${state}.`;
	await run(tell[0]!, [...tell.slice(1), offerText(week)]);
	await append(store, "explore.jsonl", { at: new Date(now).toISOString(), offer: week.resets, used: Math.round(week.used) });
	const notified = await run("notify-send", ["--app-name=hypervisor", "Explore before the week resets?", `${Math.round(100 - week.used)}% of the week unused. The hypervisor asks in its chat.`]).then(
		() => "",
		(error) => ` The desktop notification failed: ${error instanceof Error ? error.message : String(error)}`,
	);
	return `Offered: ${state}.${notified}`;
}

const run = promisify(execFile);

if (import.meta.main) {
	const argv = process.argv.slice(2);
	const split = argv.indexOf("--");
	const args = split < 0 ? argv : argv.slice(0, split);
	const tell = split < 0 ? [] : argv.slice(split + 1);
	if (args[0] === "--help" || args[0] === "-h") {
		console.log(USAGE);
		process.exit(0);
	}
	const store = process.env.HV_STORE;
	if (!store || !tell.length || args.length) {
		console.error(`hv offer: run it as hv offer, which sets HV_STORE and says how to reach hv tell\n\n${USAGE}`);
		process.exit(2);
	}
	try {
		console.log(await offer(store, tell));
	} catch (error) {
		console.error(`hv offer: ${error instanceof Error ? error.message : String(error)}`);
		process.exit(1);
	}
}
