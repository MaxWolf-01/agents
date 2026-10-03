import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ToolDefinition } from "@earendil-works/pi-coding-agent";
import { delegate, look, type SessionConfig, spawn, tell } from "./sessions.ts";
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

/** The session tools: each starts, messages, reads or delegates to a Claude Code session, never acting itself. */
export function sessionTools(config: SessionConfig): ToolDefinition[] {
	const session = Type.String({ description: "A session as look lists it: its tmux window (repo:window, or the window alone), its name, or its pid." });
	const dir = (what: string) => Type.String({ description: `${what}, absolute, under ~/, or relative to max's home.` });
	return [
		defineTool({
			name: "spawn",
			label: "Spawn",
			description:
				"Start an orchestrator: interactive Claude Code in auto mode, in a new tmux window of the repo's tmux session, with the brief as its first prompt. It reports back with hv tell, and you hear when its turn ends.",
			parameters: Type.Object({
				dir: dir("The repo's directory"),
				name: Type.String({ description: "The window's name: the ticket's slug, or a few words for the activity." }),
				brief: Type.String({ description: "The orchestrator's first prompt: what max wants done, in his words where you have them." }),
			}),
			execute: async (_id, params) => answer(await spawn(config, params)),
		}),
		defineTool({
			name: "tell",
			label: "Tell",
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
				"Have a one-shot Claude Code session in auto mode do a task and answer: reading a ticket, a board or a session page, or any side effect. Its permission classifier judges what it does. Returns only its answer.",
			parameters: Type.Object({
				task: Type.String({ description: "What to do or find out, and what to answer with." }),
				dir: Type.Optional(dir("Where it runs, max's home if not given")),
			}),
			execute: async (_id, params, signal) => answer(await delegate(config, params, signal)),
		}),
	] as ToolDefinition[];
}
