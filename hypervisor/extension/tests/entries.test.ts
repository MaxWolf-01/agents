// A finished run as entries: a turn of max's keeps every message, an explore step only its tool calls and its finding.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { test } from "node:test";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import fc from "fast-check";
import { entriesOf, fits } from "../src/entries.ts";

const run = [
	{ role: "user", content: "Explore step 2. Your goal: …", timestamp: 1 },
	{ role: "assistant", content: [{ type: "text", text: "looking at notes first" }, { type: "toolCall", id: "c1", name: "read", arguments: { path: "notes/today.md" } }] },
	{ role: "toolResult", toolCallId: "c1", toolName: "read", content: [{ type: "text", text: "ship explore mode" }], isError: false, timestamp: 2 },
	{ role: "assistant", content: [{ type: "text", text: "max ships explore mode today (~/notes/today.md)" }] },
] as unknown as AgentMessage[];

test("a turn logs max's message, each text of the agent's, and each tool call", () => {
	assert.deepEqual(
		entriesOf(run).map((e) => e.text),
		["max: Explore step 2. Your goal: …", "me: looking at notes first", 'read {"path":"notes/today.md"} → ship explore mode', "me: max ships explore mode today (~/notes/today.md)"],
	);
});

test("an explore step logs its tool calls and its last text as the finding, and not the harness's message", () => {
	assert.deepEqual(
		entriesOf(run, "step").map((e) => e.text),
		['read {"path":"notes/today.md"} → ship explore mode', "finding: max ships explore mode today (~/notes/today.md)"],
	);
});

const STORE = path.resolve(import.meta.dirname, "../../store");
/** Whitespace and line breaks of either language, the ones where Python and JavaScript part ways among them. */
const TRICKY = [..."\n\r\v\f\t \x1c\x1f\x85\xa0", ...[0x2028, 0x2029, 0x3000, 0xfeff].map((c) => String.fromCodePoint(c)), "é", "€", "𝄞"];

test("an entry holds a text as it is exactly when the store does, so a text the store would clip gets a gist", () => {
	const texts = [
		...fc.sample(fc.string({ unit: fc.oneof(fc.constantFrom(...TRICKY), fc.constantFrom("a", "b")), maxLength: 8 }), { numRuns: 2000, seed: 42 }),
		...[510, 511, 512, 513].flatMap((n) => ["a".repeat(n), `${"a".repeat(n - 2)}é`, `${"a".repeat(n - 4)}𝄞`]),
	];
	// The store's own judgment, `as_entry`, run over every text in one process.
	const judged = spawnSync("uv", ["run", "--quiet", "--with", "tyro", "python", "-c", `import json, sys; sys.path.insert(0, ${JSON.stringify(STORE)}); from hv_store import as_entry; print(json.dumps([as_entry(t)[1] is None for t in json.load(sys.stdin)]))`], {
		input: JSON.stringify(texts),
		encoding: "utf8",
	});
	assert.equal(judged.status, 0, judged.stderr);
	const asIs: boolean[] = JSON.parse(judged.stdout);
	const disagree = texts.filter((t, i) => fits(t) !== asIs[i]);
	assert.deepEqual(disagree.map((t) => JSON.stringify(t)), []);
});

test("a call whose run ended before its result is logged without one, and a failed call's result as an error", () => {
	const calls = [
		{ role: "assistant", content: [{ type: "toolCall", id: "c1", name: "look", arguments: {} }, { type: "toolCall", id: "c2", name: "raw", arguments: { id: 3 } }] },
		{ role: "toolResult", toolCallId: "c2", toolName: "raw", content: [{ type: "text", text: "no entry #3" }], isError: true, timestamp: 2 },
	] as unknown as AgentMessage[];
	assert.deepEqual(
		entriesOf(calls).map((e) => e.text),
		["look {} → (no result)", 'raw {"id":3} → error: no entry #3'],
	);
});
