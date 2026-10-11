// Explore mode on Taelin's recipe: `node src/recipe-run.ts` with the options `USAGE` names.
//
// It runs pi with our pi-optchat fork and the explorer's read tools over RPC, one explore step per turn of an OptChat
// profile, and starts the next step until the budget runs out. The budget counts price-weighted tokens: what the turns and
// the summaries cost, at pi's prices, over the price of one uncached Opus input token. A new profile starts from
// `explore-recipe/`'s config and instructions. Once the steps end, it waits until every message has its line, then prints
// the tokens by role. pi takes its credentials, and OptChat its profiles, from the environment, as `hv` sets them.

import { spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";
import { step } from "./explore-run.ts";
import { MODEL } from "./pi.ts";

export const USAGE =
	"usage: recipe-run.ts [--steps N] [--budget TOKENS] [--profile NAME] [--effort LEVEL]\n" +
	"The budget is in price-weighted tokens, Opus input tokens at pi's prices, checked before each step; the steps default to 30.";

const OPUS_INPUT = 4 / 1e6;
const HERE = path.resolve(import.meta.dirname, "..");
const SEED = path.resolve(HERE, "../explore-recipe");
const OPTCHAT = process.env.OPTCHAT_FORK ?? path.join(homedir(), "repos/github/MaxWolf-01/pi-optchat");
const PI = path.join(OPTCHAT, "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js");
const TOOLS = ["zoom", "date", "read", "ls", "find", "grep", "memex"];
/** How long the summaries of the last step may take once the steps end. */
const SETTLE_MS = 15 * 60_000;

interface Usage { input: number; output: number; cacheRead: number; cacheWrite: number; cost: { total: number } }
interface Spent { date: string; role: string; usage: Usage }

export async function run(options: { steps: number; budget: number; profile: string; effort: string }): Promise<number> {
	const home = process.env.OPTCHAT_HOME ?? path.join(homedir(), ".optchat");
	const profile = path.join(home, "profiles", options.profile);
	if (!existsSync(profile)) {
		mkdirSync(profile, { recursive: true, mode: 0o700 });
		for (const file of ["config.json", "AGENTS.md"]) copyFileSync(path.join(SEED, file), path.join(profile, file));
	}
	const since = new Date().toISOString();
	const spent = () => lines<Spent>(path.join(profile, "usage.jsonl")).filter((s) => s.date >= since);
	const weighted = () => Math.round(spent().reduce((sum, s) => sum + s.usage.cost.total, 0) / OPUS_INPUT);

	const pi = spawn(
		process.execPath,
		[PI, "--mode", "rpc", "--model", MODEL, "--thinking", options.effort, "--no-extensions", "--no-skills", "--no-context-files", "--no-prompt-templates",
			"--no-builtin-tools", "--tools", TOOLS.join(","), "-e", path.join(OPTCHAT, "src/index.ts"), "-e", path.join(HERE, "src/recipe-tools.ts"),
			"--optchat-profile", options.profile],
		{ cwd: homedir(), stdio: ["pipe", "pipe", "inherit"] },
	);
	pi.stdout!.setEncoding("utf8");
	const closed = new Promise((resolve) => pi.on("close", resolve));
	let code = 0;
	for (let n = 1; n <= options.steps; n++) {
		const before = weighted();
		if (before >= options.budget) break;
		const left = Math.round((100 * (options.budget - before)) / options.budget);
		const done = await step(pi, `Explore step ${n} of ${options.steps}. ${left}% of your budget is left.`);
		console.log(`step ${n}: ${weighted() - before} weighted tokens since it started. ${done.error ? `It failed: ${done.error}` : `Finding: ${done.finding}`}`);
		if (done.error) {
			code = 1;
			break;
		}
	}
	console.log("Waiting for the last step's summaries.");
	const memory = memoryOf(profile);
	for (const deadline = Date.now() + SETTLE_MS; unsummarized(memory) > 0 && Date.now() < deadline; ) await new Promise((r) => setTimeout(r, 5000));
	console.log(`${unsummarized(memory)} messages without their line.`);
	pi.stdin!.end();
	await closed;
	for (const role of ["main", "compactor"]) {
		const mine = spent().filter((s) => s.role === role);
		const sum = (key: "input" | "output" | "cacheRead" | "cacheWrite") => mine.reduce((total, s) => total + s.usage[key], 0);
		const cost = mine.reduce((total, s) => total + s.usage.cost.total, 0);
		console.log(`${role}: ${mine.length} calls, input ${sum("input")}, output ${sum("output")}, cache read ${sum("cacheRead")}, cache write ${sum("cacheWrite")}, $${cost.toFixed(2)}`);
	}
	console.log(`Used ${weighted()} of ${options.budget} weighted tokens.`);
	return code;
}

/** The profile's memory directory: an import can point the profile at another one. */
function memoryOf(profile: string): string {
	const pointer = path.join(profile, "active-memory.json");
	return existsSync(pointer) ? path.join(profile, JSON.parse(readFileSync(pointer, "utf8"))) : profile;
}

/** Messages in the log that have no line of their own in the tree yet. */
function unsummarized(memory: string): number {
	const records = (dir: string) => (existsSync(dir) ? readdirSync(dir).filter((n) => n.endsWith(".jsonl")).flatMap((n) => lines<{ l?: number }>(path.join(dir, n))) : []);
	return records(path.join(memory, "main")).length - records(path.join(memory, "tree")).filter((node) => node.l === 0).length;
}

function lines<T>(file: string): T[] {
	if (!existsSync(file)) return [];
	return readFileSync(file, "utf8").split("\n").flatMap((line) => {
		try {
			return line.trim() ? [JSON.parse(line) as T] : [];
		} catch {
			return [];
		}
	});
}

if (import.meta.main) {
	const { values } = parseArgs({
		options: { steps: { type: "string", default: "30" }, budget: { type: "string", default: "2000000" }, profile: { type: "string", default: "explore-recipe" }, effort: { type: "string", default: "medium" }, help: { type: "boolean", short: "h" } },
	});
	if (values.help) {
		console.log(USAGE);
		process.exit(0);
	}
	process.exit(await run({ steps: Number(values.steps), budget: Number(values.budget), profile: values.profile, effort: values.effort }));
}
