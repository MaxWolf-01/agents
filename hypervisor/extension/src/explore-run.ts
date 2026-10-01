// Explore mode's harness: `node src/explore-run.ts --steps N --tokens N [--model provider/id]`.
//
// It runs pi with the hypervisor's extension in explore mode over RPC, one step per prompt, and starts the next step,
// with the goal and the budget left, until the budget in steps or tokens runs out. It prints each step's tokens and
// finding, and at the end the tokens the run used, the forks' among them. pi takes the store, the home it reads, and
// its credentials from the environment, as `hv` sets them.

import { type ChildProcess, spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";
import { fromEnvironment } from "./index.ts";

const PI = path.resolve(import.meta.dirname, "../node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js");
const EXTENSION = path.resolve(import.meta.dirname, "index.ts");
const GOAL = "Gather what makes you the best assistant, coordinator of coding agents, secretary, collaborator and companion to max.";

export interface Budget {
	steps?: number;
	tokens?: number;
}

/** Tokens as the provider reports them; a run's total counts each kind, cache reads included. */
export interface Tokens {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
}

const none = (): Tokens => ({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
const total = (t: Tokens) => t.input + t.output + t.cacheRead + t.cacheWrite;
const plus = (a: Tokens, b: Partial<Tokens>): Tokens => ({
	input: a.input + (b.input ?? 0),
	output: a.output + (b.output ?? 0),
	cacheRead: a.cacheRead + (b.cacheRead ?? 0),
	cacheWrite: a.cacheWrite + (b.cacheWrite ?? 0),
});

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
		const gone = () => reject(new Error("pi exited during the step"));
		const read = (chunk: Buffer) => {
			buffer += chunk.toString();
			for (let at = buffer.indexOf("\n"); at >= 0; at = buffer.indexOf("\n")) {
				const record = JSON.parse(buffer.slice(0, at));
				buffer = buffer.slice(at + 1);
				if (record.type === "response" && !record.success) {
					pi.stdout!.off("data", read);
					pi.off("close", gone);
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
					pi.stdout!.off("data", read);
					pi.off("close", gone);
					resolve(done);
				}
			}
		};
		pi.stdout!.on("data", read);
		pi.once("close", gone);
		pi.stdin!.write(`${JSON.stringify({ type: "prompt", message })}\n`);
	});
}

/** The tokens of the forks logged in `forks.jsonl` after its first `skip` lines. */
function forkTokens(file: string, skip: number): { lines: number; tokens: Tokens } {
	let lines: string[];
	try {
		lines = readFileSync(file, "utf8").split("\n").filter(Boolean);
	} catch {
		lines = [];
	}
	const calls = lines.slice(skip).flatMap((line) => (JSON.parse(line).calls ?? []) as { usage: Tokens }[]);
	return { lines: lines.length, tokens: calls.reduce((sum, call) => plus(sum, call.usage), none()) };
}

function shown(t: Tokens): string {
	return `${total(t)} (input ${t.input}, output ${t.output}, cache read ${t.cacheRead}, cache write ${t.cacheWrite})`;
}

/** Runs explore mode to the end of its budget; resolves with the exit code. */
export async function explore(budget: Budget, model: string, print = console.log): Promise<number> {
	const config = fromEnvironment();
	const forks = path.join(config.store, "forks.jsonl");
	const before = forkTokens(forks, 0).lines;
	const pi = spawn(
		process.execPath,
		[PI, "--mode", "rpc", "--no-session", "--no-extensions", "--no-builtin-tools", "--no-skills", "--no-context-files", "--no-prompt-templates", "-e", EXTENSION, "--explore", "--model", model],
		{ cwd: config.home, stdio: ["pipe", "pipe", "inherit"] },
	);
	const closed = new Promise((resolve) => pi.on("close", resolve));
	let steps = none();
	let taken = 0;
	let code = 0;
	for (;;) {
		const used = total(steps) + total(forkTokens(forks, before).tokens);
		if (!allows(budget, taken + 1, used)) break;
		const done = await step(pi, stepMessage(taken + 1, budget, used));
		steps = plus(steps, done.tokens);
		print(`step ${++taken}: ${total(done.tokens)} tokens. ${done.error ? `It failed: ${done.error}` : `Finding: ${done.finding}`}`);
		if (done.error) {
			code = 1;
			break;
		}
	}
	print("Waiting for the last steps' compressions to be written.");
	pi.stdin!.end();
	await closed;
	const forked = forkTokens(forks, before).tokens;
	print(`Used ${shown(plus(steps, forked))} tokens in ${taken} ${taken === 1 ? "step" : "steps"}: ${shown(steps)} by the steps, ${shown(forked)} by the forks.`);
	return code;
}

if (import.meta.main) {
	const { values } = parseArgs({ options: { steps: { type: "string" }, tokens: { type: "string" }, model: { type: "string", default: "anthropic/claude-opus-5-5" } } });
	const budget: Budget = { steps: values.steps === undefined ? undefined : Number(values.steps), tokens: values.tokens === undefined ? undefined : Number(values.tokens) };
	if ((budget.steps === undefined && budget.tokens === undefined) || [budget.steps, budget.tokens].some((v) => v !== undefined && !(v > 0))) {
		console.error("usage: explore-run.ts [--steps N] [--tokens N] [--model provider/id]: a budget of steps, tokens, or both");
		process.exit(2);
	}
	process.exit(await explore(budget, values.model));
}
