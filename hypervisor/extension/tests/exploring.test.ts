// Explore runs on the live hypervisor, end to end: `hv explore` runs headless, a real pi over RPC with the live
// extension against a stand-in for the Anthropic endpoint, and stops at the first of its budgets. The stand-in logs
// each call's cost to the profile's usage log, as pi-optchat does. The offer before the week resets is checked on the
// extension loaded into a stand-in for pi.

import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, writeFileSync, appendFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { exploring, offerDue, parse, stopBefore } from "../src/exploring.ts";
import { found } from "../src/hv-explore.ts";
import { waiting } from "../src/inbox.ts";
import { lines } from "../src/journal.ts";
import { PI } from "../src/pi.ts";
import { weekFromHeaders, weekFromStatusline } from "../src/quota.ts";
import { load, standIn } from "./properties/stand-in.ts";
import { type Request, standInAnthropic, standInModels, textOf } from "./stand-in-anthropic.ts";

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
	if (f.tool && !result) return { tool: f.tool, input: { dir: "~", name: "x", brief: "y" } };
	return { text: `finding ${f.requests.length}: ${result ? JSON.stringify(result.content) : "max reads papers on ALife"}`, delay: f.name === "interrupted" ? 400 : 0 };
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

/** `hv explore args` headless, as `hv` runs it; resolves with what it printed and its exit code. */
function explore(f: Fixture, ...args: string[]): Promise<{ out: string; code: number }> {
	current = f;
	return new Promise((resolve) =>
		execFile(process.execPath, [HV_EXPLORE, ...args, "--", ...pi], { env: env(f), timeout: 60_000 }, (error, stdout, stderr) =>
			resolve({ out: `${stdout}${stderr}`, code: error ? Number(error.code ?? 1) : 0 }),
		),
	);
}

/** A run driven over RPC as max would in the TUI: `/explore 5`, and a message of his while its first step is in flight. */
function interrupted(f: Fixture): Promise<string[]> {
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
				if (record.type === "agent_start" && f.requests.length === 0) child.stdin.write(`${JSON.stringify({ type: "prompt", message: "max here, what did you find?", streamingBehavior: "steer" })}\n`);
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
		child.stdin.write(`${JSON.stringify({ type: "prompt", message: "/explore 5" })}\n`);
	});
}

let anthropic: Awaited<ReturnType<typeof standInAnthropic>>;
const runs = new Map<string, { out: string; code: number }>();
let notes: string[] = [];
const now = Date.now();
before(async () => {
	anthropic = await standInAnthropic(answer, () => current?.headers ?? {});
	standInModels(agent, anthropic.url);
	runs.set("steps", await explore(fixture("steps"), "3", "papers", "on", "open-ended", "ALife"));
	runs.set("tokens", await explore(fixture("tokens"), "5", "--tokens", "1500"));
	runs.set("headers", await explore(fixture("headers", { headers: { "anthropic-ratelimit-unified-7d-utilization": "0.96", "anthropic-ratelimit-unified-7d-reset": String(Math.round(now / 1000) + 86400) } }), "5", "--until-week", "95"));
	const statusline = fixture("statusline");
	const cache = path.join(statusline.home, ".cache", "claude-statusline");
	mkdirSync(cache, { recursive: true });
	const input = (account: string, used: number, at: number) => ({ session_id: "s", config_dir: path.join(statusline.home, account), written_at: at, rate_limits: { seven_day: { used_percentage: used, resets_at: now / 1000 + 86400 } } });
	writeFileSync(path.join(cache, "a.json"), JSON.stringify(input(".claude", 97, now / 1000 - 60)));
	// Another account's input, newer and nearly unused, does not count.
	writeFileSync(path.join(cache, "b.json"), JSON.stringify(input(".claude-pro", 10, now / 1000)));
	runs.set("statusline", await explore(statusline, "5", "--until-week", "95"));
	runs.set("blocked", await explore(fixture("blocked", { tool: "start_session" }), "1"));
	runs.set("unread", await explore(fixture("unread"), "1", "--until-week", "95"));
	notes = await interrupted(fixture("interrupted"));
});
after(async () => {
	await anthropic?.close();
	rmSync(dir, { recursive: true, force: true });
});

const journal = (name: string) => lines<{ run?: string; step?: number; finding?: string; ended?: string; steps?: number }>(fixtures.get(name)!.store, "explore.jsonl");

test("hv explore N with a direction runs N steps on the live profile: the direction starts the run, and every later step is a bare continue", async () => {
	const run = runs.get("steps")!;
	assert.equal(run.code, 0, run.out);
	const firsts = fixtures.get("steps")!.requests.map((r) => said(r).at(-1));
	assert.deepEqual(firsts, ["Explore: papers on open-ended ALife", "continue", "continue"]);
	for (let n = 1; n <= 3; n++) assert.match(run.out, new RegExp(`^explore step ${n} of 3, 1000 tokens: finding ${n}: max reads papers`, "m"));
	assert.match(run.out, /^explore run ended after 3 steps, 3000 tokens: stopped by 3 steps\./m);
	const lines = await journal("steps");
	assert.deepEqual(lines.map((l) => l.step ?? l.ended), [1, 2, 3, "3 steps"]);
});

test("what a run found reads back from the store, step by step, with how it ended", async () => {
	const text = await found(fixtures.get("steps")!.store);
	assert.match(text, /toward papers on open-ended ALife:\n\nstep 1, 1000 tokens:\nfinding 1: max reads papers[\s\S]*step 3[\s\S]*Ended after 3 steps, 3000 tokens: stopped by 3 steps\./);
	assert.equal(await found(fixtures.get("tokens")!.store).then((t) => t.includes("finding 1") && !t.includes("finding 3")), true);
	assert.equal(await found(path.join(dir, "nowhere")), "No explore run yet.");
});

test("a run stops at its token cap, counted from the profile's usage log, before N steps", () => {
	const run = runs.get("tokens")!;
	assert.equal(run.code, 0, run.out);
	assert.match(run.out, /^explore run ended after 2 steps, 2000 tokens: stopped by the cap of 1500 tokens\./m);
	assert.equal(fixtures.get("tokens")!.requests.length, 2);
});

test("a run stops once the week's quota reaches its share, read from the reply's rate-limit headers", () => {
	const run = runs.get("headers")!;
	assert.match(run.out, /^explore run ended after 1 step, 1000 tokens: stopped by the week at 96% used\. The week is at 96%\./m);
});

test("without a reply's headers, the week is read from the statusline's cache of max's own account", () => {
	const run = runs.get("statusline")!;
	assert.match(run.out, /^explore run ended after 0 steps, 0 tokens: stopped by the week at 97% used\./m);
	assert.equal(fixtures.get("statusline")!.requests.length, 0);
});

test("a run starts no session: start_session is refused while it is in flight", () => {
	const [, second] = fixtures.get("blocked")!.requests;
	assert.ok(second, runs.get("blocked")!.out);
	assert.match(JSON.stringify(second.messages.at(-1)), /An explore run is in flight: read and delegate, and start or message no session/);
	assert.match(runs.get("blocked")!.out, /stopped by 1 step\./);
});

test("a message from max ends the run after the step in flight", async () => {
	assert.match(notes.at(-1)!, /^explore run ended after 1 step, .*: stopped by max wrote\./);
	const requests = fixtures.get("interrupted")!.requests;
	assert.ok(requests.some((r) => said(r).some((text) => text.startsWith("max here, what did you find?"))), "his message reaches the hypervisor");
	assert.ok(!requests.some((r) => said(r).includes("continue")), "no second step");
	const [step] = await journal("interrupted");
	assert.match(step!.finding!, /^finding 1: max reads papers/, "the step's finding, not the reply to max that joined its turn");
});

test("hv explore refuses what /explore cannot run, before any pi starts", async () => {
	const f = fixture("refused");
	for (const args of [[], ["0"], ["three", "steps"], ["3", "--tokens", "1.5"], ["3", "--until-week", "120"]]) {
		const run = await explore(f, ...args);
		assert.equal(run.code, 2, `${args}: ${run.out}`);
	}
	assert.equal(f.requests.length, 0);
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
	assert.equal(weekFromStatusline(path.join(dir, "nowhere"), "/x"), undefined);
});

test("an offer is due about 12 hours before the reset, with more than a fifth of the week unused", () => {
	const hour = 3600_000;
	assert.equal(offerDue({ used: 50, resets: now + 11 * hour, at: now }, now), true);
	assert.equal(offerDue({ used: 50, resets: now + 13 * hour, at: now }, now), false, "too early");
	assert.equal(offerDue({ used: 85, resets: now + 11 * hour, at: now }, now), false, "the week nearly used");
	assert.equal(offerDue({ used: 50, resets: now - hour, at: now }, now), false, "the week already reset");
});

test("in the TUI, the hypervisor is asked once per week to offer max a run, with a desktop notification; nothing starts a run", async () => {
	const f = fixture("offer");
	const cache = path.join(f.home, "cache");
	mkdirSync(cache);
	const resets = now + 6 * 3600_000;
	writeFileSync(path.join(cache, "s.json"), JSON.stringify({ config_dir: path.join(f.home, ".claude"), written_at: now / 1000, rate_limits: { seven_day: { used_percentage: 40, resets_at: resets / 1000 } } }));
	const ran: string[][] = [];
	const config = { store: f.store, statusline: cache, account: path.join(f.home, ".claude"), now: () => now };
	for (let session = 0; session < 2; session++) {
		const sent: string[] = [];
		const extension = await load((pi) => exploring(new Proxy(pi, { get: (t, k) => (k === "exec" ? async (c: string, a: string[]) => (ran.push([c, ...a]), { code: 0 }) : k === "sendUserMessage" ? (m: string) => sent.push(m) : t[k as keyof typeof t]) }), config), f.home);
		for (const handler of extension.handlers.get("session_start") ?? []) await handler(standIn({ type: "session_start" }), standIn({ mode: "tui" }));
		await new Promise((r) => setTimeout(r, 200));
		for (const handler of extension.handlers.get("session_shutdown") ?? []) await handler(standIn({}), standIn({}));
		assert.deepEqual(sent, [], "no step is sent without max's command");
	}
	const pings = waiting(f.store);
	assert.equal(pings.length, 1, "one offer for the week, across sessions");
	assert.equal(pings[0]!.from, "explore offer");
	assert.ok(pings[0]!.ping);
	assert.match(pings[0]!.text, /60% of it unused\. Ask him whether you should explore for up to 50 steps until 95% of the week is used.*`\/explore 50 --until-week 95 <direction>`.*No answer means no run\./);
	assert.equal(ran.length, 1);
	assert.equal(ran[0]![0], "notify-send");
	assert.deepEqual(readdirSync(f.store).sort(), ["explore.jsonl", "inbox"]);
});

test("with the hypervisor's TUI open, hv explore types the command into its pane and starts no pi of its own", async () => {
	const f = fixture("tui");
	const open = path.join(dir, "bin-open");
	const calls = path.join(dir, "tmux.calls");
	mkdirSync(open);
	writeFileSync(path.join(open, "tmux"), `#!/bin/sh\nprintf '%s\\n' "$*" >> "${calls}"\n`, { mode: 0o755 });
	current = f;
	const ran = await new Promise<{ code: number; out: string }>((resolve) =>
		execFile(process.execPath, [HV_EXPLORE, "20", "the", "news", "--", ...pi], { env: { ...env(f), PATH: `${open}:${process.env.PATH}` }, timeout: 30_000 }, (error, stdout) =>
			resolve({ code: error ? Number(error.code ?? 1) : 0, out: String(stdout) }),
		),
	);
	assert.equal(ran.code, 0, ran.out);
	assert.deepEqual(readFileSync(calls, "utf8").trimEnd().split("\n"), ["has-session -t =hypervisor", "send-keys -t =hypervisor -l /explore 20 the news", "send-keys -t =hypervisor Enter"]);
	assert.equal(f.requests.length, 0);
});

test("a share of the week asked for and never read stopped nothing, and the run's end says so", async () => {
	assert.match(runs.get("unread")!.out, /stopped by 1 step\. The week's quota was never read, so --until-week stopped nothing\./);
	assert.match(await found(fixtures.get("unread")!.store), /Ended after 1 step, 1000 tokens: stopped by 1 step\. The week's quota was never read\./);
});
