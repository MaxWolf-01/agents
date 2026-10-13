import { randomBytes } from "node:crypto";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ToolDefinition } from "@earendil-works/pi-coding-agent";
import { age, markRead, shown, size, waiting } from "./inbox.ts";
import { delegation, look, type SessionConfig, spawn, tell } from "./sessions.ts";
import type { Background } from "./pace.ts";
import type { Store } from "./store.ts";

/** A tool's answer: the text it printed, or `(nothing)`. */
export const answer = (text: string) => ({ content: [{ type: "text" as const, text: text.trimEnd() || "(nothing)" }], details: undefined });

/** The memory tools: each runs one store command and answers with what it printed. */
export function memoryTools(store: Store): ToolDefinition[] {
	return [
		defineTool({
			name: "zoom",
			label: "Zoom",
			description: "Show a block of your view one level finer: its two halves as view lines. Zoom again into a half to go deeper; a half of one entry is that entry.",
			parameters: Type.Object({ block: Type.String({ description: "The block as LO-HI, the numbers after # on its view line, e.g. 64-127." }) }),
			execute: async (_id, { block }) => answer(await store.zoom(block)),
		}),
		defineTool({
			name: "recall",
			label: "Recall",
			description: "Search your whole log, every entry ever logged, for a Python regex, ignoring case. Prints the matching entries, newest last.",
			parameters: Type.Object({ regex: Type.String({ description: "A Python regular expression." }) }),
			execute: async (_id, { regex }) => answer(await store.recall(regex)),
		}),
		defineTool({
			name: "raw",
			label: "Raw",
			description: "Print the whole text of one entry, for an entry whose line ends in [raw: N bytes].",
			parameters: Type.Object({ id: Type.Integer({ description: "The entry's number, after # on its line." }) }),
			execute: async (_id, { id }) => answer(await store.raw(id)),
		}),
	] as ToolDefinition[];
}

/** The details that have pi-optchat log a tool's result as `work` in memory, not as its echo (pi-optchat's `WORK_RESULT`). */
const WORK_RESULT = { optchat: "work" };

/** The inbox tool: what waits in the store's inbox, listed without its text, or read and so moved to `inbox/read/`. */
export function inboxTool(store: string): ToolDefinition {
	return defineTool({
		name: "inbox",
		label: "Inbox",
		description:
			"Your inbox: the messages that wait for you, from orchestrators' hv tell and from spawned sessions' turns ending. Without arguments, list them: id, sender, size and age. With an id, read that message; with a sender, read every message from it. A message you read leaves the inbox and stays in your memory.",
		parameters: Type.Object({
			id: Type.Optional(Type.String({ description: "A message's id, as the listing gives it." })),
			from: Type.Optional(Type.String({ description: "A sender, as the listing or the status line names it." })),
		}),
		execute: async (_id, { id, from }) => {
			const all = waiting(store).filter((m) => !m.ping);
			if (id === undefined && from === undefined) {
				const now = Date.now();
				return answer(all.map((m) => `${m.id}  ${m.from}  ${size(m.bytes)}  ${age(now - Date.parse(m.at))} old`).join("\n") || "The inbox is empty.");
			}
			const chosen = all.filter((m) => (id === undefined || m.id === id) && (from === undefined || m.from === from));
			if (!chosen.length) return answer(`No unread message ${[id && `with id ${id}`, from && `from ${from}`].filter(Boolean).join(" ")}; inbox lists what waits.`);
			await markRead(store, chosen);
			return { ...answer(chosen.map((m) => `${shown(m)} (sent ${m.at.slice(0, 16)}Z)`).join("\n\n")), details: WORK_RESULT };
		},
	}) as ToolDefinition;
}

/**
 * The session tools: each starts, messages, reads or delegates to a Claude Code session, never acting itself. Given
 * `work`, delegate can also run in the background, its answer arriving as a ping.
 */
export function sessionTools(config: SessionConfig, work?: Background): ToolDefinition[] {
	const session = Type.String({ description: "A session as look lists it: its tmux window (repo:window, or the window alone), its name, or its pid." });
	const dir = (what: string) => Type.String({ description: `${what}, absolute, under ~/, or relative to max's home.` });
	return [
		defineTool({
			name: "start_session",
			label: "Start session",
			description:
				"Start an orchestrator: interactive Claude Code in auto mode, in a new tmux window of the repo's tmux session, with the brief as its first prompt. Its reports and its turns ending wait in your inbox; it pings you when it needs max.",
			parameters: Type.Object({
				dir: dir("The repo's directory"),
				name: Type.String({ description: "The window's name: the ticket's slug, or a few words for the activity." }),
				brief: Type.String({ description: "The orchestrator's first prompt: what max wants done, in his words where you have them." }),
			}),
			execute: async (_id, params) => answer(await spawn(config, params)),
		}),
		defineTool({
			name: "tell_session",
			label: "Tell session",
			description: "Send a session a message. It arrives as a cross-session message from the hypervisor.",
			parameters: Type.Object({ session, message: Type.String({ description: "The message, as the session should read it." }) }),
			execute: async (_id, params) => answer(await tell(config, params)),
		}),
		defineTool({
			name: "look",
			label: "Look",
			description: "Without a session: every Claude Code session on this machine, with its state and tmux window. With one: its state and the end of its pane.",
			parameters: Type.Object({ session: Type.Optional(session) }),
			execute: async (_id, params) => answer(await look(config, params)),
		}),
		defineTool({
			name: "delegate",
			label: "Delegate",
			description:
				"Have a one-shot Claude Code session in auto mode do a task and answer: reading a ticket, a board or a session page, or any side effect. Its permission classifier judges what it does. Returns only its answer, within 45 minutes.",
			parameters: Type.Object({
				task: Type.String({ description: "What to do or find out, and what to answer with." }),
				dir: Type.Optional(dir("Where it runs, max's home if not given")),
				...(work
					? { background: Type.Optional(Type.Boolean({ description: "Return at once with an id, and end your turn: the answer arrives as a report starting [delegate <id>]." })) }
					: {}),
			}),
			execute: async (_id, { task: what, dir, background }, signal) => {
				const task = await delegation(config, { task: what, dir });
				if (!work || background !== true) return answer(await task(signal));
				const id = randomBytes(2).toString("hex");
				work.start(`delegate ${id}`, task);
				return answer(`Delegated as ${id}; its answer arrives as a report starting [delegate ${id}]. End your turn.`);
			},
		}),
	] as ToolDefinition[];
}
