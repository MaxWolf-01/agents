// Explore mode's harness, `node src/explore-run.ts` with the options `USAGE` names.
//
// It runs pi with the hypervisor's extension in explore mode over RPC, one step per prompt, and starts the next step,
// with the goal and the budget left, until the budget in steps or tokens runs out. It prints each step's tokens and
// finding, and at the end the tokens the run used, the forks' among them. pi takes the store, the home it reads, and
// its credentials from the environment, as `hv` sets them.

import { type ChildProcess, spawn } from "node:child_process";
import path from "node:path";
import { parseArgs } from "node:util";
import { fromEnvironment } from "./index.ts";
import { lines } from "./journal.ts";
import { HYPERVISOR, MODEL, PI } from "./pi.ts";

const GOAL =
	"Learn what no single ticket or repo holds: what is going on in max's life, his goals, what he wants and why, his preferences and rules; and what you find about the environment you work in, how his machines and tools are set up, where your knowledge has gaps, the bugs that recur, and where agents like you go wrong.";
export const USAGE =
	"usage: explore-run.ts [--steps N] [--tokens N] [--model provider/id]\n" +
	"A budget of steps, of tokens, or both, checked before each step: a step once started runs to its finding. The model defaults to " + MODEL + ".";

/** A budget of steps, of tokens, or both. */
export type Budget = { steps: number; tokens?: number } | { steps?: number; tokens: number };

/** Tokens as the provider reports them; a run's total counts each kind, cache reads included. */
export interface Tokens {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
}

/** Runs explore mode to the end of its budget; resolves with the exit code, 1 when a step failed. */
export async function explore(budget: Budget, model: string): Promise<number> {
	const config = fromEnvironment();
	const before = (await forkTokens(config.store, 0)).lines;
	const pi = spawn(
		process.execPath,
		[PI, "--mode", "rpc", "--no-session", ...HYPERVISOR, "--explore", "--model", model],
		{ cwd: config.home, stdio: ["pipe", "pipe", "inherit"] },
	);
	pi.stdout!.setEncoding("utf8");
	const closed = new Promise((resolve) => pi.on("close", resolve));
	let steps = none();
	let taken = 0;
	let code = 0;
	for (;;) {
		// Forks still running for the step before are not in forks.jsonl yet; the closing count has them all.
		const used = total(steps) + total((await forkTokens(config.store, before)).tokens);
		if (!allows(budget, taken + 1, used)) break;
		const done = await step(pi, stepMessage(taken + 1, budget, used));
		steps = plus(steps, done.tokens);
		console.log(`step ${++taken}: ${total(done.tokens)} tokens. ${done.error ? `It failed: ${done.error}` : `Finding: ${done.finding}`}`);
		if (done.error) {
			code = 1;
			break;
		}
	}
	console.log("Waiting for the last steps' compressions to be written.");
	pi.stdin!.end();
	await closed;
	const forked = (await forkTokens(config.store, before)).tokens;
	console.log(`Used ${shown(plus(steps, forked))} tokens in ${taken} ${taken === 1 ? "step" : "steps"}: ${shown(steps)} by the steps, ${shown(forked)} by the forks.`);
	return code;
}

/** The budget the command line asks for, or why it asks for none. */
export function budgetOf(values: { steps?: string; tokens?: string }): Budget | string {
	const number = (value: string | undefined) => (value === undefined ? undefined : Number(value));
	const steps = number(values.steps);
	const tokens = number(values.tokens);
	if ([steps, tokens].some((n) => n !== undefined && !(Number.isInteger(n) && n > 0))) return "a budget is a whole number above 0";
	if (steps !== undefined) return tokens === undefined ? { steps } : { steps, tokens };
	if (tokens !== undefined) return { tokens };
	return "a budget of steps, tokens, or both";
}

/** What the harness says to start step `n`, with what is left of the budget once the run has used `used` tokens. */
export function stepMessage(n: number, budget: Budget, used: number): string {
	const left = [
		...(budget.steps === undefined ? [] : [`${budget.steps - n} more ${budget.steps - n === 1 ? "step" : "steps"} after this one`]),
		...(budget.tokens === undefined ? [] : [`${budget.tokens - used} tokens`]),
	];
	return `Explore step ${n}. Your goal: ${GOAL} Left of your budget: ${left.join(", ")}.`;
}

/** Whether the budget allows step `n`, once the run has used `used` tokens. */
export function allows(budget: Budget, n: number, used: number): boolean {
	return (budget.steps === undefined || n <= budget.steps) && (budget.tokens === undefined || used < budget.tokens);
}

/** One step's outcome: the tokens its requests used, its last text, and the error it ended on, if it did. */
interface Step {
	tokens: Tokens;
	finding: string;
	error?: string;
}

/** Sends one step's message and resolves once pi has settled, with what pi reported of the step. */
function step(pi: ChildProcess, message: string): Promise<Step> {
	return new Promise((resolve, reject) => {
		const done: Step = { tokens: none(), finding: "" };
		let buffer = "";
		const stop = () => {
			pi.stdout!.off("data", read);
			pi.off("close", gone);
		};
		const gone = () => {
			stop();
			reject(new Error("pi exited during the step"));
		};
		const read = (chunk: string) => {
			buffer += chunk;
			for (let at = buffer.indexOf("\n"); at >= 0; at = buffer.indexOf("\n")) {
				const record = JSON.parse(buffer.slice(0, at));
				buffer = buffer.slice(at + 1);
				if (record.type === "response" && !record.success) {
					stop();
					reject(new Error(record.error));
				}
				if (record.type === "message_end" && record.message.role === "assistant") {
					const reply = record.message;
					done.tokens = plus(done.tokens, reply.usage ?? {});
					const text = reply.content.flatMap((part: { type: string; text?: string }) => (part.type === "text" ? [part.text] : [])).join("\n");
					if (text.trim()) done.finding = text.trim();
					done.error = reply.stopReason === "error" || reply.stopReason === "aborted" ? (reply.errorMessage ?? reply.stopReason) : undefined;
				}
				if (record.type === "agent_settled") {
					stop();
					resolve(done);
				}
			}
		};
		pi.stdout!.on("data", read);
		pi.once("close", gone);
		pi.stdin!.write(`${JSON.stringify({ type: "prompt", message })}\n`);
	});
}

/**
 * The tokens of the forks logged in the store's `forks.jsonl` after its first `skip` lines; a store with no fork yet has
 * none. A line still being written is left out until it is whole.
 */
async function forkTokens(store: string, skip: number): Promise<{ lines: number; tokens: Tokens }> {
	const forks = await lines<{ calls: { usage: Tokens }[] }>(store, "forks.jsonl");
	const calls = forks.slice(skip).flatMap((fork) => fork.calls);
	return { lines: forks.length, tokens: calls.reduce((sum, call) => plus(sum, call.usage), none()) };
}

const none = (): Tokens => ({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
const total = (t: Tokens) => t.input + t.output + t.cacheRead + t.cacheWrite;
const plus = (a: Tokens, b: Partial<Tokens>): Tokens => ({
	input: a.input + (b.input ?? 0),
	output: a.output + (b.output ?? 0),
	cacheRead: a.cacheRead + (b.cacheRead ?? 0),
	cacheWrite: a.cacheWrite + (b.cacheWrite ?? 0),
});

function shown(t: Tokens): string {
	return `${total(t)} (input ${t.input}, output ${t.output}, cache read ${t.cacheRead}, cache write ${t.cacheWrite})`;
}

if (import.meta.main) {
	const { values } = parseArgs({ options: { steps: { type: "string" }, tokens: { type: "string" }, model: { type: "string", default: MODEL }, help: { type: "boolean", short: "h" } } });
	if (values.help) {
		console.log(USAGE);
		process.exit(0);
	}
	const budget = budgetOf(values);
	if (typeof budget === "string") {
		console.error(`${budget}\n${USAGE}`);
		process.exit(2);
	}
	process.exit(await explore(budget, values.model));
}
