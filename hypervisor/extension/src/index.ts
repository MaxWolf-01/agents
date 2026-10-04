import { appendFile, mkdir, writeFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { AHEAD, placeBreakpoints, remember, viewEnds, type Written } from "./breakpoints.ts";
import { saidIn } from "./entries.ts";
import { eventMessage } from "./events.ts";
import { exploreTools } from "./explore.ts";
import type { Finished } from "./forks.ts";
import { memory } from "./memory.ts";
import { store as openStore } from "./store.ts";
import { swapContext } from "./swap.ts";
import { memoryTools, sessionTools } from "./tools.ts";
import { watch } from "./watch.ts";

export interface Config {
	/** The store's directory, the one place the extension and its tools write. */
	store: string;
	/**
	 * max's home: the explorer reads under it, a relative path the model sends starts there, and its `.claude*`
	 * directories list the live Claude Code sessions.
	 */
	home: string;
}

const PROMPT = fileURLToPath(new URL("../system-prompt.md", import.meta.url));
/** What the system prompt gains in a conversation, where the session tools are the agent's, and in explore mode. */
const SESSIONS_PROMPT = fileURLToPath(new URL("../sessions-prompt.md", import.meta.url));
const EXPLORE_PROMPT = fileURLToPath(new URL("../explore-prompt.md", import.meta.url));
/** The view the run in flight started from, in the store. */
const VIEW = "view.txt";
/** How often the spawned sessions and the inbox are looked at. */
const WATCH_MS = 3000;

/**
 * The hypervisor as a pi extension. It registers the hypervisor's tools and makes them the whole active set, so none
 * of pi's own tools (`bash`, `edit`, `write`, an unguarded `read`) stays active. With `--explore`, each run is one
 * explore step: the explorer's read tools take the session tools' place, the system prompt explore mode's part theirs, and
 * the step is logged as its tool calls and its finding. Outside explore mode, what the spawned sessions do and what
 * orchestrators leave with `hv tell` reach the agent as `<event>` messages, which start a turn of their own when none
 * runs.
 *
 * Under `config.store`: `log/`, the store's own directory; `view.txt`, the view the latest run started from;
 * `requests.jsonl`, a line for each request sent, what it
 * carried in brief, with the error when the store's `stays` failed for its run; `forks.jsonl`, a line for each fork,
 * with the tokens each of its calls read from cache and wrote; `lost.jsonl`, a line for each turn the log could not
 * take; `spawned.jsonl`, a line for each window spawn opened; `inbox/`, what `hv tell` left and the watch has not taken;
 * `watch.jsonl`, a line for each look of the watch that failed.
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
		const watchLog = jsonl("watch.jsonl");
		const mind = memory(store, { fork: jsonl("forks.jsonl"), lost: jsonl("lost.jsonl") });
		const tools = memoryTools(store);
		const steering = sessionTools(config);
		const reading = exploreTools(config);
		for (const tool of [...tools, ...steering, ...reading]) pi.registerTool(tool);
		pi.registerFlag("explore", { type: "boolean", default: false, description: "Run each prompt as one step of exploring max's machine." });
		const exploring = () => pi.getFlag("explore") === true;

		/** The view of the run in flight, rendered once as it starts, so its requests share one prefix. */
		let view: string | undefined;
		/** After how many of the view's lines its breakpoints go, kept past the run for the requests that warm its cache. */
		let ends: number[] = [];
		/** The view's prefixes the requests sent wrote to the cache, while their entries live. */
		let written: Written[] = [];
		/** Why the store's `stays` failed for the run in flight, which its requests' log lines carry. */
		let failed: string | undefined;
		const render = async () => {
			failed = undefined;
			const rendered = await mind.view();
			// What the agent wakes to, kept where max reads it (`hv view`); a turn goes on without it.
			await writeFile(path.join(config.store, VIEW), `${rendered}\n`).catch(() => {});
			// Without the store's `stays`, the view still reads what earlier requests wrote; the request log says why.
			const stays = await store.stays(AHEAD).catch((error) => {
				failed = String(error);
				return [];
			});
			ends = viewEnds(rendered.split("\n"), stays, written, Date.now());
			return rendered;
		};
		/** What max sent to start the run in flight, and when its first request saw it. */
		let prompt: string | undefined;
		let start: number | undefined;
		/** The last request the run in flight sent, the one its forks continue. */
		let sent: Finished["payload"] | undefined;

		let watching: ReturnType<typeof watch> | undefined;
		/**
		 * Whether a run is past `before_agent_start` and not yet running. pi counts a run as running only once that
		 * hook returns, and this one waits for the view, so an event sent then would start a second run beside it.
		 */
		let starting = false;

		pi.on("session_start", async (_event, ctx) => {
			pi.setActiveTools([...tools, ...(exploring() ? reading : steering)].map((tool) => tool.name));
			await store.init();
			// An event goes when pi starts a run with it (idle) or queues it (running), never while it compacts or starts.
			const ready = () => !starting && (ctx.isIdle() || ctx.signal !== undefined);
			if (!exploring())
				watching ??= watch(
					config,
					WATCH_MS,
					(events) => pi.sendUserMessage(eventMessage(events), { deliverAs: "followUp" }),
					(error) => void watchLog({ at: new Date().toISOString(), error: String(error) }).catch(() => {}),
					ready,
				);
		});
		pi.on("before_agent_start", async (event) => {
			starting = true;
			try {
				view = await render();
			} catch (error) {
				starting = false;
				throw error;
			}
			prompt = typeof event.prompt === "string" ? event.prompt : undefined;
			return { systemPrompt: `${system.trimEnd()}\n\n${readFileSync(exploring() ? EXPLORE_PROMPT : SESSIONS_PROMPT, "utf8")}` };
		});
		pi.on("agent_start", () => {
			starting = false;
		});
		pi.on("agent_settled", () => {
			starting = false;
		});
		pi.on("context", async (event) => {
			if (!Array.isArray(event.messages)) return undefined;
			view ??= await render();
			start ??= event.messages.findLast((m) => m.role === "user")?.timestamp;
			const at = event.messages.findIndex((m) => m.role === "user" && m.timestamp === start);
			return { messages: swapContext(event.messages, view, at < 0 ? undefined : at) };
		});
		pi.on("before_provider_request", async (event) => {
			const placed = placeBreakpoints(event.payload, ends);
			if (placed === undefined) return undefined;
			written = remember(written, placed, Date.now());
			// pi's cache warming re-sends the last request for one token; a fork continues the run's own.
			const warm = (placed as { max_tokens?: number }).max_tokens === 1;
			if (!warm) sent = placed as Finished["payload"];
			await requests({ ...brief(placed as Finished["payload"]), ...(warm ? { warm } : {}), ...(failed ? { stays: failed } : {}) });
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
			mind.finish([...asked, ...event.messages], finished, exploring() ? "step" : "turn");
			view = prompt = start = sent = undefined;
		});
		pi.on("session_shutdown", async () => {
			watching?.stop();
			watching = undefined;
			await mind.settled();
		});
	};
}

/**
 * A request in brief: each message's role and the head of each of its blocks, with the blocks a breakpoint closes
 * marked. Text blocks that follow a text block, neither closed by a breakpoint, are counted rather than shown: the
 * view is a block per line.
 */
function brief(payload: Finished["payload"]) {
	type Block = { type: string; text?: string; cache_control?: unknown };
	const head = (block: Block) => `${block.cache_control ? "[cached] " : ""}${block.type === "text" ? JSON.stringify((block.text ?? "").slice(0, 120)) : block.type}`;
	const plain = (block: Block | undefined) => block?.type === "text" && !block.cache_control;
	const heads = (content: Block[]) => {
		const out: string[] = [];
		let more = 0;
		const counted = () => {
			if (more) out.push(`+${more} text blocks`);
			more = 0;
		};
		for (const [i, block] of content.entries()) {
			if (plain(block) && plain(content[i - 1])) more++;
			else {
				counted();
				out.push(head(block));
			}
		}
		counted();
		return out;
	};
	return {
		at: new Date().toISOString(),
		messages: payload.messages.map((m) => ({ role: m.role, blocks: typeof m.content === "string" ? [JSON.stringify(m.content.slice(0, 120))] : heads(m.content) })),
	};
}

/** The configuration from the environment: the store `$HV_STORE`, or `~/.local/share/hypervisor`; the home `$HV_HOME`, or home. */
export function fromEnvironment(): Config {
	return { store: process.env.HV_STORE ?? path.join(homedir(), ".local/share/hypervisor"), home: process.env.HV_HOME ?? homedir() };
}

/** The extension as pi loads it (`pi -e`). */
export default hypervisor(fromEnvironment());
