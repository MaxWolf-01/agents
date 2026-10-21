import { randomBytes } from "node:crypto";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ToolDefinition } from "@earendil-works/pi-coding-agent";
import type { Inbox } from "./inbox.ts";
import { type JarvisConfig, tellJarvis } from "./jarvis.ts";
import { DELEGATE_MINUTES, delegation, look, type SessionConfig, spawn, tell } from "./sessions.ts";
import type { Background } from "./pace.ts";

/** A tool's answer: the text it printed, or `(nothing)`. */
export const answer = (text: string) => ({ content: [{ type: "text" as const, text: text.trimEnd() || "(nothing)" }], details: undefined });

/** The details that have pi-optchat log a tool's result as `work` in memory, not as its echo (pi-optchat's `WORK_RESULT`). */
const WORK_RESULT = { optchat: "work" };

/** The inbox tool: the plain messages that wait in `inbox`, listed without their text, or read and so out of it. */
export function inboxTool(inbox: Inbox): ToolDefinition {
	return defineTool({
		name: "inbox",
		label: "Inbox",
		description:
			"Your inbox: the messages orchestrators left you with hv tell, and Jarvis's, which wait for you. Without arguments, list them: id, sender, size and age. With an id, read that message; with a sender, read every message from it. A message you read leaves the inbox and stays in your memory.",
		parameters: Type.Object({
			id: Type.Optional(Type.String({ description: "A message's id, as the listing gives it." })),
			from: Type.Optional(Type.String({ description: "A sender, as the listing or the status line names it." })),
		}),
		execute: async (_id, { id, from }) => {
			if (id === undefined && from === undefined) return answer(inbox.list().join("\n") || "The inbox is empty.");
			const read = await inbox.read({ id, from });
			if (!read.length) return answer(`No unread message ${[id && `with id ${id}`, from && `from ${from}`].filter(Boolean).join(" ")}; inbox lists what waits.`);
			return { ...answer(read.join("\n\n")), details: WORK_RESULT };
		},
	}) as ToolDefinition;
}

/** The tell_jarvis tool: leaves Jarvis a message in its inbox, through the mailbox key `config` names. */
export function jarvisTool(config: JarvisConfig): ToolDefinition {
	return defineTool({
		name: "tell_jarvis",
		label: "Tell Jarvis",
		description:
			"Leave Jarvis, max's life assistant on his VPS, a message. It waits in Jarvis's inbox until Jarvis's next wake. What Jarvis sends you waits in your inbox, from jarvis.",
		parameters: Type.Object({ message: Type.String({ description: "The message, as Jarvis reads it." }) }),
		execute: async (_id, { message }) => answer(await tellJarvis(config, message)),
	}) as ToolDefinition;
}

/**
 * The session tools: each starts, messages, reads or delegates to a Claude Code session, never acting itself. delegate can
 * also run in the background on `work`, its answer arriving as a ping.
 */
export function sessionTools(config: SessionConfig, work: Background): ToolDefinition[] {
	const session = Type.String({ description: "A session as look lists it: its tmux window (repo:window, or the window alone), its name, or its pid." });
	const dir = (what: string) => Type.String({ description: `${what}, absolute, under ~/, or relative to max's home.` });
	return [
		defineTool({
			name: "start_session",
			label: "Start session",
			description:
				"Start an orchestrator: interactive Claude Code in auto mode, in a new tmux window of the repo's tmux session, with the prompt as its first message. Its reports wait in your inbox; it pings you when it needs max. look shows what it is doing.",
			parameters: Type.Object({
				dir: dir("The repo's directory"),
				name: Type.String({ description: "The window's name: the ticket's slug, or a few words for the activity." }),
				prompt: Type.String({ description: "The orchestrator's first prompt: what max wants done, in his words where you have them." }),
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
				`Have a one-shot Claude Code session in auto mode do a task and answer: reading a ticket, a board or a session page, or any side effect. Its permission classifier judges what it does. Returns only its answer, within ${DELEGATE_MINUTES} minutes.`,
			parameters: Type.Object({
				task: Type.String({ description: "What to do or find out, and what to answer with." }),
				dir: Type.Optional(dir("Where it runs, max's home if not given")),
				background: Type.Optional(Type.Boolean({ description: "Return at once with an id, and end your turn: the answer arrives as a report starting [delegate <id>]." })),
			}),
			execute: async (_id, { task: what, dir, background }, signal) => {
				const task = await delegation(config, { task: what, dir });
				if (background !== true) return answer(await task(signal));
				const id = randomBytes(2).toString("hex");
				work.start(`delegate ${id}`, task);
				return answer(`Delegated as ${id}; its answer arrives as a report starting [delegate ${id}]. End your turn.`);
			},
		}),
	] as ToolDefinition[];
}
