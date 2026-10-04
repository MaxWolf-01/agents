// The extension in a real pi, run over RPC against a stand-in for the Anthropic endpoint: what a spawned session's
// turn ending and an orchestrator's `hv tell` do while max says nothing. The spawned session is this test's own
// process, entered in a stand-in registry and recorded as the claude a spawned window runs.

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { appendFileSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { post } from "../src/inbox.ts";
import { HYPERVISOR, PI } from "../src/pi.ts";
import { conversing, type Request, standInAnthropic, standInModels, textOf } from "./stand-in-anthropic.ts";

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-events-")));
const store = path.join(dir, "store");
const claude = path.join(dir, ".claude");
const entry = path.join(claude, "sessions", `${process.pid}.json`);
let anthropic: Awaited<ReturnType<typeof standInAnthropic>>;
/** The requests of each run, by what started it. */
const runs = new Map<string, Request[]>();
let run = "";

/** Enters this process in the registry as the session in pane %42, in `status`. */
function registered(status: string) {
	writeFileSync(entry, JSON.stringify({ pid: process.pid, name: "orch-42", cwd: dir, status, tmux: "agents:@7.%42" }));
}

before(async () => {
	anthropic = await standInAnthropic((request) => {
		const last = textOf(request.messages.at(-1)!);
		// The long message's gist keeps the next run in its start for seconds, the watch's looks included.
		if (/is too long for one entry/.test(last) && last.includes("long-marker")) return { text: "gist of the long message", delay: 8000 };
		if (/Write the compression|is too long for one entry/.test(last)) return { text: "compressed" };
		runs.set(run, [...(runs.get(run) ?? []), request]);
		return { text: `noted ${run}` };
	});
	const agent = path.join(dir, "agent");
	mkdirSync(agent);
	mkdirSync(path.dirname(entry), { recursive: true });
	mkdirSync(store, { recursive: true });
	standInModels(agent, anthropic.url);
	appendFileSync(path.join(store, "spawned.jsonl"), `${JSON.stringify({ at: new Date().toISOString(), pane: "%42", pid: process.pid, window: "agents:board-fix", dir })}\n`);
	registered("busy");
	const pi = spawn(
		process.execPath,
		[PI, "--mode", "rpc", "--no-session", "--offline", ...HYPERVISOR, "--provider", "stand-in", "--model", "claude-opus-5-5"],
		{ cwd: dir, env: { ...process.env, PI_CODING_AGENT_DIR: agent, HV_STORE: store, HV_HOME: dir }, stdio: ["pipe", "pipe", "inherit"] },
	);
	const settled = settling(pi.stdout!);
	run = "max";
	pi.stdin!.write(`${JSON.stringify({ type: "prompt", message: "max-marker start board-fix" })}\n`);
	// The watch's first look, as pi starts, learns the session busy; a later one sees its turn end.
	await settled.next();
	run = "idle";
	registered("idle");
	await settled.next();
	run = "told";
	await post(store, { at: new Date().toISOString(), from: "agents:board-fix", text: "told-marker the fix is on its branch" });
	await settled.next();
	run = "long";
	pi.stdin!.write(`${JSON.stringify({ type: "prompt", message: `long-marker ${"more than an entry holds. ".repeat(30)}` })}\n`);
	await settled.next();
	run = "starting";
	pi.stdin!.write(`${JSON.stringify({ type: "prompt", message: "starting-marker hello" })}\n`);
	// A second in, the run waits for the gist; the watch looks twice in the seven seconds left of the wait.
	await new Promise((settle) => setTimeout(settle, 1000));
	await post(store, { at: new Date().toISOString(), from: "agents:board-fix", text: "while-starting-marker reported as a turn starts" });
	const both = () => ["max: starting-marker hello", "while-starting-marker"].every((marker) => logged().includes(marker));
	for (const start = Date.now(); !both() && Date.now() - start < 30_000; ) await new Promise((settle) => setTimeout(settle, 100));
	pi.stdin!.end();
	await new Promise((resolve) => pi.on("close", resolve));
});
after(async () => {
	await anthropic?.close();
	rmSync(dir, { recursive: true, force: true });
});

const logged = () => readFileSync(path.join(store, "log", "LOG.txt"), "utf8");

/** `next()` resolves at the next `agent_settled` pi reports, one already reported included; it fails after 20 s without one. */
function settling(stdout: NodeJS.ReadableStream) {
	let buffer = "";
	let settled = 0;
	let taken = 0;
	stdout.on("data", (chunk: Buffer) => {
		buffer += chunk.toString();
		for (let at = buffer.indexOf("\n"); at >= 0; at = buffer.indexOf("\n")) {
			const record = JSON.parse(buffer.slice(0, at));
			buffer = buffer.slice(at + 1);
			if (record.type === "agent_settled") settled++;
		}
	});
	return {
		async next() {
			for (const start = Date.now(); settled === taken; await new Promise((settle) => setTimeout(settle, 50)))
				if (Date.now() - start > 20_000) throw new Error(`no turn settled within 20 s (run ${run})`);
			taken++;
		},
	};
}

test("a spawned session's turn ending starts a turn of the hypervisor's own, carrying the event after the view", () => {
	const [request] = runs.get("idle") ?? [];
	assert.ok(request, "a request with no message from max");
	assert.equal(request.messages.length, 2);
	assert.ok(textOf(request.messages[0]).includes("max-marker"), "the earlier turn is in the view");
	assert.equal(textOf(request.messages[1]), "<event>\nagents:board-fix: busy → idle\n</event>");
	assert.ok(request.system?.some(conversing), "the hypervisor's system prompt");
});

test("an orchestrator's hv tell starts a turn carrying what it said and where from", () => {
	const [request] = runs.get("told") ?? [];
	assert.ok(request);
	assert.equal(textOf(request.messages.at(-1)!), "<event>\nagents:board-fix (hv tell): told-marker the fix is on its branch\n</event>");
	assert.ok(!request.messages.slice(1).some((m) => textOf(m).includes("max-marker")), "no message of an earlier turn");
});

test("the log keeps each event as the event's, not max's", () => {
	const log = readFileSync(path.join(store, "log", "LOG.txt"), "utf8");
	assert.match(log, /event: agents:board-fix: busy → idle/);
	assert.match(log, /event: agents:board-fix \(hv tell\): told-marker the fix is on its branch/);
	assert.doesNotMatch(log, /max: <event>/);
});

test("an event that arrives while a turn is starting waits for it to run, and neither the turn's message nor the event is lost", () => {
	assert.match(logged(), /max: starting-marker hello/);
	assert.match(logged(), /event: agents:board-fix \(hv tell\): while-starting-marker reported as a turn starts/);
});
