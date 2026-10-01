// A finished run as entries: a turn of max's keeps every message, an explore step only its tool calls and its finding.

import assert from "node:assert/strict";
import { test } from "node:test";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { entriesOf } from "../src/entries.ts";

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
