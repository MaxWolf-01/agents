// How the hypervisor paces itself: work it starts and does not wait for in its turn, a `job wait`, a timer or a
// delegated task, whose result reaches it later as a ping, `[from] text`, which starts a turn of its own.

import { execFile } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ToolDefinition } from "@earendil-works/pi-coding-agent";
import { post } from "./inbox.ts";
import { run } from "./run.ts";

/** Work running in the background, each piece ending in a ping. */
export interface Background {
	/** Runs `work`, and posts what it answers, or how it failed, as a ping from `from`. */
	start(from: string, work: (signal: AbortSignal) => Promise<string>): void;
	/** Stops what still runs, each piece posting that it stopped, and resolves once every ping is posted. */
	stop(): Promise<void>;
}

/** The ping a piece of work posts when the hypervisor's session ends before it does. */
export const STOPPED = "stopped: the hypervisor's session ended before it finished";

/** Background work whose pings go to the inbox of `store`, which the watch delivers at once. */
export function background(store: string): Background {
	let stopping = new AbortController();
	const running = new Set<Promise<void>>();
	return {
		start(from, work) {
			const { signal } = stopping;
			const done = Promise.resolve()
				.then(() => work(signal))
				.catch((error) => (signal.aborted ? STOPPED : `failed: ${error instanceof Error ? error.message : String(error)}`))
				.then((text) => post(store, { at: new Date().toISOString(), from, text: text.trim() || "(nothing)", ping: true }))
				.catch(() => {})
				.finally(() => running.delete(done));
			running.add(done);
		},
		async stop() {
			// What starts after this runs until the next stop.
			const stopped = stopping;
			stopping = new AbortController();
			stopped.abort();
			await Promise.all(running);
		},
	};
}

/** A job's name as `job` takes one, and not one it would read as a flag. */
const JOB_NAME = /^[A-Za-z0-9._][A-Za-z0-9._-]*$/;

/** What the wait tool was asked for. Spans are in minutes. */
export interface WaitParams {
	job?: string;
	minutes?: number;
	stall?: number;
	watch?: string;
	note?: string;
	probe?: boolean;
}

/**
 * The arguments of the `job wait` that `params` asks for, checked so that no value of the model's reaches `job` as
 * anything but the value of its flag. Without a job, none: the wait is a timer.
 */
export function jobWaitArgs({ job, minutes, stall, watch }: WaitParams): string[] | undefined {
	if (minutes === undefined || !(minutes > 0) || !Number.isFinite(minutes)) throw new Error("minutes: how long to wait at most, a number above 0");
	if (job === undefined) {
		if (stall !== undefined || watch !== undefined) throw new Error("stall and watch need a job to read the log of");
		return undefined;
	}
	if (!JOB_NAME.test(job)) throw new Error(`"${job}" is no job name; job probe lists them`);
	const args = ["wait", job, "--deadline", seconds(minutes)];
	if (stall !== undefined) {
		if (!(stall > 0) || !Number.isFinite(stall)) throw new Error("stall: minutes without a write to the log, a number above 0");
		args.push("--stall", seconds(stall));
	}
	if (watch !== undefined) {
		// job hands the pattern to grep as its first argument, where a leading - would read as an option.
		if (!watch || watch.startsWith("-")) throw new Error("watch: a regex for the log, not empty and not starting with -");
		args.push("--watch", watch);
	}
	return args;
}

/** The wait tool: waits in the background on a job, or on the clock, and the result arrives as `[wait <job>] …`. */
export function waitTool(work: Background): ToolDefinition {
	const minutes = (what: string) => Type.Optional(Type.Number({ description: `${what}, in minutes.` }));
	return defineTool({
		name: "wait",
		label: "Wait",
		description:
			"Wake yourself later, without holding up this turn. With a job, a turn starts when the job ends or the deadline passes, whichever comes first, with job's status line and the log's tail; without one, it starts once the minutes are up. Returns at once; end your turn. With probe, lists every job instead: running, done or gone.",
		parameters: Type.Object({
			job: Type.Optional(Type.String({ description: "A job's name, as job probe, look or a report gives it. Without it, a plain timer." })),
			minutes: minutes("The deadline: how long to wait at most"),
			stall: minutes("With a job: stop waiting once its log has had nothing written to it for this long"),
			watch: Type.Optional(Type.String({ description: "With a job: stop waiting once its log matches this extended regex." })),
			note: Type.Optional(Type.String({ description: "What to do when it ends, repeated in the report that wakes you." })),
			probe: Type.Optional(Type.Boolean({ description: "List the jobs instead of waiting." })),
		}),
		execute: async (_id, params) => {
			const text = (said: string) => ({ content: [{ type: "text" as const, text: said }], details: undefined });
			if (params.probe) return text((await run("job", ["probe"])).trimEnd() || "(no jobs)");
			const args = jobWaitArgs(params);
			const noted = (said: string) => (params.note?.trim() ? `${said.trimEnd()}\nYour note: ${params.note.trim()}` : said);
			const from = args ? `wait ${params.job}` : "wait";
			work.start(from, async (signal) => noted(args ? await jobWait(args, signal) : await timer(params.minutes!, signal)));
			return text(`Waiting${args ? ` on ${params.job}` : ""}, ${params.minutes} minutes at most; a report starting [${from}] wakes you. End your turn.`);
		},
	}) as ToolDefinition;
}

async function timer(minutes: number, signal: AbortSignal): Promise<string> {
	await sleep(minutes * 60_000, undefined, { signal, ref: false });
	return `${minutes} minutes are up.`;
}

/** Runs `job` with `args`, without a shell, and answers with what it printed, whatever its exit code. */
function jobWait(args: string[], signal: AbortSignal): Promise<string> {
	return new Promise((resolve, reject) => {
		const child = execFile("job", args, { encoding: "utf8", signal, maxBuffer: 1 << 20 }, (error, stdout, stderr) => {
			if (signal.aborted) reject(error ?? new Error("stopped"));
			else if (error && typeof error.code !== "number") reject(error);
			else resolve(String(stdout).trim() || String(stderr).trim());
		});
		child.stdin?.end();
	});
}

/** Minutes as whole seconds, at least one. */
function seconds(minutes: number): string {
	return String(Math.max(1, Math.round(minutes * 60)));
}
