// lifelong-hypervisor#P4 at the tool registry: the live extension is loaded into a stand-in for pi, and its tools and
// handlers run while its processes and writes are watched.

import assert from "node:assert/strict";
import { mkdtempSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import fc from "fast-check";
import { watchEffects } from "./effects.ts";
import { HOSTILE, paramsFor } from "./params.ts";
import { harnessProblems, strings, toolProblems } from "./rules.ts";
import { execute, load, standIn, within } from "./stand-in.ts";

const store = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-store-")));
const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-home-")));
const effects = watchEffects(store);
after(() => {
	effects.stop();
	rmSync(store, { recursive: true, force: true });
	rmSync(home, { recursive: true, force: true });
});
const { live } = await import("../../src/live.ts");

/** How long a tool or handler runs before the check moves on; what it does after that is stray. */
const LIMIT = 1000;

test("lifelong-hypervisor#P4: the extension registers the closed set: the session tools, the inbox, wait and the explorer's read tools", async () => {
	const { tools } = await load(live({ store, home }), home);
	const SESSIONS = ["start_session", "tell_session", "look", "delegate"];
	const READ = ["read", "ls", "find", "grep", "memex"];
	assert.deepEqual([...tools.keys()].sort(), [...SESSIONS, "inbox", "wait", ...READ].sort());
});

test("lifelong-hypervisor#P4: no tool runs a shell or writes outside the store, whatever its arguments", async () => {
	let extension!: Awaited<ReturnType<typeof load>>;
	const atLoad = await effects.during(async () => {
		extension = await load(live({ store, home }), home);
	});
	assert.deepEqual(harnessProblems(atLoad, store), [], "loading the extension");
	for (const [event, handlers] of extension.handlers) {
		const seen = await effects.during(() => Promise.all(handlers.map((handler) => within(LIMIT, async () => handler(standIn({ type: event }), extension.context)))));
		assert.deepEqual(harnessProblems(seen, store), [], `its ${event} handler`);
	}
	for (const tool of extension.tools.values()) {
		await fc.assert(
			fc.asyncProperty(paramsFor(tool.parameters, HOSTILE), async (params) => {
				const seen = await effects.during(() => execute(tool, params, extension.context, LIMIT));
				assert.deepEqual(toolProblems(seen, store, strings(params)), [], `${tool.name} ${JSON.stringify(params)}`);
			}),
			{ numRuns: 25 },
		);
	}
	// The last run's tool may still be going: give it as long again before reading what came after the limits. A
	// tool still running past that reaches no assertion.
	await new Promise((settle) => setTimeout(settle, LIMIT));
	assert.deepEqual(effects.stray, { launches: [], writes: [] }, "effects after a tool's or handler's time ran out");
});
