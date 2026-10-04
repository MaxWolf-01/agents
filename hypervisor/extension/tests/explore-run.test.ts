// Explore mode end to end on a fixture home: the harness (`src/explore-run.ts`) drives a real pi over RPC against a
// stand-in for the Anthropic endpoint, whose model reads one file each step and then reports its finding. One run is
// held by a budget of steps, one by a budget of tokens.

import assert from "node:assert/strict";
import { execFile, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { budgetOf, USAGE as HELP } from "../src/explore-run.ts";
import { type Request, standInAnthropic, standInModels, textOf, USAGE } from "./stand-in-anthropic.ts";

const RUN = path.resolve(import.meta.dirname, "../src/explore-run.ts");
const PER_CALL = USAGE.input_tokens + USAGE.output_tokens + USAGE.cache_read_input_tokens + USAGE.cache_creation_input_tokens;
const STEPS = 3;
/** A budget of tokens the steps-budget run never reaches, so its messages say what is left of it. */
const AMPLE = 10_000_000;

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-explore-run-")));
const home = path.join(dir, "home");
for (const [file, text] of Object.entries({ "notes/today.md": "today: ship explore mode", ".ssh/id_ed25519": "c4n4ry-key" })) {
	mkdirSync(path.dirname(path.join(home, file)), { recursive: true });
	writeFileSync(path.join(home, file), text);
}
const agent = path.join(dir, "agent");
mkdirSync(agent);

let anthropic: Awaited<ReturnType<typeof standInAnthropic>>;
/** The requests each run's steps sent, by the run's name; the runs go one after another. */
const steps = new Map<string, Request[]>();
let current = "";

/** The step a request belongs to, by the harness's message that started it. */
const stepOf = (request: Request) => Number(/Explore step (\d+)\./.exec(request.messages.map((m) => textOf(m)).join("\n"))?.[1]);

/**
 * The model: a fork's ask gets a line; a step reads `notes/today.md` first, then the key, then reports its finding. The
 * view, the first message, may quote earlier steps, so only the messages after it count.
 */
function answer(request: Request) {
	const last = textOf(request.messages.at(-1)!);
	const block = /Write the compression of entries #(\S+)/.exec(last);
	if (block) return { text: `compressed ${block[1]}` };
	if (last.includes("is too long for one entry")) return { text: "a gist" };
	steps.set(current, [...(steps.get(current) ?? []), request]);
	const results = request.messages.slice(1).filter((m) => Array.isArray(m.content) && m.content.some((b) => b.type === "tool_result")).length;
	if (results === 0) return { tool: "read", input: { path: "notes/today.md" } };
	if (results === 1) return { tool: "read", input: { path: "~/.ssh/id_ed25519" } };
	return { text: `finding-${stepOf(request)}: max ships explore mode today, per ~/notes/today.md` };
}

/** Runs the harness with `args` over a store of its own; resolves with what it printed, its store, and how many calls it made. */
function explore(name: string, ...args: string[]): Promise<{ out: string; code: number; store: string; requests: number }> {
	const store = path.join(dir, name);
	current = name;
	const from = anthropic.requests.length;
	const env = { ...process.env, PI_CODING_AGENT_DIR: agent, PI_OFFLINE: "1", HV_STORE: store, HV_HOME: home };
	return new Promise((resolve) =>
		execFile(process.execPath, [RUN, ...args, "--model", "stand-in/claude-opus-5-5"], { env, timeout: 120_000 }, (error, stdout) =>
			resolve({ out: String(stdout), code: error ? Number(error.code ?? 1) : 0, store, requests: anthropic.requests.length - from }),
		),
	);
}

let bySteps: Awaited<ReturnType<typeof explore>>;
let byTokens: Awaited<ReturnType<typeof explore>>;
before(async () => {
	anthropic = await standInAnthropic(answer);
	standInModels(agent, anthropic.url);
	bySteps = await explore("steps", "--steps", String(STEPS), "--tokens", String(AMPLE));
	// A step makes three calls: under one step's tokens, the budget allows the first step and no second.
	byTokens = await explore("tokens", "--tokens", String(2 * PER_CALL));
});
after(async () => {
	await anthropic?.close();
	rmSync(dir, { recursive: true, force: true });
});

const log = (store: string) => readFileSync(path.join(store, "log", "LOG.txt"), "utf8");

test("a run of a few steps leaves one finding entry per step, and the tool calls as entries", () => {
	assert.equal(bySteps.code, 0, bySteps.out);
	const text = log(bySteps.store);
	for (let n = 1; n <= STEPS; n++) assert.equal(text.split(`finding: finding-${n}:`).length - 1, 1, `step ${n}'s finding\n${text}`);
	assert.equal(text.match(/read \{"path":"notes\/today.md"\} → today: ship explore mode/g)?.length, STEPS, text);
	assert.equal(text.match(/read \{"path":"~\/.ssh\/id_ed25519"\} → error: .*denied/g)?.length, STEPS, text);
	assert.doesNotMatch(text, /c4n4ry|max: |Explore step/, "the key, or the harness's message as max's");
});

test("each step starts with the goal and the budget left, and remembers the steps before through its view", () => {
	const [first, second, third] = [1, 2, 3].map((n) => steps.get("steps")!.filter((r) => stepOf(r) === n)[0]);
	assert.match(textOf(first.messages[1]), /Your goal: Gather what makes you the best assistant.*2 more steps after this one/);
	assert.match(textOf(third.messages[1]), /0 more steps after this one/);
	// What step 1 used, and whatever its forks had logged by then: a whole number of calls, three at least.
	const left = Number(/after this one, (\d+) tokens\./.exec(textOf(second.messages[1]))?.[1]);
	assert.ok((AMPLE - left) % PER_CALL === 0 && AMPLE - left >= 3 * PER_CALL, `${AMPLE - left} tokens used before step 2`);
	assert.match(textOf(second.messages[0]), /^<view>\n[\s\S]*finding: finding-1:/);
	assert.doesNotMatch(textOf(second.messages[0]), /Explore step 1/);
});

test("explore mode reads with the read tools and memex beside the memory tools, under its own prompt", () => {
	// On an OAuth key, pi sends a tool named like one of Claude Code's under Claude Code's casing: read as Read.
	for (const request of [...steps.values()].flat()) {
		assert.deepEqual(request.tools?.map((t) => t.name.toLowerCase()).sort(), ["find", "grep", "ls", "memex", "raw", "read", "recall", "zoom"]);
		assert.ok(request.system?.some((b) => b.text.includes("## Explore mode") && !b.text.includes("## Sessions")), "explore mode's prompt, and nothing of the session tools it lacks");
	}
});

test("the run stops when its budget of steps or of tokens runs out, and prints the tokens it used", () => {
	for (const [run, taken] of [[bySteps, STEPS], [byTokens, 1]] as const) {
		const steps = [...run.out.matchAll(/^step (\d+): (\d+) tokens\. Finding: finding-\d+/gm)];
		assert.deepEqual(steps.map((m) => Number(m[1])), Array.from({ length: taken }, (_, i) => i + 1), run.out);
		for (const m of steps) assert.equal(Number(m[2]), 3 * PER_CALL, "a step's three calls");
		// Every call to the stand-in, the steps' and the forks', reports the same usage.
		const used = new RegExp(`^Used ${run.requests * PER_CALL} \\(.*\\) tokens in ${taken} steps?: ${taken * 3 * PER_CALL} \\(`, "m");
		assert.match(run.out, used);
	}
});

test("the command line asks for a budget of whole steps or tokens above 0", () => {
	assert.deepEqual(budgetOf({ steps: "30" }), { steps: 30 });
	assert.deepEqual(budgetOf({ tokens: "500000" }), { tokens: 500000 });
	assert.deepEqual(budgetOf({ steps: "2", tokens: "9" }), { steps: 2, tokens: 9 });
	for (const values of [{}, { steps: "0" }, { steps: "abc" }, { tokens: "1.5" }, { steps: "3", tokens: "-1" }]) assert.equal(typeof budgetOf(values), "string", JSON.stringify(values));
});

test("explore mode's --help prints its usage", () => {
	const ran = spawnSync(process.execPath, [RUN, "--help"], { encoding: "utf8" });
	assert.equal(ran.status, 0, ran.stderr);
	assert.equal(ran.stdout, `${HELP}\n`);
});
