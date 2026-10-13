// How the hypervisor paces itself: wait and a background delegate return at once, and what they wait on reaches the
// inbox later as a ping, which the watch delivers at once (live.test.ts). job and claude are stand-ins on PATH that
// record how they were called and answer once the test releases them.

import assert from "node:assert/strict";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import type { ToolDefinition } from "@earendil-works/pi-coding-agent";
import { type Told, waiting } from "../src/inbox.ts";
import { background, STOPPED, waitTool } from "../src/pace.ts";
import { sessionTools } from "../src/tools.ts";

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-pace-")));
after(() => rmSync(dir, { recursive: true, force: true }));
const home = path.join(dir, "home");
const bin = path.join(dir, "bin");
mkdirSync(home);
mkdirSync(bin);
// Each stand-in records its arguments in `<program>.calls`, then waits for `<program>.release`, whose first line is
// the exit code and whose rest it prints.
for (const program of ["job", "claude"]) {
	writeFileSync(
		path.join(bin, program),
		`#!${process.execPath}
const fs = require("node:fs");
const at = ${JSON.stringify(dir)} + "/" + ${JSON.stringify(program)};
fs.appendFileSync(at + ".calls", JSON.stringify(process.argv.slice(2)) + "\\n");
const answer = () => {
	if (!fs.existsSync(at + ".release")) return setTimeout(answer, 20);
	const [code, ...said] = fs.readFileSync(at + ".release", "utf8").split("\\n");
	process.stdout.write(said.join("\\n"));
	process.exit(Number(code));
};
answer();
`,
	);
	chmodSync(path.join(bin, program), 0o755);
}
process.env.PATH = `${bin}:${process.env.PATH}`;

/** A store of the test's own, background work posting to its inbox, and the tools that start that work. */
function setUp() {
	const store = realpathSync(mkdtempSync(path.join(dir, "store-")));
	for (const program of ["job", "claude"]) rmSync(path.join(dir, `${program}.release`), { force: true });
	for (const program of ["job", "claude"]) rmSync(path.join(dir, `${program}.calls`), { force: true });
	const work = background(store);
	const call = (tool: ToolDefinition, params: object) => tool.execute("call", params as never, undefined, undefined, undefined as never).then(textOf);
	const wait = (params: object) => call(waitTool(work), params);
	const delegate = (params: object) => call(sessionTools({ home, store }, work).find((t) => t.name === "delegate")!, params);
	return { store, work, wait, delegate };
}

const release = (program: string, code: number, said: string) => writeFileSync(path.join(dir, `${program}.release`), `${code}\n${said}`);
const calls = (program: string) => readFileSync(path.join(dir, `${program}.calls`), "utf8").trim().split("\n").map((line) => JSON.parse(line) as string[]);
const textOf = (result: { content: { type: string; text?: string }[] }) => result.content.map((c) => c.text ?? "").join("");
/** What waits in the inbox, once `count` messages do, or after `within` ms. */
async function pinged(store: string, { count = 1, within = 5000 } = {}): Promise<Told[]> {
	for (const end = Date.now() + within; Date.now() < end; await new Promise((settle) => setTimeout(settle, 20))) {
		const told = waiting(store);
		if (told.length >= count) return told.map(({ at, from, text, ping }) => ({ at, from, text, ping }));
	}
	return waiting(store);
}

test("wait on a job returns at once, and the job's end reaches the inbox as a ping [wait <job>] with job's status line", async () => {
	const { store, wait } = setUp();
	const said = await wait({ job: "api-build", minutes: 20, stall: 1.5, note: "check the migration" });
	assert.match(said, /api-build/);
	await pinged(store, { within: 300 });
	assert.deepEqual(waiting(store), [], "nothing arrives while the job runs");
	release("job", 0, "done  exit=0 ended=2026-10-13T12:00:00+00:00 secs=4\n-- log tail\nok");
	const [told] = await pinged(store);
	assert.equal(told.from, "wait api-build");
	assert.equal(told.ping, true);
	assert.equal(told.text, "done  exit=0 ended=2026-10-13T12:00:00+00:00 secs=4\n-- log tail\nok\nYour note: check the migration");
	assert.deepEqual(calls("job"), [["wait", "api-build", "--deadline", "1200", "--stall", "90"]]);
});

test("a deadline that passes first reaches the inbox as job says it, whatever its exit code", async () => {
	const { store, wait } = setUp();
	await wait({ job: "api-build", minutes: 1 });
	release("job", 5, "deadline  not finished 60s into this wait");
	const [told] = await pinged(store);
	assert.deepEqual([told.from, told.text, told.ping], ["wait api-build", "deadline  not finished 60s into this wait", true]);
});

test("the model's arguments reach job as its arguments, and never a shell", async () => {
	const { store, wait } = setUp();
	const pattern = "$(touch pwned); `touch pwned` | rm -rf ~";
	await wait({ job: "build", minutes: 1, watch: pattern });
	release("job", 3, "watch  pattern matched");
	await pinged(store);
	assert.deepEqual(calls("job"), [["wait", "build", "--deadline", "60", "--watch", pattern]]);
	assert.ok(!existsSync(path.join(process.cwd(), "pwned")) && !existsSync(path.join(bin, "pwned")));
});

test("wait refuses what job would misread, and a wait with no deadline", async () => {
	const { wait } = setUp();
	for (const params of [{ job: "build" }, { job: "build", minutes: 0 }, { job: "--status", minutes: 1 }, { job: "a b", minutes: 1 }, { job: "build", minutes: 1, watch: "-f/etc/passwd" }, { minutes: 1, stall: 2 }])
		await assert.rejects(wait(params), Error, JSON.stringify(params));
	assert.ok(!existsSync(path.join(dir, "job.calls")), "job never ran");
});

test("wait with no job is a timer: a ping [wait] once the minutes are up", async () => {
	const { store, wait } = setUp();
	await wait({ minutes: 0.002, note: "look at agents:board" });
	const [told] = await pinged(store);
	assert.deepEqual([told.from, told.text, told.ping], ["wait", "0.002 minutes are up.\nYour note: look at agents:board", true]);
});

test("wait with probe lists the jobs", async () => {
	const { wait } = setUp();
	release("job", 0, "api-build running  since 2026-10-13T12:00:00+00:00");
	assert.equal(await wait({ probe: true }), "api-build running  since 2026-10-13T12:00:00+00:00");
	assert.deepEqual(calls("job"), [["probe"]]);
});

test("a background delegate returns an id at once, and its answer reaches the inbox as a ping [delegate <id>]", async () => {
	const { store, delegate } = setUp();
	const said = await delegate({ task: "summarise the board", background: true });
	const id = /Delegated as (\w+)/.exec(said)?.[1];
	assert.ok(id, said);
	assert.deepEqual(waiting(store), []);
	release("claude", 0, "three tickets wait on max\n");
	const [told] = await pinged(store);
	assert.deepEqual([told.from, told.text, told.ping], [`delegate ${id}`, "three tickets wait on max", true]);
	assert.equal(calls("claude")[0][1], "--permission-mode");
});

test("a background delegate that fails says so in its ping; one with no task is refused before it starts", async () => {
	const { store, delegate } = setUp();
	await assert.rejects(delegate({ task: " ", background: true }), /empty/);
	await delegate({ task: "x", background: true });
	release("claude", 1, "");
	const [told] = await pinged(store);
	assert.match(told.text, /^failed: claude -p/);
});

test("without background, delegate answers in the turn, as before", async () => {
	const { store, delegate } = setUp();
	release("claude", 0, "the answer");
	assert.equal(await delegate({ task: "x" }), "the answer");
	assert.deepEqual(waiting(store), []);
});

test("what still runs when the session ends posts that it stopped, and work started after runs again", async () => {
	const { store, work, wait } = setUp();
	await wait({ job: "api-build", minutes: 20 });
	await wait({ minutes: 20 });
	await work.stop();
	const told = waiting(store);
	assert.deepEqual(told.map((m) => [m.from, m.text, m.ping]).sort(), [["wait api-build", STOPPED, true], ["wait", STOPPED, true]]);
	await wait({ minutes: 0.001 });
	assert.match((await pinged(store, { count: 3 })).at(-1)!.text, /minutes are up/);
});
