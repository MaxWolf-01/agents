import type { AgentMessage } from "@earendil-works/pi-agent-core";

/** One entry of a finished turn. A text an entry cannot hold names itself in `whose`, and a fork writes its gist. */
export interface Entry {
	text: string;
	whose?: string;
}

/** Bytes of text one entry holds, as the store's `--help` says. */
export const ENTRY = 512;

/**
 * A turn's messages as entries, in order: each message max sent, each text of the agent's, and each tool call with its
 * result. A tool call's result is data the store clips to its head; what max and the agent said gets a gist.
 */
export function entriesOf(messages: AgentMessage[]): Entry[] {
	const results = new Map(messages.flatMap((m) => (m.role === "toolResult" ? [[m.toolCallId, m] as const] : [])));
	return messages.flatMap((message): Entry[] => {
		if (message.role === "user") {
			const words = textOf(message.content);
			return [said(`max: ${words}`, `max's message that begins "${head(words.trim())}"`)];
		}
		if (message.role !== "assistant") return [];
		const words = saidIn(message);
		const calls = message.content.flatMap((part) => (part.type === "toolCall" ? [part] : []));
		return [
			...(words.trim() ? [said(`me: ${words}`, `your message that begins "${head(words.trim())}"`)] : []),
			...calls.map((call) => {
				const result = results.get(call.id);
				const answer = result ? `${result.isError ? "error: " : ""}${textOf(result.content)}` : "(no result)";
				return { text: `${call.name} ${JSON.stringify(call.arguments)} → ${answer}` };
			}),
		];
	});
}

/** Whether an entry holds `text` as it is, as the store judges it: one line of at most 512 bytes, no space at its ends. */
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

function said(text: string, whose: string): Entry {
	return fits(text) ? { text } : { text, whose };
}

function textOf(content: string | readonly { type: string; text?: string }[]): string {
	if (typeof content === "string") return content;
	return content.map((part) => (part.type === "text" ? (part.text ?? "") : `[${part.type}]`)).join("\n");
}
