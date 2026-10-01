// lifelong-hypervisor#P4 at the tool registry: the extension is loaded into a stand-in for pi, and every tool it
// registers is run with generated arguments while its processes and file writes are watched.

import assert from "node:assert/strict";
import { mkdtempSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import type { ExtensionAPI, ToolDefinition } from "@earendil-works/pi-coding-agent";
import fc from "fast-check";
import { under, watchEffects } from "./effects.ts";
import { isStub, liftedBy } from "./lifted-by.ts";
import { paramsFor } from "./params.ts";

const store = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-store-")));
const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-home-")));
after(() => {
	rmSync(store, { recursive: true, force: true });
	rmSync(home, { recursive: true, force: true });
});
const effects = watchEffects(store);
const { hypervisor } = await import("../../src/index.ts");
const { exploreTools } = await import("../../src/explore.ts");

/** The parent's closed set: spawn, tell, look and delegate, and the memory tools. */
const CONVERSE = ["spawn", "tell", "look", "delegate", "zoom", "recall", "raw"];
const MEMORY = ["zoom", "recall", "raw"];
/** pi's own tools, the first four active unless an extension changes the set. */
const PI_TOOLS = ["read", "bash", "edit", "write", "grep", "find", "ls"];
const PI_ACTIVE = PI_TOOLS.slice(0, 4);
/** The programs a tool may start: tmux and claude for sessions, uv for the store, memex for the explorer. */
const PROGRAMS = new Set(["tmux", "claude", "uv", "memex"]);
/** Strings that do harm wherever a tool hands them to a shell or uses them as a path. */
const HOSTILE = fc.oneof(
	fc.string(),
	fc.constantFrom("; touch pwned", "$(touch pwned)", "`touch pwned`", "x\nrm -rf ~", "../../../../tmp/pwned", "/tmp/pwned", "-rf", "--help"),
);

// Answers anything a tool or handler asks of its context, and awaits as nothing.
const inert: any = new Proxy(() => {}, { get: (_, key) => (key === "then" ? undefined : inert), apply: () => undefined });
const context = new Proxy({ cwd: home, hasUI: false } as Record<PropertyKey, unknown>, { get: (target, key) => (key in target ? target[key] : inert) });

/** The extension loaded as pi loads it, through to session start; `flipped` sets every boolean flag it registers. */
async function load(flipped: boolean) {
	const tools = new Map<string, ToolDefinition>();
	const flags = new Map<string, { type: string; default?: unknown }>();
	const handlers = new Map<string, ((event: unknown, ctx: unknown) => unknown)[]>();
	let active = [...PI_ACTIVE];
	const api: Record<string, unknown> = {
		registerTool(tool: ToolDefinition) {
			tools.set(tool.name, tool);
			const exposure = tool.exposure ?? "direct";
			if ((tool.defaultActive ?? (exposure === "direct" || exposure === "model-only")) && !active.includes(tool.name)) active.push(tool.name);
		},
		setActiveTools(names: string[]) {
			active = names.filter((name) => tools.has(name) || PI_TOOLS.includes(name));
		},
		getActiveTools: () => [...active],
		on(event: string, handler: (event: unknown, ctx: unknown) => unknown) {
			handlers.set(event, [...(handlers.get(event) ?? []), handler]);
			return () => {};
		},
		registerFlag(name: string, options: { type: string; default?: unknown }) {
			flags.set(name, options);
		},
		getFlag(name: string) {
			const flag = flags.get(name);
			return flipped && flag?.type === "boolean" ? !flag.default : flag?.default;
		},
		// pi's exec starts its program without a shell; it is watched as a process like any other.
		exec: async (command: string, args: string[]) => {
			const { execFile } = await import("node:child_process");
			execFile(command, args, () => {});
			return { stdout: "", stderr: "", code: 0, killed: false };
		},
	};
	const pi = new Proxy(api, { get: (target, key) => (key in target ? target[key as string] : inert) }) as unknown as ExtensionAPI;
	hypervisor({ store, home })(pi);
	for (const handler of handlers.get("session_start") ?? []) await handler({ type: "session_start", reason: "startup" }, context);
	return { tools, active };
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

test("lifelong-hypervisor#P4: the extension's tools are the closed set, and none of pi's own stays active", liftedBy("hypervisor-view-swap"), async () => {
	const allowed = new Set([...CONVERSE, ...explorerToolNames()]);
	for (const flipped of [false, true]) {
		const { tools, active } = await load(flipped);
		assert.deepEqual([...tools.keys()].filter((name) => !allowed.has(name)), [], "tools outside the closed set");
		assert.deepEqual(active.filter((name) => !tools.has(name)), [], "pi's own tools still active");
		if (!flipped) assert.deepEqual(MEMORY.filter((name) => !tools.has(name)), [], "memory tools missing");
	}
});

test("lifelong-hypervisor#P4: no tool runs a shell or writes outside the store, whatever its arguments", liftedBy("hypervisor-view-swap"), async () => {
	for (const flipped of [false, true]) {
		const { tools } = await load(flipped);
		for (const tool of tools.values()) {
			await fc.assert(
				fc.asyncProperty(paramsFor(tool.parameters as never, HOSTILE), async (params) => {
					const seen = await effects.during(() => settled(tool, params));
					for (const { program, args, shell } of seen.launches) {
						const command = [program, ...args].join(" ");
						assert.equal(shell, false, `${tool.name} ran a shell: ${command}`);
						assert.ok(PROGRAMS.has(path.basename(program)), `${tool.name} started ${command}`);
						// Typing into a pane is max's own channel (the parent's Tell), and a pane runs what it is typed.
						if (path.basename(program) === "tmux") assert.ok(!args.some((a) => /^send(-keys)?$/.test(a)), `${tool.name} typed into a pane: ${command}`);
					}
					for (const file of seen.writes) assert.ok(file !== "fd" && under(file, store), `${tool.name} wrote ${file}`);
				}),
				{ numRuns: 25 },
			);
		}
	}
});

/** Runs a tool to its end, or for a second at most; its errors are its own business here. */
async function settled(tool: ToolDefinition, params: unknown) {
	const stop = new AbortController();
	const timer = setTimeout(() => stop.abort(), 1000);
	try {
		await Promise.race([
			tool.execute("p4", params as never, stop.signal, undefined, context as never),
			new Promise((settle) => stop.signal.addEventListener("abort", settle)),
		]);
	} catch (error) {
		if (isStub(error)) throw error;
	} finally {
		clearTimeout(timer);
	}
}
