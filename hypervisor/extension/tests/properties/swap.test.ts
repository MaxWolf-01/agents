// lifelong-hypervisor#P1 at the context swap, over generated histories: any number of turns, each a user message and
// any number of tool rounds, and a current turn cut off anywhere after its user message.

import assert from "node:assert/strict";
import { test } from "node:test";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import fc from "fast-check";
import { swapContext } from "../../src/swap.ts";
import { liftedBy } from "./lifted-by.ts";

const text = fc.string({ maxLength: 30 });
const usage = { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } };
const assistant = (content: unknown[], stopReason: string) => ({ role: "assistant", content, api: "anthropic-messages", provider: "anthropic", model: "claude-opus-5-5", usage, stopReason });

const user = fc
	.oneof(text, fc.array(fc.record({ type: fc.constant("text"), text }, { noNullPrototype: true }), { minLength: 1, maxLength: 3 }))
	.map((content) => [{ role: "user", content }]);
const call = fc.record({
	type: fc.constant("toolCall"),
	id: fc.uuid(),
	name: fc.string({ minLength: 1, maxLength: 10 }),
	arguments: fc.dictionary(fc.string({ maxLength: 8 }), fc.oneof(text, fc.integer()), { noNullPrototype: true }),
}, { noNullPrototype: true });
// One model response that calls tools, then each call's result.
const round = fc.tuple(fc.option(text, { nil: undefined }), fc.array(call, { minLength: 1, maxLength: 3 }), fc.array(text, { minLength: 3, maxLength: 3 }), fc.boolean()).map(([said, calls, results, isError]) => [
	assistant([...(said === undefined ? [] : [{ type: "text", text: said }]), ...calls], "toolUse"),
	...calls.map((c, i) => ({ role: "toolResult", toolCallId: c.id, toolName: c.name, content: [{ type: "text", text: results[i] }], isError })),
]);
const answer = text.map((said) => [assistant([{ type: "text", text: said }], "stop")]);
const turn = fc.tuple(user, fc.array(round, { maxLength: 3 }), answer).map(([u, rounds, a]) => [...u, ...rounds.flat(), ...a]);
// The current turn as the swap meets it: before any model call of the turn, or between two of them.
const current = fc.tuple(turn, fc.nat()).map(([messages, cut]) => messages.slice(0, 1 + (cut % messages.length)));

/** A history split where the swap must split it, every message stamped later than the one before. */
const history = fc.tuple(fc.array(turn, { maxLength: 6 }), current).map(([earlier, now]) => {
	const stamp = (messages: object[], from: number) => messages.map((m, i) => ({ ...m, timestamp: 1_790_000_000_000 + (from + i) * 1000 }) as AgentMessage);
	const before = stamp(earlier.flat(), 0);
	return { before, now: stamp(now, before.length) };
});
const view = fc.array(fc.string({ minLength: 1, maxLength: 40 }), { minLength: 1, maxLength: 12 }).map((lines) => lines.join("\n"));

function textOf(message: AgentMessage): string {
	const content = (message as { content?: unknown }).content;
	if (typeof content === "string") return content;
	return Array.isArray(content) ? content.map((part) => (part.type === "text" ? part.text : "")).join("") : "";
}

function withoutTimestamp(message: AgentMessage) {
	const { timestamp: _, ...rest } = message as AgentMessage & { timestamp?: number };
	return rest;
}

test("lifelong-hypervisor#P1: a request carries the view and the current turn, and no message from an earlier turn", liftedBy("hypervisor-view-swap"), () => {
	fc.assert(
		fc.property(history, history, view, ({ before, now }, other, rendered) => {
			const messages = [...before, ...now];
			const given = structuredClone(messages);
			const sent = swapContext(messages, rendered);

			assert.deepEqual(messages, given, "the swap changed the session's messages");
			assert.deepEqual(sent.slice(1), now, "the current turn, whole and in order, follows the view");
			assert.ok(textOf(sent[0]).includes(rendered), "the first message holds the view");
			// The view's message is the view's alone: another history with the same view yields the same one.
			const elsewhere = swapContext([...other.before, ...other.now], rendered);
			assert.deepEqual(withoutTimestamp(elsewhere[0]), withoutTimestamp(sent[0]), "the view's message carries something of the history");
			assert.deepEqual(swapContext(messages, rendered), sent, "the same history and view gave a different request");
		}),
	);
});
