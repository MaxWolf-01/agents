// lifelong-hypervisor#P4 at the tool registry, and the half of #P1 the extension's provider hook could break: the
// extension is loaded into a stand-in for pi, and its tools and handlers run while its processes and writes are watched.

import assert from "node:assert/strict";
import { mkdtempSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import fc from "fast-check";
import { watchEffects } from "./effects.ts";
import { HOSTILE, paramsFor } from "./params.ts";
import { harnessProblems, strings, toolProblems } from "./rules.ts";
import { VIEW_OPEN } from "../../src/swap.ts";
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

/** How long a tool or handler runs before the check moves on; what it does after that is stray. */
const LIMIT = 1000;
const MEMORY = ["zoom", "recall", "raw"];
/** The parent's closed set of tools. */
const CONVERSE = ["start_session", "tell_session", "look", "delegate", ...MEMORY];
/** The explorer's read tools, which join the set under `--explore`. */
const EXPLORE = ["read", "ls", "find", "grep", "memex"];

/** The extension loaded, with what loading it did. */
async function loaded(flipped: boolean) {
	let extension!: Awaited<ReturnType<typeof load>>;
	const atLoad = await effects.during(async () => {
		extension = await load(hypervisor({ store, home }), home, flipped);
	});
	return { ...extension, atLoad };
}

// The extension registers exactly the closed set, the parent's tools active in a conversation, and under `--explore`
// (`flipped`) the explorer's read tools in place of the session tools.
test("lifelong-hypervisor#P4: the extension's tools are the closed set, and none of pi's own stays active", async () => {
	for (const flipped of [false, true]) {
		const { tools, active } = await loaded(flipped);
		assert.deepEqual([...tools.keys()].sort(), [...CONVERSE, ...EXPLORE].sort(), "the tools registered");
		assert.deepEqual([...active].sort(), (flipped ? [...MEMORY, ...EXPLORE] : CONVERSE).sort(), flipped ? "the tools active under --explore" : "the tools active");
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
/** A cache breakpoint as pi's Anthropic provider places one, on a system block or a tool. */
const breakpoint = fc.constantFrom({ type: "ephemeral" }, { type: "ephemeral", ttl: "1h" });
const block = fc.record({ type: fc.constant("text"), text: fc.string({ maxLength: 30 }), cache_control: breakpoint }, { requiredKeys: ["type", "text"], noNullPrototype: true });
const tool = fc.record(
	{ name: fc.string({ minLength: 1, maxLength: 12 }), description: fc.string({ maxLength: 30 }), input_schema: fc.constant({ type: "object", properties: {} }), cache_control: breakpoint },
	{ requiredKeys: ["name", "description", "input_schema"], noNullPrototype: true },
);
const message = fc.record({ role: fc.constantFrom("user", "assistant"), content: fc.array(block, { minLength: 1, maxLength: 2 }) }, { noNullPrototype: true });
/** The view's message, as the context swap puts it first: lines the hook may split into blocks and close with breakpoints. */
const view = fc
	.array(fc.string({ maxLength: 20 }).map((text) => `2026-10-01T14:07 #1 ${text.replace(/\n/g, " ")}`), { maxLength: 4 })
	.map((lines) => ({ role: "user", content: [{ type: "text", text: `${VIEW_OPEN}${lines.join("\n")}\n</view>` }] }));
// A request as the Anthropic provider sends it, which is what the provider hook sees.
const payload = fc.record(
	{
		model: fc.constant("claude-opus-5-5"),
		max_tokens: fc.constant(32000),
		system: fc.array(block, { minLength: 1, maxLength: 3 }),
		tools: fc.array(tool, { maxLength: 5 }),
		messages: fc.tuple(fc.option(view, { nil: undefined }), fc.array(message, { minLength: 1, maxLength: 4 })).map(([first, rest]) => (first ? [first, ...rest] : rest)),
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
