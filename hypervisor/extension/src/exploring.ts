// Explore runs on the live hypervisor: `/explore N [direction]` runs up to N explore steps as turns of its own
// profile, so what they find lands in the memory max talks to. Each step's message says it is one, toward what, and
// where the run stands against what stops it. A run stops before the next step at the first of: N steps taken, its
// token cap spent, the week's quota used to its share, a step that failed, or a message from max, who is back and whose
// turn comes first. The week's quota is read from the rate-limit headers of the hypervisor's replies. While a run is in
// flight, the hypervisor reads and delegates, and starts or messages no session.

import { readFileSync } from "node:fs";
import path from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { append } from "./journal.ts";
import { type Week, weekFromHeaders } from "./quota.ts";

export const USAGE =
	"usage: /explore N [direction] [--tokens T] [--until-week P]\n" +
	"Runs up to N explore steps, toward the direction or your instructions' default goal. --tokens caps the run's price-weighted tokens " +
	"(one uncached Opus input token each, the profile's summaries included); --until-week stops it once P% of the week's quota is used.";

/** The tools a run blocks: no session is started or messaged while max is away. */
const BLOCKED = ["start_session", "tell_session"];

/** The price of one uncached Opus input token, the unit of a token cap. */
const OPUS_INPUT = 4 / 1e6;
/** How often a run looks whether the turn in flight has ended, before it sends its next step. */
const IDLE_POLL_MS = 1000;
/**
 * How long a step's turn has to start. pi tells no extension when it refuses a prompt before its turn starts (expired
 * credentials, a compaction running), so a step whose turn has not started by then has failed.
 */
const START_MS = 120_000;

/** What `/explore` was asked for. */
export interface Request {
	steps: number;
	direction?: string;
	tokens?: number;
	untilWeek?: number;
}

/** Where a run reads what it costs. */
export interface RunConfig {
	/** The hypervisor's store: `explore.jsonl` keeps each step's finding and each run's end. */
	store: string;
	/** OptChat's usage log for the profile, a line per model call with its cost; without it, a run takes no token cap. */
	usage?: string;
}

/** A line of `explore.jsonl`, the journal of explore runs: a step's finding or a run's end. */
export type JournalLine = { at: string } & (StepLine | EndLine);
export interface StepLine {
	/** The run's start, which names it. */
	run: string;
	step: number;
	/** The run's direction, on its first step. */
	direction?: string;
	finding: string;
	tokens: number;
	error?: string;
}
export interface EndLine {
	run: string;
	/** What stopped it, as it reads after "stopped by". */
	ended: string;
	steps: number;
	tokens: number;
	/** The week's use in percent as the run ended, or `unread` when --until-week was asked for and the week never read. */
	week?: number | "unread";
}

/** A run's state between steps. */
interface Run {
	request: Request;
	/** When it started, as an ISO date: its name in the journal. */
	started: string;
	/** Whether its first step is under way: until then, the turn in flight is not the run's, and its tool calls are not blocked. */
	begun: boolean;
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

/**
 * The message that starts step `n` of a run, with `spent` of its tokens spent and the week as last read: what the step
 * is, toward what, and where the run stands against each budget it was asked for.
 */
export function stepMessage(request: Request, n: number, spent: number, week: Week | undefined, now: number): string {
	const stands: string[] = [];
	if (request.tokens !== undefined) stands.push(`${spent} of ${request.tokens} tokens spent`);
	if (request.untilWeek !== undefined) {
		const live = current(week, now);
		const used = live ? `at ${Math.round(live.used)}%` : "not read yet";
		stands.push(`the week ${used}, the run stops at ${request.untilWeek}%`);
	}
	const head = `Explore step ${n} of at most ${request.steps}, toward ${request.direction ?? "the default goal"}.`;
	const tail = stands.join("; ");
	return tail ? `${head} ${tail[0]!.toUpperCase()}${tail.slice(1)}.` : head;
}

/** Why a run stops before its next step, or nothing while it goes on. */
export function stopBefore(run: Run, spent: number, week: Week | undefined, now: number): string | undefined {
	const { request } = run;
	const live = current(week, now);
	if (run.interrupted) return "a message from max";
	if (run.taken >= request.steps) return `${request.steps} ${request.steps === 1 ? "step" : "steps"}`;
	if (request.tokens !== undefined && spent >= request.tokens) return `the cap of ${request.tokens} tokens`;
	if (request.untilWeek !== undefined && live && live.used >= request.untilWeek) return `the week at ${Math.round(live.used)}% used`;
	return undefined;
}

/** The week as last read, unless its reset has passed: its quota has started over, and what was read tells nothing. */
function current(week: Week | undefined, now: number): Week | undefined {
	return week && week.resets > now ? week : undefined;
}

/** Registers `/explore` with pi. */
export function exploring(pi: ExtensionAPI, config: RunConfig): void {
	/** The week as this process's replies last gave it. */
	let replied: Week | undefined;
	const journal = (line: StepLine | EndLine) => append(config.store, "explore.jsonl", { at: new Date().toISOString(), ...line });

	/** The run asked for, from `/explore` until it ends. */
	let run: Run | undefined;
	/** Resolve on pi's next agent_start and agent_settled. */
	const waiting = { start: new Set<() => void>(), settled: new Set<() => void>() };
	const next = (event: keyof typeof waiting) => new Promise<void>((resolve) => waiting[event].add(resolve));
	const fire = (event: keyof typeof waiting) => {
		const resolvers = [...waiting[event]];
		waiting[event].clear();
		for (const resolve of resolvers) resolve();
	};
	/** The message of the step in flight, whose reply is its finding. */
	let sent: string | undefined;
	/** How the step's turn ended: the step's reply, and the error it ended on, if it did. */
	let ended: { finding: string; error?: string } = { finding: "" };

	pi.on("after_provider_response", (event) => {
		replied = weekFromHeaders(event.headers) ?? replied;
	});
	pi.on("input", (event) => {
		// What max types ends the run after the step in flight; what an extension sends, a step's own message among it, does not.
		if (run && event.source !== "extension" && event.text.trim()) run.interrupted = true;
		return { action: "continue" };
	});
	pi.on("tool_call", (event) => {
		if (run?.begun && BLOCKED.includes(event.toolName)) return { block: true, reason: "An explore run is in flight: read and delegate, and start or message no session while max is away." };
		return undefined;
	});
	pi.on("agent_end", (event) => {
		// The step's reply follows its own message. A message that joined the turn after that reply, max's or a ping's, is
		// not the step's: the step ends before it.
		const own = event.messages.findLastIndex((m) => m.role === "user" && sent !== undefined && textOf(m.content) === sent);
		const replied = event.messages.findIndex((m, i) => i > own && m.role === "assistant");
		const joined = event.messages.findIndex((m, i) => i > replied && (m.role === "user" || m.role === "custom"));
		const last = event.messages.slice(0, replied < 0 || joined < 0 ? undefined : joined).findLast((m) => m.role === "assistant");
		if (last?.role !== "assistant") return;
		const text = last.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("\n").trim();
		ended = { finding: text, ...(last.stopReason === "error" || last.stopReason === "aborted" ? { error: last.errorMessage ?? last.stopReason } : {}) };
	});
	pi.on("agent_start", () => fire("start"));
	pi.on("agent_settled", () => fire("settled"));

	/** What the run has cost since `since`, in the cap's tokens; `undefined` when there is no usage log to count from. */
	const spent = (since: string): number | undefined => {
		if (!config.usage) return 0;
		let text: string;
		try {
			text = readFileSync(config.usage, "utf8");
		} catch {
			return undefined;
		}
		let cost = 0;
		for (const line of text.split("\n")) {
			// The last line may be one OptChat is still writing.
			try {
				const record = JSON.parse(line) as { date: string; usage: { cost: { total: number } } };
				if (record.date >= since) cost += record.usage.cost.total;
			} catch {}
		}
		return Math.round(cost / OPUS_INPUT);
	};

	const step = async (ctx: ExtensionContext, message: string) => {
		const started = next("start");
		const settled = next("settled");
		sent = message;
		ended = { finding: "" };
		// pi runs the input handlers before it looks whether a turn is in flight, so a ping's turn can start in between:
		// the step then follows that turn, and its finding is still the reply to its own message.
		pi.sendUserMessage(message, { deliverAs: "followUp" });
		const began = await Promise.race([started.then(() => true), sleep(START_MS, false, { ref: false })]);
		if (!began) return { finding: "", error: `its turn did not start within ${START_MS / 1000} s` };
		await settled;
		return ended;
	};

	const explore = async (request: Request, ctx: ExtensionContext) => {
		const current: Run = { request, started: new Date().toISOString(), begun: false, taken: 0, interrupted: false };
		run = current;
		let stopped = "";
		try {
			ctx.ui.notify(`explore: up to ${request.steps} steps toward ${request.direction ?? "the default goal"}. A message from you ends the run after the step in flight.`, "info");
			for (;;) {
				// A turn in flight, max's or a ping's, ends before the next step starts, so the step's turn is the step's alone.
				// One in flight when the run was asked for is not the run's: the run begins once it ends.
				while (!ctx.isIdle()) await sleep(IDLE_POLL_MS);
				if (!current.begun) {
					current.begun = true;
					current.started = new Date().toISOString();
				}
				const before = spent(current.started) ?? 0;
				stopped = stopBefore(current, before, replied, Date.now()) ?? "";
				if (stopped) break;
				const done = await step(ctx, stepMessage(request, current.taken + 1, before, replied, Date.now()));
				current.taken++;
				const after = spent(current.started);
				const tokens = (after ?? before) - before;
				await journal({ run: current.started, step: current.taken, ...(current.taken === 1 && request.direction ? { direction: request.direction } : {}), finding: done.finding, tokens, ...(done.error ? { error: done.error } : {}) });
				ctx.ui.notify(`explore step ${current.taken} of ${request.steps}, ${tokens} tokens: ${done.error ? `failed: ${done.error}` : done.finding}`, done.error ? "error" : "info");
				if (done.error) {
					stopped = `step ${current.taken} failing`;
					break;
				}
				// A cap read from a log that cannot be read would never stop the run.
				if (request.tokens !== undefined && after === undefined) {
					stopped = `no usage log at ${config.usage} to count the cap from`;
					break;
				}
			}
		} catch (error) {
			stopped = `an error: ${error instanceof Error ? error.message : String(error)}`;
		} finally {
			run = undefined;
		}
		const used = replied;
		const tokens = spent(current.started) ?? 0;
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
}

/** The OptChat profile `hv` runs on, as its environment locates it. */
function profileDir(): string | undefined {
	const home = process.env.OPTCHAT_HOME;
	const profile = process.env.HV_PROFILE;
	return home && profile ? path.join(home, "profiles", profile) : undefined;
}

/** OptChat's usage log for that profile. */
export function usageLog(): string | undefined {
	const profile = profileDir();
	return profile && path.join(profile, "usage.jsonl");
}

/** A message's text, as pi holds it: a string, or its text parts. */
function textOf(content: string | { type: string; text?: string }[]): string {
	return typeof content === "string" ? content : content.flatMap((part) => (part.type === "text" && part.text !== undefined ? [part.text] : [])).join("\n");
}
