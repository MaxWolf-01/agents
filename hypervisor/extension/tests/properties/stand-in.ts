import type { ExtensionAPI, ToolDefinition } from "@earendil-works/pi-coding-agent";
import { isStub } from "./lifted-by.ts";

/** pi's own tools, the first four active unless an extension changes the set. */
const PI_TOOLS = ["read", "bash", "edit", "write", "grep", "find", "ls"];
const PI_ACTIVE = PI_TOOLS.slice(0, 4);

type Handler = (event: unknown, context: unknown) => unknown;
type Execute = ToolDefinition["execute"];

/** Answers anything asked of it, and awaits as nothing. */
export const inert: any = new Proxy(() => {}, { get: (_, key) => (key === "then" ? undefined : inert), apply: () => undefined });

/** An object with `fields`, answering anything else as `inert`: a context, or an event, as far as a check cares. */
export function standIn(fields: Record<PropertyKey, unknown>): any {
	return new Proxy(fields, { get: (target, key) => (key in target ? target[key] : inert) });
}

/**
 * An extension loaded as pi loads it, through to session start, into a stand-in for pi that keeps the tools it
 * registers, the tools active, and its event handlers. `flipped` sets every boolean flag the extension registers.
 */
export async function load(extension: (pi: ExtensionAPI) => void, cwd: string, flipped = false) {
	const tools = new Map<string, ToolDefinition>();
	const flags = new Map<string, { type: string; default?: unknown }>();
	const handlers = new Map<string, Handler[]>();
	const state = { active: [...PI_ACTIVE] };
	const api: Record<string, unknown> = {
		registerTool(tool: ToolDefinition) {
			tools.set(tool.name, tool);
			const exposure = tool.exposure ?? "direct";
			if ((tool.defaultActive ?? (exposure === "direct" || exposure === "model-only")) && !state.active.includes(tool.name)) state.active.push(tool.name);
		},
		setActiveTools(names: string[]) {
			state.active = names.filter((name) => tools.has(name) || PI_TOOLS.includes(name));
		},
		getActiveTools: () => [...state.active],
		on(event: string, handler: Handler) {
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
		// pi's exec starts its program without a shell, so it is a launch like any other.
		exec: async (command: string, args: string[]) => {
			const { execFile } = await import("node:child_process");
			execFile(command, args, () => {});
			return { stdout: "", stderr: "", code: 0, killed: false };
		},
	};
	const pi = standIn(api) as ExtensionAPI;
	extension(pi);
	const context = standIn({ cwd, hasUI: false });
	for (const handler of handlers.get("session_start") ?? []) await handler(standIn({ type: "session_start", reason: "startup" }), context);
	return { tools, active: state.active, handlers, context };
}

/** How one run of a tool or a handler ended: what it returned, what it threw, or that it had not ended in time. */
export interface Outcome {
	end: "returned" | "threw" | "late";
	said: string;
}

/** Runs `work` for `ms` at most, handing it the signal that aborts it then. A stub's error propagates. */
export async function within(ms: number, work: (signal: AbortSignal) => Promise<unknown>): Promise<Outcome> {
	const stop = new AbortController();
	const timer = setTimeout(() => stop.abort(), ms);
	const late = new Promise<Outcome>((settle) => stop.signal.addEventListener("abort", () => settle({ end: "late", said: "" })));
	try {
		return await Promise.race([work(stop.signal).then((result) => ({ end: "returned" as const, said: JSON.stringify(result) ?? "" })), late]);
	} catch (error) {
		if (isStub(error)) throw error;
		return { end: "threw", said: error instanceof Error ? `${error.message}\n${error.stack}` : String(error) };
	} finally {
		clearTimeout(timer);
	}
}

/** A tool run once as pi runs it, with arguments a model sent. */
export function execute(tool: ToolDefinition, params: unknown, context: unknown, ms: number): Promise<Outcome> {
	return within(ms, (signal) => tool.execute("check", params as Parameters<Execute>[1], signal, undefined, context as Parameters<Execute>[4]));
}
