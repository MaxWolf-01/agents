import { appendFile, mkdir } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { placeBreakpoints } from "./breakpoints.ts";
import { saidIn } from "./entries.ts";
import type { Finished } from "./forks.ts";
import { memory } from "./memory.ts";
import { store as openStore } from "./store.ts";
import { swapContext } from "./swap.ts";
import { memoryTools } from "./tools.ts";

export interface Config {
	/** The store's directory, the one place the extension and its tools write. */
	store: string;
	/** The home directory of the machine the explorer reads; a relative path the model sends starts here. */
	home: string;
}

const PROMPT = fileURLToPath(new URL("../system-prompt.md", import.meta.url));

/**
 * The hypervisor as a pi extension. It registers the hypervisor's tools and makes them the whole active set, so none
 * of pi's own tools (`bash`, `edit`, `write`, an unguarded `read`) stays active.
 *
 * Under `config.store`: `log/`, the store's own directory; `requests.jsonl`, a line for each request sent, what it
 * carried in brief; `forks.jsonl`, a line for each fork, with the tokens each of its calls read from cache and wrote;
 * `lost.jsonl`, a line for each turn the log could not take.
 */
export function hypervisor(config: Config): (pi: ExtensionAPI) => void {
	return (pi) => {
		const system = readFileSync(PROMPT, "utf8");
		const store = openStore(path.join(config.store, "log"));
		const jsonl = (name: string) => async (line: object) => {
			await mkdir(config.store, { recursive: true });
			await appendFile(path.join(config.store, name), `${JSON.stringify(line)}\n`);
		};
		const requests = jsonl("requests.jsonl");
		const mind = memory(store, { fork: jsonl("forks.jsonl"), lost: jsonl("lost.jsonl") });
		const tools = memoryTools(store);
		for (const tool of tools) pi.registerTool(tool);

		/** The view of the run in flight, rendered once as it starts, so its requests share one prefix. */
		let view: string | undefined;
		/** What max sent to start the run in flight, and when its first request saw it. */
		let prompt: string | undefined;
		let start: number | undefined;
		/** The last request the run in flight sent, the one its forks continue. */
		let sent: Finished["payload"] | undefined;

		pi.on("session_start", async () => {
			pi.setActiveTools(tools.map((tool) => tool.name));
			await store.init();
		});
		pi.on("before_agent_start", async (event) => {
			view = await mind.view();
			prompt = typeof event.prompt === "string" ? event.prompt : undefined;
			return { systemPrompt: system };
		});
		pi.on("context", async (event) => {
			if (!Array.isArray(event.messages)) return undefined;
			view ??= await mind.view();
			start ??= event.messages.findLast((m) => m.role === "user")?.timestamp;
			const at = event.messages.findIndex((m) => m.role === "user" && m.timestamp === start);
			return { messages: swapContext(event.messages, view, at < 0 ? undefined : at) };
		});
		pi.on("before_provider_request", async (event) => {
			const placed = placeBreakpoints(event.payload);
			if (placed === undefined) return undefined;
			// pi's cache warming re-sends the last request for one token; a fork continues the run's own.
			const warm = (placed as { max_tokens?: number }).max_tokens === 1;
			if (!warm) sent = placed as Finished["payload"];
			await requests({ ...brief(placed as Finished["payload"]), ...(warm ? { warm } : {}) });
			return placed;
		});
		pi.on("agent_end", async (event, ctx) => {
			if (!Array.isArray(event.messages)) return;
			const last = event.messages.at(-1);
			const answered = last?.role === "assistant" && last.stopReason !== "error" && last.stopReason !== "aborted";
			const answer = answered ? saidIn(last) : "";
			const finished = sent && ctx.model ? { payload: sent, answer, model: ctx.model, models: ctx.modelRegistry, sessionId: ctx.sessionManager.getSessionId() } : undefined;
			// A run that fails hands over its failure alone, without the message that started it.
			const asked = !event.messages.some((m) => m.role === "user") && prompt ? [{ role: "user" as const, content: prompt, timestamp: start ?? Date.now() }] : [];
			mind.finish([...asked, ...event.messages], finished);
			view = prompt = start = sent = undefined;
		});
		pi.on("session_shutdown", async () => {
			await mind.settled();
		});
	};
}

/** A request in brief: each message's role and the head of each of its blocks, with the blocks a breakpoint closes marked. */
function brief(payload: Finished["payload"]) {
	const head = (block: { type: string; text?: string; cache_control?: unknown }) =>
		`${block.cache_control ? "[cached] " : ""}${block.type === "text" ? JSON.stringify((block.text ?? "").slice(0, 120)) : block.type}`;
	return {
		at: new Date().toISOString(),
		messages: payload.messages.map((m) => ({ role: m.role, blocks: typeof m.content === "string" ? [JSON.stringify(m.content.slice(0, 120))] : m.content.map(head) })),
	};
}

/** The extension as pi loads it (`pi -e`): the store under `$HV_STORE`, or `~/.local/share/hypervisor`. */
export default hypervisor({ store: process.env.HV_STORE ?? path.join(homedir(), ".local/share/hypervisor"), home: homedir() });
