import assert from "node:assert/strict";
import { test } from "node:test";
import { placeBreakpoints, stableEnds } from "../src/breakpoints.ts";

const HEADER = "now 2026-10-01T14:07 (Thu), 2 minutes since the last entry, #300";

test("a view of single entries is stable to its last entry", () => {
	assert.deepEqual(stableEnds(["2026-10-01T14:00 #0 a", "2026-10-01T14:01 #1 b", HEADER, "</view>"]), [2]);
});

test("a view with blocks is split after its last block of 128 entries or more, and of 32 or more", () => {
	const view = ["T #0-255 a", "T #256-383 b", "T #384-415 c", "T #416-431 d", "T #432 e", HEADER, "</view>"];
	assert.deepEqual(stableEnds(view), [2, 3]);
	assert.deepEqual(stableEnds(["T #0-15 a", "T #16-23 b", "T #24 c", HEADER]), []);
});

// pi's request on an OAuth key: a breakpoint on both system blocks, the last tool, and the last message.
const mark = { type: "ephemeral" };
const view = "<view>\nT #0-255 a\nT #256-383 b\nT #384-415 c\nT #416 d\nnow\n</view>";
const request = {
	model: "claude-opus-5-5",
	system: [{ type: "text", text: "You are Claude Code", cache_control: mark }, { type: "text", text: "the prompt", cache_control: mark }],
	tools: [{ name: "zoom" }, { name: "raw", cache_control: mark }],
	messages: [
		{ role: "user", content: [{ type: "text", text: view }] },
		{ role: "user", content: [{ type: "text", text: "hi", cache_control: mark }] },
	],
};

test("the breakpoints on the tools and the first system block move into the view, which keeps its text", () => {
	const placed = placeBreakpoints(request) as typeof request;
	assert.deepEqual(placed.system.map((b) => "cache_control" in b), [false, true]);
	assert.deepEqual(placed.tools.map((b) => "cache_control" in b), [false, false]);
	const blocks = placed.messages[0].content as { text: string; cache_control?: unknown }[];
	assert.deepEqual(blocks.map((b) => [b.text, b.cache_control]), [
		["<view>\nT #0-255 a\nT #256-383 b\n", mark],
		["T #384-415 c\n", mark],
		["T #416 d\nnow\n</view>", undefined],
	]);
	assert.deepEqual(placed.messages[1], request.messages[1]);
});

test("a request without breakpoints gets none in the view", () => {
	const bare = { ...request, system: [{ type: "text", text: "the prompt" }], tools: [] };
	assert.equal(((placeBreakpoints(bare) as typeof request).messages[0].content as object[]).length, 1);
});
