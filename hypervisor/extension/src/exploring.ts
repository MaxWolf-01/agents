// Explore runs on the live hypervisor: `/explore N [direction]` runs up to N explore steps as turns of its own
// profile, so what they find lands in the memory max talks to. The first step's message is the direction, every later
// one a bare "continue". A run stops before the next step at the first of: N steps taken, its token cap spent, the
// week's quota used to its share, a step that failed, or a message from max, who is back and whose turn comes first.
// While a run is in flight, the hypervisor reads and delegates, and starts or messages no session.
//
// About 12 hours before the week resets, with more than a fifth of it unused, the hypervisor is asked to offer max a
// run, in its chat and with a desktop notification; only the command he types starts one.

import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { inbox } from "./inbox.ts";
import { append, lines } from "./journal.ts";
import { newer, type Week, weekFromHeaders, weekFromStatusline } from "./quota.ts";

export const USAGE =
	"usage: /explore N [direction] [--tokens T] [--until-week P]\n" +
	"Runs up to N explore steps, toward the direction or your instructions' default goal. --tokens caps the run's price-weighted tokens " +
	"(one uncached Opus input token each, the profile's summaries included); --until-week stops it once P% of the week's quota is used.";

/** The tools a run blocks: no session is started or messaged while max is away. */
export const BLOCKED = ["start_session", "tell_session"];

/** The offer: this long before the week resets, with more than this share of it unused, for up to this many steps. */
export const OFFER_AHEAD_MS = 12 * 3600_000;
export const OFFER_UNUSED = 20;
export const OFFER_STEPS = 50;
export const OFFER_UNTIL = 95;
/** How often the offer is looked at. */
const OFFER_EVERY_MS = 10 * 60_000;

/** The price of one uncached Opus input token, the unit of a token cap. */
const OPUS_INPUT = 4 / 1e6;

/** What `/explore` was asked for. */
export interface Request {
	steps: number;
	direction?: string;
	tokens?: number;
	untilWeek?: number;
}

/** Where a run reads what it costs and how much of the week is used. */
export interface ExploreConfig {
	/** The hypervisor's store: `explore.jsonl` keeps each step's finding, each run's end, and each offer made. */
	store: string;
	/** OptChat's usage log for the profile, a line per model call with its cost; without it, a run takes no token cap. */
	usage?: string;
	/** Where the statusline keeps Claude Code's inputs. */
	statusline?: string;
	/** The Claude Code account whose statusline inputs count, by its config directory. */
	account?: string;
	/** The clock, in ms since the epoch. */
	now?: () => number;
}

/** A run's state between steps. */
interface Run {
	request: Request;
	/** When it started, as an ISO date: its name in the journal. */
	started: string;
	taken: number;
	interrupted: boolean;
}

/** The request `/explore`'s arguments make, or why they make none. */
export function parse(args: string): Request | string {
	const words = args.trim().split(/\s+/).filter(Boolean);
	const steps = Number(words.shift());
	if (!Number.isInteger(steps) || steps < 1) return "N, the steps at most, is a whole number above 0";
	const request: Request = { steps };
	const direction: string[] = [];
	while (words.length) {
		const word = words.shift()!;
		if (word === "--tokens" || word === "--until-week") {
			const n = Number(words.shift());
			if (word === "--tokens") {
				if (!Number.isInteger(n) || n < 1) return "--tokens takes a whole number above 0";
				request.tokens = n;
			} else {
				if (!(n > 0 && n <= 100)) return "--until-week takes a percentage above 0, at most 100";
				request.untilWeek = n;
			}
		} else direction.push(word);
	}
	if (direction.length) request.direction = direction.join(" ");
	return request;
}

/** The message that starts step `n` of a run toward `direction`. */
export function stepMessage(n: number, direction: string | undefined): string {
	if (n > 1) return "continue";
	return direction ? `Explore: ${direction}` : "Explore.";
}

/** Why a run stops before its next step, or nothing while it goes on. A week whose reset has passed tells nothing. */
export function stopBefore(run: Run, spent: number, week: Week | undefined, now: number): string | undefined {
	const { request } = run;
	if (run.interrupted) return "max wrote";
	if (run.taken >= request.steps) return `${request.steps} ${request.steps === 1 ? "step" : "steps"}`;
	if (request.tokens !== undefined && spent >= request.tokens) return `the cap of ${request.tokens} tokens`;
	if (request.untilWeek !== undefined && week && week.resets > now && week.used >= request.untilWeek) return `the week at ${Math.round(week.used)}% used`;
	return undefined;
}

/** Whether the week, read at `now`, is due an offer: it resets within OFFER_AHEAD_MS, with more than OFFER_UNUSED% unused. */
export function offerDue(week: Week | undefined, now: number): boolean {
	return week !== undefined && week.resets > now && week.resets - now <= OFFER_AHEAD_MS && 100 - week.used > OFFER_UNUSED;
}

/** The offer's text, as the hypervisor reads it in the ping that starts its turn. */
export function offerText(week: Week): string {
	const command = `/explore ${OFFER_STEPS} --until-week ${OFFER_UNTIL} <direction>`;
	return (
		`max's week resets at ${new Date(week.resets).toISOString().slice(0, 16)}Z with ${Math.round(100 - week.used)}% of it unused. ` +
		`Ask him whether you should explore for up to ${OFFER_STEPS} steps until ${OFFER_UNTIL}% of the week is used, and suggest a direction. ` +
		`A run starts only when he types the command, \`${command}\`, so give it to him with your direction filled in. No answer means no run.`
	);
}

/** Registers `/explore` and the offer with pi. */
export function exploring(pi: ExtensionAPI, config: ExploreConfig): void {
	const now = config.now ?? Date.now;
	const statusline = config.statusline ?? path.join(homedir(), ".cache", "claude-statusline");
	const account = config.account ?? path.join(homedir(), ".claude");
	/** The week as this process's replies last gave it. */
	let replied: Week | undefined;
	const week = () => newer(replied, weekFromStatusline(statusline, account));
	const journal = (line: object) => append(config.store, "explore.jsonl", { at: new Date(now()).toISOString(), ...line });

	let run: Run | undefined;
	/** Resolves the step in flight once pi settles. */
	let settle: (() => void) | undefined;
	/** How the latest turn ended: its last text, and the error it ended on, if it did. */
	let ended: { finding: string; error?: string } = { finding: "" };

	pi.on("after_provider_response", (event) => {
		replied = weekFromHeaders(event.headers, now()) ?? replied;
	});
	pi.on("input", (event) => {
		// What max types ends the run after the step in flight; what an extension sends, a step's own message among it, does not.
		if (run && event.source !== "extension" && event.text.trim()) run.interrupted = true;
		return { action: "continue" };
	});
	pi.on("tool_call", (event) => {
		if (run && BLOCKED.includes(event.toolName)) return { block: true, reason: "An explore run is in flight: read and delegate, and start or message no session while max is away." };
		return undefined;
	});
	pi.on("agent_end", (event) => {
		// A message that joined the step's turn after its first reply, max's or a ping's, is not the step's: the step ends before it.
		const replied = event.messages.findIndex((m) => m.role === "assistant");
		const joined = event.messages.findIndex((m, i) => i > replied && (m.role === "user" || m.role === "custom"));
		const last = event.messages.slice(0, replied < 0 || joined < 0 ? undefined : joined).findLast((m) => m.role === "assistant");
		if (last?.role !== "assistant") return;
		const text = last.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("\n").trim();
		ended = { finding: text, ...(last.stopReason === "error" || last.stopReason === "aborted" ? { error: last.errorMessage ?? last.stopReason } : {}) };
	});
	pi.on("agent_settled", () => {
		const done = settle;
		settle = undefined;
		done?.();
	});

	const spent = (since: string): number => {
		if (!config.usage) return 0;
		let text = "";
		try {
			text = readFileSync(config.usage, "utf8");
		} catch {}
		let cost = 0;
		for (const line of text.split("\n")) {
			try {
				const record = JSON.parse(line) as { date: string; usage: { cost: { total: number } } };
				if (record.date >= since) cost += record.usage.cost.total;
			} catch {}
		}
		return Math.round(cost / OPUS_INPUT);
	};

	const step = (ctx: ExtensionContext, message: string) => {
		const settled = new Promise<void>((resolve) => (settle = resolve));
		ended = { finding: "" };
		pi.sendUserMessage(message, ctx.isIdle() ? undefined : { deliverAs: "followUp" });
		return settled.then(() => ended);
	};

	const explore = async (request: Request, ctx: ExtensionContext) => {
		const current: Run = { request, started: new Date(now()).toISOString(), taken: 0, interrupted: false };
		run = current;
		let stopped: string | undefined;
		try {
			ctx.ui.notify(`explore: up to ${request.steps} steps toward ${request.direction ?? "the default goal"}. A message from you ends the run after the step in flight.`, "info");
			for (;;) {
				const before = spent(current.started);
				stopped = stopBefore(current, before, week(), now());
				if (stopped) break;
				const done = await step(ctx, stepMessage(current.taken + 1, request.direction));
				current.taken++;
				const tokens = spent(current.started) - before;
				await journal({ run: current.started, step: current.taken, ...(current.taken === 1 && request.direction ? { direction: request.direction } : {}), finding: done.finding, tokens, ...(done.error ? { error: done.error } : {}) });
				ctx.ui.notify(`explore step ${current.taken} of ${request.steps}, ${tokens} tokens: ${done.error ? `failed: ${done.error}` : done.finding}`, done.error ? "error" : "info");
				if (done.error) {
					stopped = `step ${current.taken} failing`;
					break;
				}
				// A cap read from a log that is not there would never stop the run.
				if (request.tokens !== undefined && config.usage && !existsSync(config.usage)) {
					stopped = `no usage log at ${config.usage} to count the cap from`;
					break;
				}
			}
		} catch (error) {
			stopped = `an error: ${error instanceof Error ? error.message : String(error)}`;
		} finally {
			run = undefined;
		}
		const used = week();
		const tokens = spent(current.started);
		// A share asked for and never read stopped nothing, which the end says rather than leave it to pass for a share not reached.
		const share = used ? ` The week is at ${Math.round(used.used)}%.` : request.untilWeek !== undefined ? " The week's quota was never read, so --until-week stopped nothing." : "";
		await journal({ run: current.started, ended: stopped, steps: current.taken, tokens, ...(used ? { week: Math.round(used.used) } : request.untilWeek !== undefined ? { week: "unread" } : {}) }).catch(() => {});
		ctx.ui.notify(`explore run ended after ${current.taken} ${current.taken === 1 ? "step" : "steps"}, ${tokens} tokens: stopped by ${stopped}.${share}`, "info");
	};

	pi.registerCommand("explore", {
		description: "Explore for up to N steps, toward a direction or the default goal: /explore N [direction] [--tokens T] [--until-week P]",
		handler: async (args, ctx) => {
			const request = parse(args);
			if (typeof request === "string") return ctx.ui.notify(`explore run refused: ${request}\n${USAGE}`, "error");
			if (run) return ctx.ui.notify(`explore: a run is in flight already; a message from you ends it after its step.`, "warning");
			if (request.tokens !== undefined && !config.usage) return ctx.ui.notify(`explore run refused: --tokens needs the profile's usage log, which OPTCHAT_HOME and HV_PROFILE locate.`, "error");
			// Not awaited, so the editor stays max's while the run goes on.
			void explore(request, ctx);
		},
	});

	let offering: ReturnType<typeof setInterval> | undefined;
	pi.on("session_start", (_event, ctx) => {
		// Only the TUI has max to ask.
		if (ctx.mode !== "tui" || offering) return;
		const look = async () => {
			const read = week();
			if (run || !read || !offerDue(read, now())) return;
			const offers = await lines<{ offer?: number }>(config.store, "explore.jsonl");
			if (offers.some((line) => line.offer === read.resets)) return;
			await journal({ offer: read.resets, used: Math.round(read.used) });
			await inbox(config.store).post({ at: new Date(now()).toISOString(), from: "explore offer", text: offerText(read), ping: true });
			await pi.exec("notify-send", ["--app-name=hypervisor", "Explore before the week resets?", `${Math.round(100 - read.used)}% of the week unused. The hypervisor asks in its chat.`]).catch(() => {});
		};
		offering = setInterval(() => void look().catch(() => {}), OFFER_EVERY_MS);
		offering.unref();
		void look().catch(() => {});
	});
	pi.on("session_shutdown", () => {
		if (offering) clearInterval(offering);
		offering = undefined;
	});
}

/** The OptChat profile `hv` runs on, as its environment locates it. */
export function profileDir(): string | undefined {
	const home = process.env.OPTCHAT_HOME;
	const profile = process.env.HV_PROFILE;
	return home && profile ? path.join(home, "profiles", profile) : undefined;
}

/** OptChat's usage log for that profile. */
export function usageLog(): string | undefined {
	const profile = profileDir();
	return profile && path.join(profile, "usage.jsonl");
}
