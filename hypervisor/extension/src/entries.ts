import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { eventsIn } from "./events.ts";

/** What a run was: a turn of max's, or a step of explore mode. */
export type Kind = "turn" | "step";

/** One entry of a finished turn. A text an entry cannot hold carries `gist`: what a fork needs to write its gist. */
export interface Entry {
	text: string;
	gist?: Speech;
}

/** Who said a text, and how a fork's ask names it. */
export interface Speech {
	speaker: string;
	whose: string;
}

/** Bytes of text one entry holds, as the store's `--help` says. */
export const ENTRY = 512;

/**
 * A turn's messages as entries, in order: each message max sent, each event the harness handed over, each text of the
 * agent's, and each tool call with its result. A tool call's result is data the store clips to its head; what max, an
 * event and the agent said gets a gist.
 *
 * An explore step is a turn the harness started, so its message is not max's and is not logged; the step's last text
 * is its finding, and the texts before it are not logged either.
 */
export function entriesOf(messages: AgentMessage[], kind: Kind = "turn"): Entry[] {
	const step = kind === "step";
	const results = new Map(messages.flatMap((m) => (m.role === "toolResult" ? [[m.toolCallId, m] as const] : [])));
	const finding = step ? messages.findLast((m) => m.role === "assistant" && saidIn(m).trim()) : undefined;
	return messages.flatMap((message): Entry[] => {
		if (step && message.role === "user") return [];
		if (message.role === "user") {
			const words = textOf(message.content);
			const events = eventsIn(words);
			if (events) return events.map((event) => said("event", event, `the event that begins "${head(event.trim())}"`));
			return [said("max", words, `max's message that begins "${head(words.trim())}"`)];
		}
		if (message.role !== "assistant") return [];
		const words = saidIn(message);
		const calls = message.content.flatMap((part) => (part.type === "toolCall" ? [part] : []));
		const [voice, what] = step ? ["finding", "finding"] : ["me", "message"];
		const kept = words.trim() && (!step || message === finding);
		return [
			...(kept ? [said(voice, words, `your ${what} that begins "${head(words.trim())}"`)] : []),
			...calls.map((call) => {
				const result = results.get(call.id);
				const answer = result ? `${result.isError ? "error: " : ""}${textOf(result.content)}` : "(no result)";
				return { text: `${call.name} ${JSON.stringify(call.arguments)} → ${answer}` };
			}),
		];
	});
}

/** Whether an entry holds `text` as it is, as the store judges it: one line of at most `ENTRY` bytes, no space at its ends. */
export function fits(text: string): boolean {
	return text.length > 0 && text === text.trim() && !/[\n\r]/.test(text) && Buffer.byteLength(text) <= ENTRY;
}

/** The text an assistant message says, without its thinking and tool calls. */
export function saidIn(message: { content: readonly { type: string; text?: string }[] }): string {
	return textOf(message.content.filter((part) => part.type === "text"));
}

/** The first `n` characters of `text`, cut between code points so no half of a surrogate pair is left. */
export function head(text: string, n = 80): string {
	return Array.from(text).slice(0, n).join("");
}

/** A line as an entry logs it: after its speaker, as an entry that fits reads, once though the line already names it. */
export function spoken(speaker: string, line: string): string {
	const prefix = `${speaker}: `;
	return prefix + (line.toLowerCase().startsWith(prefix.toLowerCase()) ? line.slice(prefix.length) : line);
}

function said(speaker: string, words: string, whose: string): Entry {
	const text = spoken(speaker, words);
	return fits(text) ? { text } : { text, gist: { speaker, whose } };
}

function textOf(content: string | readonly { type: string; text?: string }[]): string {
	if (typeof content === "string") return content;
	return content.map((part) => (part.type === "text" ? (part.text ?? "") : `[${part.type}]`)).join("\n");
}
