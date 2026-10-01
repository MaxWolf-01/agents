import type { Api, AssistantMessage, Model, Usage } from "@earendil-works/pi-ai";
import type { ModelRegistry } from "@earendil-works/pi-coding-agent";
import { ENTRY, saidIn } from "./entries.ts";

/** How long one call of a fork may take before it counts as failed. */
const PATIENCE = 5 * 60_000;

/** A finished turn as a fork continues it: the last request the turn sent, its answer to that, and what sends another. */
export interface Finished {
	payload: Payload;
	/** The text of the reply to `payload`, when the turn ended on one. */
	answer?: string;
	model: Model<Api>;
	models: Pick<ModelRegistry, "complete">;
	sessionId?: string;
}

type Block = { type: string; text?: string };
type Payload = { messages: { role: string; content: string | Block[] }[] };

/** What one model call of a fork cost, as the provider reported it. */
export interface Call {
	ms: number;
	usage: Pick<Usage, "input" | "output" | "cacheRead" | "cacheWrite">;
}

export function compressionAsk(block: string, body: string): string {
	return `Write the compression of entries #${block} of your log, shown below: one line of at most ${ENTRY} bytes, which stands in for them in your view from now on. Keep what has lasting effect: what was asked, decided, built, abandoned or changed direction, and the pointers (tickets, sessions, paths, entry numbers) that lead back to the detail. Drop what does not. Invent nothing. You see your whole view, so leave out what it already says. Write the content itself: no preamble such as "this block covers", and no leading date, since the view line carries its time. Reply with the line alone, and call no tool.\n\n${body}`;
}

export function gistAsk(whose: string): string {
	return `${whose[0].toUpperCase()}${whose.slice(1)} is too long for one entry of your log. Write its gist: one line of at most ${ENTRY} bytes, logged in its place, while raw keeps the whole text. Keep what a later turn needs to know what was said and to find it again. Write the content itself: no preamble, and no leading date. Reply with the line alone, and call no tool.`;
}

/**
 * The line a fork of the finished turn writes for `ask`. The fork sends the turn's last request as it went, then the
 * turn's answer and the ask, so everything before them is read from the cache that request wrote. A reply that is no
 * line of at most 512 bytes is asked for again once; `calls` holds every call, the failed ones too.
 */
export async function fork(finished: Finished, ask: string, calls: Call[] = []): Promise<{ line: string; calls: Call[] }> {
	for (const attempt of [ask, `${ask}\n\nYour last reply was not one line of at most ${ENTRY} bytes. Reply with that line alone.`]) {
		const started = Date.now();
		const reply: AssistantMessage = await finished.models.complete(finished.model, { messages: [] }, {
			onPayload: () => withAsk(finished, attempt),
			signal: AbortSignal.timeout(PATIENCE),
			...(finished.sessionId ? { sessionId: finished.sessionId } : {}),
		});
		const { input, output, cacheRead, cacheWrite } = reply.usage;
		calls.push({ ms: Date.now() - started, usage: { input, output, cacheRead, cacheWrite } });
		if (reply.stopReason === "error" || reply.stopReason === "aborted") throw new Error(reply.errorMessage ?? `the fork's call ended: ${reply.stopReason}`);
		const line = saidIn(reply).split(/\s+/).join(" ").trim();
		if (line && Buffer.byteLength(line) <= ENTRY) return { line, calls };
	}
	throw new Error(`no line of at most ${ENTRY} bytes in two replies`);
}

/** The request followed by the answer and `ask`, or, for a turn that ended on no answer, with `ask` its last text. */
function withAsk({ payload, answer }: Finished, ask: string): Payload {
	const messages = [...payload.messages];
	const last = messages.at(-1);
	const text = { type: "text", text: ask };
	if (answer) messages.push({ role: "assistant", content: [{ type: "text", text: answer }] }, { role: "user", content: [text] });
	else if (last?.role === "user") messages[messages.length - 1] = { ...last, content: [...(typeof last.content === "string" ? [{ type: "text", text: last.content }] : last.content), text] };
	else messages.push({ role: "user", content: [text] });
	return { ...payload, messages };
}
