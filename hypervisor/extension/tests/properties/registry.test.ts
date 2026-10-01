// lifelong-hypervisor#P4 at the tool registry, and the half of #P1 the extension's provider hook could break: the
// extension is loaded into a stand-in for pi, and its tools and handlers run while its processes and writes are watched.

import assert from "node:assert/strict";
import { mkdtempSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import fc from "fast-check";
import { watchEffects } from "./effects.ts";
import { isStub } from "./lifted-by.ts";
import { paramsFor } from "./params.ts";
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
const { hypervisor } = await import("../../src/index.ts");
const { exploreTools } = await import("../../src/explore.ts");

/** How long a tool or handler runs before the check moves on; what it does after that is stray. */
const LIMIT = 1000;
const MEMORY = ["zoom", "recall", "raw"];
/** The parent's closed set of tools. */
const CONVERSE = ["spawn", "tell", "look", "delegate", ...MEMORY];
/** Strings that do harm wherever a tool hands them to a shell or uses them as a path. */
const HOSTILE = fc.oneof(
	fc.string(),
	fc.constantFrom("; touch pwned", "$(touch pwned)", "`touch pwned`", "x\nrm -rf ~", "../../../../tmp/pwned", "/tmp/pwned", "-rf", "--help", "#(touch pwned)"),
);

/** The extension loaded, with what loading it did. */
async function loaded(flipped: boolean) {
	let extension!: Awaited<ReturnType<typeof load>>;
	const atLoad = await effects.during(async () => {
		extension = await load(hypervisor({ store, home }), home, flipped);
	});
	return { ...extension, atLoad };
}

/** The explorer's tools are allowed by name too; before its slice lands there are none. */
function explorerToolNames(): string[] {
	try {
		return exploreTools({ home }).map((tool) => tool.name);
	} catch (error) {
		if (isStub(error)) return [];
		throw error;
	}
}

// Within the closed set rather than equal to it: the memory tools land first (hypervisor-view-swap), the session
// tools after (hypervisor-orchestrators), and the check has to hold at each step.
test("lifelong-hypervisor#P4: the extension's tools are within the closed set, and none of pi's own stays active", async () => {
	const allowed = new Set([...CONVERSE, ...explorerToolNames()]);
	for (const flipped of [false, true]) {
		const { tools, active } = await loaded(flipped);
		assert.deepEqual([...tools.keys()].filter((name) => !allowed.has(name)), [], "tools outside the closed set");
		assert.deepEqual(active.filter((name) => !tools.has(name)), [], "pi's own tools still active");
		if (!flipped) assert.deepEqual(MEMORY.filter((name) => !tools.has(name)), [], "memory tools missing");
	}
});

test("lifelong-hypervisor#P4: no tool runs a shell or writes outside the store, whatever its arguments", async () => {
	for (const flipped of [false, true]) {
		const extension = await loaded(flipped);
		assert.deepEqual(harnessProblems(extension.atLoad, store), [], "loading the extension");
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
	}
	// The last run's tool may still be going: give it as long again before reading what came after the limits. A
	// tool still running past that reaches no assertion.
	await new Promise((settle) => setTimeout(settle, LIMIT));
	assert.deepEqual(effects.stray, { launches: [], writes: [] }, "effects after a tool's or handler's time ran out");
});

type Block = { type: string; text?: string; cache_control?: unknown };
const block = fc.record({ type: fc.constant("text"), text: fc.string({ maxLength: 30 }) }, { noNullPrototype: true });
// A request as the Anthropic provider sends it, which is what the provider hook sees.
const payload = fc.record(
	{
		model: fc.constant("claude-opus-5-5"),
		max_tokens: fc.constant(32000),
		system: fc.array(block, { minLength: 1, maxLength: 3 }),
		tools: fc.array(fc.record({ name: fc.string({ minLength: 1, maxLength: 12 }), description: fc.string({ maxLength: 30 }), input_schema: fc.constant({ type: "object", properties: {} }) }, { noNullPrototype: true }), { maxLength: 5 }),
		messages: fc.array(fc.record({ role: fc.constantFrom("user", "assistant"), content: fc.array(block, { minLength: 1, maxLength: 2 }) }, { noNullPrototype: true }), { minLength: 1, maxLength: 4 }),
	},
	{ noNullPrototype: true },
);

/** A request's system prompt and tools, without the cache breakpoints a hook may place in them. */
function promptAndTools(request: { system: Block[]; tools: object[] }) {
	const bare = (o: object) => Object.fromEntries(Object.entries(o).filter(([key]) => key !== "cache_control"));
	return { system: request.system.map(bare), tools: request.tools.map(bare) };
}

test("lifelong-hypervisor#P1: a request leaves the extension with its system prompt and tools", async () => {
	const { handlers, context } = await loaded(false);
	await fc.assert(
		fc.asyncProperty(payload, async (sent) => {
			let request = structuredClone(sent);
			const seen = await effects.during(async () => {
				for (const handler of handlers.get("before_provider_request") ?? []) request = ((await handler({ type: "before_provider_request", payload: request }, context)) as typeof request) ?? request;
			});
			assert.deepEqual(promptAndTools(request), promptAndTools(sent));
			assert.deepEqual(harnessProblems(seen, store), []);
		}),
	);
});
