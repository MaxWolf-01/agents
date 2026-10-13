// The extension in a real pi, run over RPC against a stand-in for the Anthropic endpoint, on an OAuth-shaped key as max's
// subscription is: what the requests carry across ten turns, what the log keeps, and what the forks send and record.

import assert from "node:assert/strict";
import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { HYPERVISOR, MODEL, PI } from "../src/pi.ts";
import { conversing, type Reply, type Request, standInAnthropic, standInModels, textOf, USAGE } from "./stand-in-anthropic.ts";

const TURNS = 10;
const LONG = `turn-3-marker ${"a long message that no entry holds as it is. ".repeat(20)}`;
const LONG_ANSWER = `a long answer to turn 7: ${"more than an entry holds. ".repeat(30)}`;
/** What max says in each turn: one carries a text too long for an entry, one asks for a tool and is steered meanwhile. */
const said = (n: number) => (n === 3 ? LONG : n === 5 ? `turn-5-marker please zoom into 0-1` : `turn-${n}-marker hello`);

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-pi-")));
const store = path.join(dir, "store");
let anthropic: Awaited<ReturnType<typeof standInAnthropic>>;
const sent: { turn: number; request: Request }[] = [];
let turn = 0;
/** Sends the steering message, once the request it is to arrive during is on its way. */
let steer: (() => void) | undefined;

function answer(request: Request): Reply {
	const last = textOf(request.messages.at(-1)!);
	const block = /Write the compression of entries #(\S+)/.exec(last);
	if (block) return { text: `compressed ${block[1]}` };
	if (last.includes("is too long for one entry")) return { text: last.includes("Max's message") ? "turn-3-marker: max sent a long message, its gist" : "the gist of a long answer" };
	sent.push({ turn, request });
	if (last.includes("please zoom")) {
		steer?.();
		steer = undefined;
		return { tool: "zoom", input: { block: "0-1" }, delay: 1000 };
	}
	return { text: turn === 7 ? LONG_ANSWER : `noted turn ${turn}` };
}

before(async () => {
	anthropic = await standInAnthropic(answer);
	const agent = path.join(dir, "agent");
	mkdirSync(agent);
	standInModels(agent, anthropic.url);
	const pi = spawn(
		process.execPath,
		[PI, "--mode", "rpc", "--no-session", "--offline", ...HYPERVISOR, "--provider", "stand-in", "--model", "claude-opus-5-5"],
		{ cwd: dir, env: { ...process.env, PI_CODING_AGENT_DIR: agent, HV_STORE: store, HV_HOME: dir }, stdio: ["pipe", "pipe", "inherit"] },
	);
	for (turn = 1; turn <= TURNS; turn++) await prompt(pi, said(turn), turn === 5 ? "turn-5-steer" : undefined);
	pi.stdin!.end();
	await new Promise((resolve) => pi.on("close", resolve));
});
after(async () => {
	await anthropic?.close();
	rmSync(dir, { recursive: true, force: true });
});

/** Sends one prompt, and `steering` while its first reply is on the way, and resolves once pi has settled. */
function prompt(pi: ChildProcess, message: string, steering?: string): Promise<void> {
	if (steering) steer = () => pi.stdin!.write(`${JSON.stringify({ type: "steer", message: steering })}\n`);
	return new Promise((resolve, reject) => {
		let buffer = "";
		const read = (chunk: Buffer) => {
			buffer += chunk.toString();
			for (let at = buffer.indexOf("\n"); at >= 0; at = buffer.indexOf("\n")) {
				const record = JSON.parse(buffer.slice(0, at));
				buffer = buffer.slice(at + 1);
				if (record.type === "response" && !record.success) reject(new Error(record.error));
				if (record.type === "agent_settled") {
					pi.stdout!.off("data", read);
					resolve();
				}
			}
		};
		pi.stdout!.on("data", read);
		pi.stdin!.write(`${JSON.stringify({ type: "prompt", message })}\n`);
	});
}

const lines = (name: string) => readFileSync(path.join(store, name), "utf8").trim().split("\n").map((line) => JSON.parse(line));

test("lifelong-hypervisor#P1: every request carries the view, which holds the earlier turns, and none of their messages", () => {
	assert.ok(sent.length > TURNS, "a request for each turn and one more for the tool's result");
	for (const { turn, request } of sent) {
		const [view, ...rest] = request.messages;
		assert.ok(textOf(view).startsWith("<view>\n"), `turn ${turn}: the first message is the view`);
		for (let earlier = 1; earlier < turn; earlier++) {
			assert.ok(textOf(view).includes(`turn-${earlier}-marker`), `turn ${turn}: the view holds turn ${earlier}`);
			// A tool's result may quote the log; a message of the turn itself may not.
			assert.ok(!rest.some((m) => textOf(m, false).includes(`turn-${earlier}-marker`)), `turn ${turn}: a message of turn ${earlier} was sent`);
		}
		assert.ok(textOf(rest[0]).includes(`turn-${turn}-marker`), `turn ${turn}: the turn's own message follows the view`);
	}
});

test("a message max sends while a turn runs joins that turn, which keeps its earlier messages", () => {
	const steered = sent.filter(({ request }) => request.messages.slice(1).some((m) => textOf(m).includes("turn-5-steer")));
	assert.equal(steered.length, 1);
	const text = steered[0].request.messages.slice(1).map((m) => textOf(m)).join("\n");
	assert.match(text, /turn-5-marker please zoom[\s\S]*#0 max: turn-1-marker hello[\s\S]*turn-5-steer/);
});

test("a request carries at most four cache breakpoints, some of them inside the view", () => {
	for (const { request } of sent) {
		const blocks = [...(request.system ?? []), ...(request.tools ?? []), ...request.messages.flatMap((m) => (Array.isArray(m.content) ? m.content : []))];
		assert.ok(blocks.filter((b) => b.cache_control).length <= 4);
	}
	const view = sent.at(-1)!.request.messages[0].content as { cache_control?: unknown }[];
	assert.ok(view.some((b) => b.cache_control), "the view of a log of single entries is cached whole");
});

test("below the budget, each turn's first request closes a breakpoint on all the view lines of the turn before", () => {
	type Block = { text?: string; cache_control?: unknown };
	const closed = (request: Request) => {
		const blocks = request.messages[0].content as Block[];
		return blocks.flatMap((b, i) => (b.cache_control ? [blocks.slice(0, i + 1).map((x) => x.text).join("")] : []));
	};
	const viewLines = (request: Request) => (request.messages[0].content as Block[]).map((b) => b.text).join("").replace(/now [^\n]*\n<\/view>$/, "");
	const firsts = Array.from({ length: TURNS }, (_, i) => sent.find(({ turn }) => turn === i + 1)!.request);
	for (const [i, request] of firsts.entries().drop(1)) {
		assert.equal((request.messages[0].content as Block[]).length, viewLines(request).split("\n").length, `turn ${i + 1}: a block per line, the header, and the closing tag`);
		// The first turn woke to an empty log, a view of no lines.
		if (i > 1) assert.ok(closed(request).includes(viewLines(firsts[i - 1])), `turn ${i + 1}: the view lines of turn ${i}`);
	}
});

test("the memory and session tools are the whole tool set, and zoom answers from the store", () => {
	for (const { request } of sent) assert.deepEqual(request.tools?.map((t) => t.name).sort(), ["delegate", "look", "raw", "recall", "start_session", "tell_session", "zoom"]);
	const results = sent.flatMap(({ request }) => request.messages.flatMap((m) => (m.content as { type: string }[]).filter((b) => b.type === "tool_result")));
	assert.equal(results.length, 1);
	assert.match(JSON.stringify(results[0]), /#0 max: turn-1-marker hello.*#1 me: noted turn 1/);
});

test("the system prompt is the hypervisor's", () => {
	for (const { request } of sent) assert.ok(request.system?.some(conversing));
});

test("a fork sends the turn's last request as it went, then the turn's answer and its ask", () => {
	const forks = anthropic.requests.filter((r) => /Write the compression|is too long for one entry/.test(textOf(r.messages.at(-1)!)));
	assert.ok(forks.length > 0);
	for (const fork of forks) {
		const parent = sent.filter(({ request }) => JSON.stringify(request.messages) === JSON.stringify(fork.messages.slice(0, -2)));
		assert.equal(parent.length, 1, "the request whose messages the fork's begin with");
		const { request, turn } = parent[0];
		assert.deepEqual(fork.messages.at(-2), { role: "assistant", content: [{ type: "text", text: turn === 7 ? LONG_ANSWER : `noted turn ${turn}` }] });
		assert.deepEqual({ ...fork, messages: [] }, { ...request, messages: [] }, "system prompt, tools and options as sent");
	}
	assert.ok(forks.some((f) => textOf(f.messages.at(-2)!) === LONG_ANSWER && textOf(f.messages.at(-1)!).includes("is too long")), "the long answer's gist is asked with the answer before it");
});

test("the log holds every turn: the long message by its gist, with its whole text kept raw", () => {
	const log = readFileSync(path.join(store, "log", "LOG.txt"), "utf8");
	for (let n = 1; n <= TURNS; n++) assert.ok(log.includes(`turn-${n}-marker`), `turn ${n}`);
	assert.ok(log.includes("max: turn-3-marker: max sent a long message, its gist [raw:"));
	assert.ok(log.includes("me: the gist of a long answer [raw:"));
});

test("each fork's calls are logged with the tokens they read from cache and wrote", () => {
	const forks = lines("forks.jsonl");
	assert.ok(forks.some((f) => f.kind === "gist") && forks.some((f) => f.kind === "compression"));
	for (const fork of forks) {
		assert.equal(fork.error, undefined);
		assert.deepEqual(fork.calls[0].usage, { input: USAGE.input_tokens, output: USAGE.output_tokens, cacheRead: USAGE.cache_read_input_tokens, cacheWrite: USAGE.cache_creation_input_tokens });
	}
});

test("the request log has a line for each request the turns sent", () => {
	assert.equal(lines("requests.jsonl").length, sent.length);
});
