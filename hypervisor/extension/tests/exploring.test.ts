// Explore runs on the live hypervisor, end to end: `/explore` sent to a real pi over RPC with the live extension,
// against a stand-in for the Anthropic endpoint, runs until the first of its budgets stops it. The stand-in logs
// each call's cost to the profile's usage log, as pi-optchat does.

import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync, appendFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { type JournalLine, parse, stopBefore } from "../src/exploring.ts";
import { found } from "../src/hv-explore.ts";
import { lines } from "../src/journal.ts";
import { weekFromHeaders } from "../src/quota.ts";
import { type Request, standInAnthropic, standInModels, textOf } from "./stand-in-anthropic.ts";

/** The pi this package installs, which the test starts in place of the fork's that `hv` starts. */
const PI = path.resolve(import.meta.dirname, "../node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js");

const HV_EXPLORE = path.resolve(import.meta.dirname, "../src/hv-explore.ts");
const LIVE = path.resolve(import.meta.dirname, "../src/live.ts");
/** What each call costs, as the stand-in logs it: 1000 tokens at the price of an uncached Opus input token. */
const CALL_COST = 0.004;

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-exploring-")));
const agent = path.join(dir, "agent");
const bin = path.join(dir, "bin");
mkdirSync(agent);
mkdirSync(bin);
// No hypervisor TUI runs, whatever this host's tmux holds.
writeFileSync(path.join(bin, "tmux"), "#!/bin/sh\nexit 1\n", { mode: 0o755 });
/** A stand-in for the command that starts the TUI: it writes the arguments after its first, one a line, to the file its first names. */
const recorder = path.join(bin, "record");
writeFileSync(recorder, `#!/bin/sh\nout=$1; shift; printf '%s\\n' "$@" >> "$out"\n`, { mode: 0o755 });

/** One run's directories, and what the stand-in sees of it. */
interface Fixture {
	name: string;
	store: string;
	home: string;
	optchat: string;
	requests: Request[];
	/** How the model answers: a finding each request, or first a tool call. */
	tool?: string;
	headers?: Record<string, string>;
}
const fixtures = new Map<string, Fixture>();
let current: Fixture | undefined;

function fixture(name: string, options: Partial<Fixture> = {}): Fixture {
	const at = path.join(dir, name);
	const f = { name, store: path.join(at, "store"), home: path.join(at, "home"), optchat: path.join(at, "optchat"), requests: [], ...options };
	for (const d of [f.store, f.home, path.join(f.optchat, "profiles", "hv")]) mkdirSync(d, { recursive: true });
	fixtures.set(name, f);
	return f;
}

/** The user messages of a request after the first, the view's place, as the model reads them. */
const said = (request: Request) => request.messages.filter((m) => m.role === "user").map((m) => textOf(m, false));

function answer(request: Request) {
	const f = current!;
	f.requests.push(request);
	appendFileSync(path.join(f.optchat, "profiles", "hv", "usage.jsonl"), `${JSON.stringify({ date: new Date().toISOString(), role: "main", usage: { cost: { total: CALL_COST } } })}\n`);
	const last = request.messages.at(-1)!;
	const result = Array.isArray(last.content) && last.content.find((b) => b.type === "tool_result");
	if (f.name === "failing") return { status: 400, error: "the stand-in refuses" };
	if (f.tool && !result) return { tool: f.tool, input: { dir: "~", name: "x", brief: "y" } };
	return { text: `finding ${f.requests.length}: ${result ? JSON.stringify(result.content) : "max reads papers on ALife"}`, delay: f.name === "interrupted" || (f.name === "busy" && f.requests.length === 1) ? 400 : 0 };
}

const env = (f: Fixture) => ({
	...process.env,
	PATH: `${bin}:${process.env.PATH}`,
	HOME: f.home,
	HV_HOME: f.home,
	HV_STORE: f.store,
	OPTCHAT_HOME: f.optchat,
	HV_PROFILE: "hv",
	PI_CODING_AGENT_DIR: agent,
	PI_OFFLINE: "1",
});
const pi = [process.execPath, PI, "--no-extensions", "--no-builtin-tools", "--no-skills", "--no-context-files", "--no-prompt-templates", "--no-session", "-e", LIVE, "--model", "stand-in/claude-opus-5-5"];

/**
 * `/explore args` sent to pi over RPC, as max types it in the TUI; resolves with the run's notifications once its end is
 * notified. With `interrupt`, max writes while the first step is in flight; with `busy`, max's message `busy` is in
 * flight when the command arrives.
 */
function notified(f: Fixture, args: string[], { interrupt = false, busy }: { interrupt?: boolean; busy?: string } = {}): Promise<string[]> {
	current = f;
	return new Promise((resolve, reject) => {
		const child = spawn(pi[0]!, [...pi.slice(1), "--mode", "rpc"], { env: env(f), stdio: ["pipe", "pipe", "inherit"] });
		const notes: string[] = [];
		let buffer = "";
		const timer = setTimeout(() => (child.kill(), reject(new Error(`no end of the run: ${notes.join("\n")}`))), 60_000);
		child.stdout.setEncoding("utf8");
		child.stdout.on("data", (chunk: string) => {
			buffer += chunk;
			for (let at = buffer.indexOf("\n"); at >= 0; at = buffer.indexOf("\n")) {
				const record = JSON.parse(buffer.slice(0, at));
				buffer = buffer.slice(at + 1);
				if (busy && record.type === "agent_start" && !sentCommand) command();
				if (interrupt && record.type === "agent_start" && f.requests.length === 0) child.stdin.write(`${JSON.stringify({ type: "prompt", message: "max here, what did you find?", streamingBehavior: "steer" })}\n`);
				if (record.type === "extension_ui_request" && record.method === "notify") {
					notes.push(record.message);
					if (record.message.startsWith("explore run ended")) {
						clearTimeout(timer);
						child.stdin.end();
						child.on("close", () => resolve(notes));
					}
				}
			}
		});
		let sentCommand = false;
		const command = () => {
			sentCommand = true;
			child.stdin.write(`${JSON.stringify({ type: "prompt", message: `/explore ${args.join(" ")}` })}\n`);
		};
		if (busy) child.stdin.write(`${JSON.stringify({ type: "prompt", message: busy })}\n`);
		else command();
	});
}

/** `/explore args`, run as `notified` runs it: its notifications, a line each. */
const explore = (f: Fixture, ...args: string[]) => notified(f, args).then((notes) => notes.join("\n"));

/** `hv explore args` as `hv` runs it, with `start` as the command that starts the TUI; resolves with what it printed and its exit code. */
function hvExplore(args: string[], start: string[], tmux = bin): Promise<{ out: string; code: number }> {
	return new Promise((resolve) =>
		execFile(process.execPath, [HV_EXPLORE, ...args, "--", ...start], { env: { ...process.env, PATH: `${tmux}:${process.env.PATH}`, HV_STORE: dir }, timeout: 30_000 }, (error, stdout, stderr) =>
			resolve({ out: `${stdout}${stderr}`, code: error ? Number(error.code ?? 1) : 0 }),
		),
	);
}

let anthropic: Awaited<ReturnType<typeof standInAnthropic>>;
const runs = new Map<string, string>();
let notes: string[] = [];
const now = Date.now();
before(async () => {
	anthropic = await standInAnthropic(answer, () => current?.headers ?? {});
	standInModels(agent, anthropic.url);
	runs.set("steps", await explore(fixture("steps"), "3", "papers", "on", "open-ended", "ALife"));
	runs.set("tokens", await explore(fixture("tokens"), "5", "--tokens", "1500"));
	runs.set("headers", await explore(fixture("headers", { headers: { "anthropic-ratelimit-unified-7d-utilization": "0.96", "anthropic-ratelimit-unified-7d-reset": String(Math.round(now / 1000) + 86400) } }), "5", "--until-week", "95"));
	runs.set("blocked", await explore(fixture("blocked", { tool: "start_session" }), "1"));
	runs.set("unread", await explore(fixture("unread"), "1", "--until-week", "95"));
	notes = await notified(fixture("interrupted"), ["5"], { interrupt: true });
	runs.set("busy", (await notified(fixture("busy"), ["1"], { busy: "max here, what is in flight?" })).join("\n"));
	runs.set("failing", await explore(fixture("failing"), "3"));
});
after(async () => {
	await anthropic?.close();
	rmSync(dir, { recursive: true, force: true });
});

const journal = (name: string) => lines<JournalLine>(fixtures.get(name)!.store, "explore.jsonl");

test("/explore N with a direction runs N steps on the live profile: the direction starts the run, and every later step is a bare continue", async () => {
	const run = runs.get("steps")!;
	const firsts = fixtures.get("steps")!.requests.map((r) => said(r).at(-1));
	assert.deepEqual(firsts, ["Explore: papers on open-ended ALife", "continue", "continue"]);
	for (let n = 1; n <= 3; n++) assert.match(run, new RegExp(`^explore step ${n} of 3, 1000 tokens: finding ${n}: max reads papers`, "m"));
	assert.match(run, /^explore run ended after 3 steps, 3000 tokens: stopped by 3 steps\./m);
	const lines = await journal("steps");
	assert.deepEqual(lines.map((l) => ("step" in l ? l.step : "ended" in l ? l.ended : undefined)), [1, 2, 3, "3 steps"]);
});

test("what a run found reads back from the store, step by step, with how it ended", async () => {
	const text = await found(fixtures.get("steps")!.store);
	assert.match(text, /toward papers on open-ended ALife:\n\nstep 1, 1000 tokens:\nfinding 1: max reads papers[\s\S]*step 3[\s\S]*Ended after 3 steps, 3000 tokens: stopped by 3 steps\./);
	assert.equal(await found(fixtures.get("tokens")!.store).then((t) => t.includes("finding 1") && !t.includes("finding 3")), true);
	assert.equal(await found(path.join(dir, "nowhere")), "No explore run yet.");
});

test("a run stops at its token cap, counted from the profile's usage log, before N steps", () => {
	const run = runs.get("tokens")!;
	assert.match(run, /^explore run ended after 2 steps, 2000 tokens: stopped by the cap of 1500 tokens\./m);
	assert.equal(fixtures.get("tokens")!.requests.length, 2);
});

test("a run stops once the week's quota reaches its share, read from the reply's rate-limit headers", () => {
	const run = runs.get("headers")!;
	assert.match(run, /^explore run ended after 1 step, 1000 tokens: stopped by the week at 96% used\. The week is at 96%\./m);
});

test("a run starts no session: start_session is refused while it is in flight", () => {
	const [, second] = fixtures.get("blocked")!.requests;
	assert.ok(second, runs.get("blocked")!);
	assert.match(JSON.stringify(second.messages.at(-1)), /An explore run is in flight: read and delegate, and start or message no session/);
	assert.match(runs.get("blocked")!, /stopped by 1 step\./);
});

test("a message from max ends the run after the step in flight", async () => {
	assert.match(notes.at(-1)!, /^explore run ended after 1 step, .*: stopped by a message from max\./);
	const requests = fixtures.get("interrupted")!.requests;
	assert.ok(requests.some((r) => said(r).some((text) => text.startsWith("max here, what did you find?"))), "his message reaches the hypervisor");
	assert.ok(!requests.some((r) => said(r).includes("continue")), "no second step");
	const [step] = await journal("interrupted");
	assert.ok(step && "finding" in step);
	assert.match(step.finding, /^finding 1: max reads papers/, "the step's finding, not the reply to max that joined its turn");
});

test("a run started while a turn is in flight waits for it to end, and journals its own step's finding", async () => {
	const requests = fixtures.get("busy")!.requests;
	const lasts = requests.map((r) => said(r).at(-1) ?? "");
	assert.equal(lasts.length, 2, runs.get("busy") ?? "");
	assert.match(lasts[0]!, /^max here, what is in flight\?/);
	assert.equal(lasts[1], "Explore.", "the step is a turn of its own");
	const [step] = await journal("busy");
	assert.ok(step && "finding" in step);
	assert.match(step.finding, /^finding 2: /, "the step's reply, not the reply to max's message");
	assert.equal(step.tokens, 1000, "only the step's own call");
});

test("a step that fails stops the run, and says so", async () => {
	assert.match(runs.get("failing")!, /^explore run ended after 1 step, .*: stopped by step 1 failing./m);
	assert.equal(fixtures.get("failing")!.requests.length, 1);
});

test("hv explore refuses what /explore cannot run, before it starts the TUI", async () => {
	const started = path.join(dir, "refused.calls");
	for (const args of [[], ["0"], ["three", "steps"], ["3", "--tokens", "1.5"], ["3", "--until-week", "120"]]) {
		const run = await hvExplore(args, [recorder, started]);
		assert.equal(run.code, 2, `${args}: ${run.out}`);
	}
	assert.equal(existsSync(started), false);
});

test("/explore's arguments: N, then a direction of any words, with its caps anywhere among them", () => {
	assert.deepEqual(parse("40"), { steps: 40 });
	assert.deepEqual(parse("12 the news --until-week 90 in ML --tokens 300000"), { steps: 12, direction: "the news in ML", untilWeek: 90, tokens: 300000 });
});

test("a week whose reset has passed stops no run, since its quota has started over", () => {
	const run = { request: { steps: 9, untilWeek: 95 }, started: "", taken: 1, interrupted: false };
	assert.equal(stopBefore(run, 0, { used: 99, resets: now - 1, at: now - 3600_000 }, now), undefined);
	assert.equal(stopBefore(run, 0, { used: 95, resets: now + 1, at: now }, now), "the week at 95% used");
});

test("the rate-limit headers read as a share in percent and a reset in ms; an API key's reply carries none", () => {
	assert.deepEqual(weekFromHeaders({ "anthropic-ratelimit-unified-7d-utilization": "0.7370692663445869", "anthropic-ratelimit-unified-7d-reset": "1764615600" }, 5), { used: 73.70692663445869, resets: 1764615600000, at: 5 });
	assert.equal(weekFromHeaders({ "anthropic-ratelimit-input-tokens-remaining": "1000" }, 5), undefined);
});

test("with the hypervisor's TUI open, hv explore types the command into its pane and starts nothing", async () => {
	const open = path.join(dir, "bin-open");
	const calls = path.join(dir, "tmux.calls");
	const started = path.join(dir, "open.calls");
	mkdirSync(open);
	writeFileSync(path.join(open, "tmux"), `#!/bin/sh\nprintf '%s\\n' "$*" >> "${calls}"\n`, { mode: 0o755 });
	const run = await hvExplore(["20", "the", "news"], [recorder, started], open);
	assert.equal(run.code, 0, run.out);
	assert.deepEqual(readFileSync(calls, "utf8").trimEnd().split("\n"), ["has-session -t =hypervisor", "send-keys -t =hypervisor: -l /explore 20 the news", "send-keys -t =hypervisor: Enter"]);
	assert.equal(existsSync(started), false);
});

test("with the hypervisor's TUI closed, hv explore starts it with the command as pi's first message", async () => {
	const started = path.join(dir, "closed.calls");
	const run = await hvExplore(["20", "the", "news", "--until-week", "90"], [recorder, started, "new-session", "pi"]);
	assert.equal(run.code, 0, run.out);
	assert.deepEqual(readFileSync(started, "utf8").trimEnd().split("\n"), ["new-session", "pi", "/explore 20 the news --until-week 90"]);
});

test("a share of the week asked for and never read stopped nothing, and the run's end says so", async () => {
	assert.match(runs.get("unread")!, /stopped by 1 step\. The week's quota was never read, so --until-week stopped nothing\./);
	assert.match(await found(fixtures.get("unread")!.store), /Ended after 1 step, 1000 tokens: stopped by 1 step\. The week's quota was never read\./);
});
