// The turn's way through the log: what the view waits for, against a stand-in for the store's process and the model.

import assert from "node:assert/strict";
import { test } from "node:test";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import type { Finished } from "../src/forks.ts";
import { type ForkRecord, type LostRecord, memory } from "../src/memory.ts";
import { Refused, type Store } from "../src/store.ts";

const HEADER = "now 2026-10-01T14:07 (Thu), 2 minutes since the last entry, #3";

/** A store whose view needs `needed` compressed, with every call it gets in `calls`; an append of `refused` fails. */
function standInStore(needed: string[], refused = "") {
	const calls: string[] = [];
	const written = new Set<string>();
	const store = {
		append: async (text: string, gist = "") => {
			if (text === refused) throw new Refused("No store at /gone. `init` creates one.");
			calls.push(`append ${gist || text}`);
			return calls.length;
		},
		due: async () => needed.filter((b) => !written.has(b)),
		body: async (block: string) => `body of ${block}`,
		compress: async (block: string, line: string) => {
			calls.push(`compress ${block} ${line}`);
			written.add(block);
			return "";
		},
		view: async () => {
			calls.push("view");
			const missing = needed.filter((b) => !written.has(b));
			if (missing.length) throw new Refused(`The view needs compressions not written yet: ${missing.join(" ")}.`);
			return `${HEADER}\n2026-10-01T14:00 #0-1 a block\n2026-10-01T14:05 #2 an entry\n`;
		},
	};
	return { store: store as unknown as Store, calls };
}

/** A turn whose forks answer after `ms`, or fail. */
function finished(ms: number, fail = false): Finished {
	const usage = { input: 1, output: 1, cacheRead: 9, cacheWrite: 0, totalTokens: 11, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } };
	return {
		payload: { messages: [{ role: "user", content: [{ type: "text", text: "<view>\n</view>" }] }] },
		model: {} as Finished["model"],
		models: {
			complete: async () => {
				await new Promise((settle) => setTimeout(settle, ms));
				return { role: "assistant", content: [{ type: "text", text: "the line" }], usage, stopReason: fail ? "error" : "stop", errorMessage: "overloaded" } as never;
			},
		},
	};
}

/** A journal that keeps what it is given. */
function journal() {
	const kept = { forks: [] as ForkRecord[], lost: [] as LostRecord[] };
	return { kept, journal: { fork: async (f: ForkRecord) => void kept.forks.push(f), lost: async (l: LostRecord) => void kept.lost.push(l) } };
}

const turn = [
	{ role: "user", content: "what is in flight?", timestamp: 1 },
	{ role: "assistant", content: [{ type: "text", text: "nothing yet" }], stopReason: "stop", timestamp: 2 },
] as AgentMessage[];

test("the view waits for the turn before it to be logged, and puts its header last", async () => {
	const { store, calls } = standInStore([]);
	const mind = memory(store, journal().journal);
	mind.finish(turn, finished(0));
	assert.equal(await mind.view(), `2026-10-01T14:00 #0-1 a block\n2026-10-01T14:05 #2 an entry\n${HEADER}`);
	assert.deepEqual(calls, ["append max: what is in flight?", "append me: nothing yet", "view"]);
});

test("the view waits for a compression it needs, and renders once the fork has written it", async () => {
	const { store, calls } = standInStore(["0-1"]);
	const { kept, journal: j } = journal();
	const mind = memory(store, j);
	mind.finish(turn, finished(50));
	assert.match(await mind.view(), /#0-1 a block/);
	assert.ok(calls.indexOf("compress 0-1 the line") < calls.lastIndexOf("view"));
	assert.deepEqual(kept.forks.map((f) => [f.kind, f.of, f.calls[0].usage.cacheRead]), [["compression", "0-1", 9]]);
});

test("a view whose compression no fork could write says so in the view's place", async () => {
	const { store } = standInStore(["0-1"]);
	const { kept, journal: j } = journal();
	const mind = memory(store, j);
	mind.finish(turn, finished(0, true));
	assert.match(await mind.view(), /^\(no view: The view needs compressions not written yet: 0-1\.\)$/);
	assert.match(kept.forks[0].error ?? "", /overloaded/);
});

test("a turn is logged while the compressions of the turn before it are still being written", async () => {
	const { store, calls } = standInStore(["0-1"]);
	const mind = memory(store, journal().journal);
	mind.finish(turn, finished(30));
	mind.finish(turn.slice(0, 1), finished(0));
	await mind.settled();
	assert.deepEqual(calls, ["append max: what is in flight?", "append me: nothing yet", "append max: what is in flight?", "compress 0-1 the line"]);
});

test("a turn the log could not take is journaled, and the next view says so once", async () => {
	const { store } = standInStore([], "me: nothing yet");
	const { kept, journal: j } = journal();
	const mind = memory(store, j);
	mind.finish(turn, finished(0));
	assert.match(await mind.view(), /\(not logged: the turn ending .*, from its entry "me: nothing yet" on: Refused: No store at \/gone.*\)\nnow /);
	assert.deepEqual(kept.lost.map((l) => l.entries), [["me: nothing yet"]]);
	assert.doesNotMatch(await mind.view(), /not logged/);
});
