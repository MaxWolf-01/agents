import assert from "node:assert/strict";
import { test } from "node:test";
import { placeBreakpoints, remember, viewEnds, type Written } from "../src/breakpoints.ts";

const HEADER = "now 2026-10-01T14:07 (Thu), 2 minutes since the last entry, #300";
const MINUTE = 60_000;

// pi's request on an OAuth key: a breakpoint on both system blocks, the last tool, and the last message.
const mark = { type: "ephemeral" };
type Block = { type: string; text: string; cache_control?: { type: string; ttl?: string } };
type Request = { system: Block[]; tools: { name: string; cache_control?: unknown }[]; messages: { role: string; content: Block[] }[] };

function request(view: string[], ttl?: string): Request {
	const m = ttl ? { ...mark, ttl } : mark;
	return {
		system: [{ type: "text", text: "You are Claude Code", cache_control: m }, { type: "text", text: "the prompt", cache_control: m }],
		tools: [{ name: "zoom" }, { name: "raw", cache_control: m }],
		messages: [
			{ role: "user", content: [{ type: "text", text: `<view>\n${view.join("\n")}\n</view>` }] },
			{ role: "user", content: [{ type: "text", text: "hi", cache_control: m }] },
		],
	};
}

const entries = (from: number, to: number) => Array.from({ length: to - from }, (_, i) => `2026-10-01T14:00 #${from + i} entry ${from + i}`);

test("the breakpoints on the tools and the first system block move into the view, sent as a block per line", () => {
	const view = ["T #0-255 a", "T #256-383 b", "T #384-415 c", "T #416 d", HEADER];
	const sent = request(view);
	const placed = placeBreakpoints(sent, [2, 3]) as Request;
	assert.deepEqual(placed.system.map((b) => "cache_control" in b), [false, true]);
	assert.deepEqual(placed.tools.map((b) => "cache_control" in b), [false, false]);
	assert.deepEqual(placed.messages[0].content.map((b) => [b.text, b.cache_control]), [
		["<view>\nT #0-255 a\n", undefined],
		["T #256-383 b\n", mark],
		["T #384-415 c\n", mark],
		["T #416 d\n", undefined],
		[`${HEADER}\n`, undefined],
		["</view>", undefined],
	]);
	assert.equal(placed.messages[0].content.map((b) => b.text).join(""), sent.messages[0].content[0].text);
	assert.deepEqual(placed.messages[1], sent.messages[1]);
});

test("the view gets no more breakpoints than the four a request may carry leave", () => {
	const placed = placeBreakpoints(request(entries(0, 6)), [1, 2, 3, 4]) as Request;
	assert.equal(placed.messages[0].content.filter((b) => b.cache_control).length, 2);
});

test("a request without breakpoints gets none in the view", () => {
	const bare = { ...request(entries(0, 3)), system: [{ type: "text", text: "the prompt" }], tools: [] };
	assert.equal((placeBreakpoints(bare, [2]) as Request).messages[0].content.length, 1);
});

test("below the budget, the next view starts with every line, so the breakpoint closes the last one", () => {
	const view = [...entries(0, 40), HEADER];
	assert.deepEqual(viewEnds(view, Array(16).fill(40), [], 0), [40]);
});

test("a lost turn's note and the header are never cached, whatever the store says stays", () => {
	const view = [...entries(0, 3), "(not logged: the turn ending 2026-10-01T14:05, …)", HEADER];
	assert.deepEqual(viewEnds(view, Array(16).fill(5), [], 0), []);
	assert.deepEqual(viewEnds(["(no view: The view needs compressions not written yet: 0-15.)", HEADER], Array(16).fill(1), [], 0), []);
});

test("one breakpoint reads the longest prefix an earlier request wrote that the view still starts with", () => {
	const view = [...entries(0, 30), HEADER];
	const written: Written[] = [
		{ lines: entries(0, 10), expires: 10 * MINUTE },
		{ lines: entries(0, 20), expires: 10 * MINUTE },
		{ lines: [...entries(0, 24), "2026-10-01T14:00 #24-25 merged since"], expires: 10 * MINUTE },
		{ lines: entries(0, 28), expires: MINUTE },
	];
	assert.deepEqual(viewEnds(view, Array(16).fill(30), written, 2 * MINUTE), [20, 30]);
});

test("past the budget, the breakpoints go where the next view keeps the most bytes over the turns ahead", () => {
	// Three lines of 10 bytes: a 1-entry turn keeps all three, longer ones keep the first or none.
	const view = ["T #0-3 aa", "T #4-5 bb", "T #6 ccc", HEADER];
	assert.deepEqual(viewEnds(view, [3, 1, 1, 1, 0, 0], [], 0), [1, 3]);
	assert.deepEqual(viewEnds(view, [3, 1, 1, 1, 0, 0], [], 0, 1), [1]);
	assert.deepEqual(viewEnds(view, [3, 0, 0, 0, 0, 0], [], 0, 1), [3]);
	assert.deepEqual(viewEnds(view, [0, 0, 0], [], 0), []);
});

test("a request leaves behind the prefixes its view's breakpoints close, for as long as their entries live", () => {
	const at = 1000;
	const fresh = remember([], placeBreakpoints(request(entries(0, 5)), [2, 5]), at);
	assert.deepEqual(fresh, [
		{ lines: entries(0, 2), expires: at + 5 * MINUTE },
		{ lines: entries(0, 5), expires: at + 5 * MINUTE },
	]);
	const later = remember(fresh, placeBreakpoints(request([...entries(0, 7), HEADER], "1h"), [5, 7]), at + 6 * MINUTE);
	assert.deepEqual(later, [
		{ lines: entries(0, 5), expires: at + 66 * MINUTE },
		{ lines: entries(0, 7), expires: at + 66 * MINUTE },
	]);
	assert.equal(remember(later, { messages: [] }, at), later);
});

/**
 * What each request reads from the cache, by the rules Anthropic's prompt-caching docs give: a breakpoint writes an
 * entry for the prefix it closes, and a read checks the breakpoint and up to 19 blocks before it for an entry an earlier
 * request wrote. Returns, for each request, how many of the view's bytes were read.
 */
function cacheReads(requests: Request[]): number[] {
	const cache = new Set<string>();
	return requests.map((r) => {
		const blocks = [...r.system, ...r.messages.flatMap((m) => m.content)];
		const prefixes = blocks.map((_, i) => JSON.stringify(blocks.slice(0, i + 1).map((b) => b.text)));
		const marked = blocks.flatMap((b, i) => (b.cache_control ? [i] : []));
		let read = -1;
		for (const at of marked) for (let i = at; i > at - 20 && i >= 0; i--) if (cache.has(prefixes[i])) {
			read = Math.max(read, i);
			break;
		}
		for (const at of marked) cache.add(prefixes[at]);
		const view = r.system.length;
		return blocks.slice(view, read + 1).reduce((sum, b) => sum + b.text.length, 0);
	});
}

/** The requests a run of turns sends, the extension placing the breakpoints as it does between turns. */
function turns(views: string[][], stays: number[][]): Request[] {
	let written: Written[] = [];
	return views.map((view, t) => {
		const lines = [...view, HEADER.replace("#300", `#${t}`)];
		const placed = placeBreakpoints(request(lines), viewEnds(lines, stays[t], written, t * MINUTE)) as Request;
		written = remember(written, placed, t * MINUTE);
		return placed;
	});
}

test("below the budget, each turn reads from the cache the whole view the turn before sent", () => {
	const ends = [3, 10, 40, 41];
	const reads = cacheReads(turns(ends.map((n) => entries(0, n)), ends.map((n) => Array(16).fill(n))));
	const viewOf = (n: number) => `<view>\n${entries(0, n).join("\n")}\n`.length;
	assert.deepEqual(reads, [0, viewOf(3), viewOf(10), viewOf(40)]);
});

test("past the budget, a turn reads the view's lines that an earlier turn's view also started with", () => {
	const block = (lo: number, hi: number) => `2026-10-01T14:00 #${lo}-${hi} summary of ${lo}-${hi}`;
	const a = [block(0, 255), block(256, 383), block(384, 447), ...entries(448, 450)];
	const b = [block(0, 255), block(256, 383), block(384, 447), block(448, 449), ...entries(450, 452)];
	const c = [block(0, 255), block(256, 383), block(384, 447), block(448, 449), block(450, 451), ...entries(452, 454)];
	// The store says a turn of two entries keeps the first four lines; the third view merges in the fifth line.
	const reads = cacheReads(turns([a, b, c], [[5, 3, 3, 3], [4, 4, 4, 4], [5, 5, 5, 5]]));
	const prefix = (view: string[], n: number) => `<view>\n${view.slice(0, n).join("\n")}\n`.length;
	assert.deepEqual(reads, [0, prefix(b, 3), prefix(c, 4)]);
});
