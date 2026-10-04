import assert from "node:assert/strict";
import { test } from "node:test";
import { placeBreakpoints, remember, viewEnds, type Written } from "../src/breakpoints.ts";
import { cacheReads } from "./cache-model.ts";

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
	assert.deepEqual(placed.system.map((b) => b.text), sent.system.map((b) => b.text), "the system prompt as it came");
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

test("the view gets the first of its ends that the four breakpoints a request may carry leave room for", () => {
	const placed = placeBreakpoints(request(entries(0, 6)), [4, 2, 3, 1]) as Request;
	assert.deepEqual(placed.messages[0].content.flatMap((b, i) => (b.cache_control ? [i + 1] : [])), [2, 4]);
	// A system prompt sent as a string carries no breakpoint, so the last tool's moves into the view too.
	const string = placeBreakpoints({ ...request(entries(0, 6)), system: "the prompt" }, [4, 2, 3, 1]) as Request;
	assert.deepEqual(string.messages[0].content.flatMap((b, i) => (b.cache_control ? [i + 1] : [])), [2, 3, 4]);
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
	assert.deepEqual(viewEnds(view, Array(16).fill(15), written, 2 * MINUTE), [20, 15], "the read keeps nothing the next view starts with");
	assert.deepEqual(viewEnds(view, Array(16).fill(20), written, 2 * MINUTE), [20], "nothing ahead adds to what the read keeps");
});

test("past the budget, each breakpoint goes where it adds the most bytes the next view keeps over the turns ahead", () => {
	// Three lines of about 10 bytes: a 1-entry turn keeps all three, longer ones keep the first or none.
	const view = ["T #0-3 aa", "T #4-5 bb", "T #6 ccc", HEADER];
	assert.deepEqual(viewEnds(view, [3, 1, 1, 1, 0, 0], [], 0), [1, 3]);
	assert.deepEqual(viewEnds(view, [3, 3, 3, 1, 1, 1, 0], [], 0), [3, 1]);
	assert.deepEqual(viewEnds(view, [3, 0, 0, 0, 0, 0], [], 0), [3]);
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
	const again = remember(later, placeBreakpoints(request(entries(0, 5)), [5]), at + 7 * MINUTE);
	assert.deepEqual(again.filter((w) => w.lines.length === 5), [{ lines: entries(0, 5), expires: at + 12 * MINUTE }], "a prefix sent again is one entry, living from the latest send");
});

test("a request of another shape than the Anthropic provider's is left to pi", () => {
	for (const payload of [null, "a request", 7, { system: 3 }, { messages: [1] }, { tools: ["zoom"] }]) assert.equal(placeBreakpoints(payload, [1]), undefined, JSON.stringify(payload));
});

/** How many of the view's bytes each request reads from the cache. */
function viewReads(requests: Request[]): number[] {
	const blocks = requests.map((r) => [...r.system, ...r.messages.flatMap((m) => m.content)]);
	return cacheReads(blocks).map((read, i) => blocks[i].slice(requests[i].system.length, read + 1).reduce((sum, b) => sum + b.text.length, 0));
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
	const reads = viewReads(turns(ends.map((n) => entries(0, n)), ends.map((n) => Array(16).fill(n))));
	const viewOf = (n: number) => `<view>\n${entries(0, n).join("\n")}\n`.length;
	assert.deepEqual(reads, [0, viewOf(3), viewOf(10), viewOf(40)]);
});

test("past the budget, a turn reads the view's lines that an earlier turn's view also started with", () => {
	const block = (lo: number, hi: number) => `2026-10-01T14:00 #${lo}-${hi} summary of ${lo}-${hi}`;
	const a = [block(0, 255), block(256, 383), block(384, 447), ...entries(448, 450)];
	const b = [block(0, 255), block(256, 383), block(384, 447), block(448, 449), ...entries(450, 452)];
	const c = [block(0, 255), block(256, 383), block(384, 447), block(448, 449), block(450, 451), ...entries(452, 454)];
	// The store says a turn of two entries keeps the first four lines; the third view merges in the fifth line.
	const reads = viewReads(turns([a, b, c], [[5, 3, 3, 3], [4, 4, 4, 4], [5, 5, 5, 5]]));
	const prefix = (view: string[], n: number) => `<view>\n${view.slice(0, n).join("\n")}\n`.length;
	assert.deepEqual(reads, [0, prefix(b, 3), prefix(c, 4)]);
});
