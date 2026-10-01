import assert from "node:assert/strict";
import { test } from "node:test";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { swapContext } from "../src/swap.ts";

const user = (text: string, timestamp: number) => ({ role: "user", content: text, timestamp }) as AgentMessage;
const said = (text: string, timestamp: number) => ({ role: "assistant", content: [{ type: "text", text }], stopReason: "stop", timestamp }) as AgentMessage;

test("a message max sends while a run goes stays in the run's turn, when the run says where it started", () => {
	const messages = [user("earlier", 1), said("done", 2), user("start", 3), said("working", 4), user("correction", 5)];
	assert.deepEqual(swapContext(messages, "v", 2).slice(1), messages.slice(2));
	assert.deepEqual(swapContext(messages, "v").slice(1), messages.slice(4));
});
