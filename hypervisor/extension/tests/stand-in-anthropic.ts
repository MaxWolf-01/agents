import http from "node:http";
import type { AddressInfo } from "node:net";

/** A request the stand-in received, as its JSON body. */
export type Request = { system?: { text: string; cache_control?: unknown }[]; tools?: { name: string; cache_control?: unknown }[]; messages: { role: string; content: string | Block[] }[] };
type Block = { type: string; text?: string; cache_control?: unknown; tool_use_id?: string; content?: unknown };

/** One reply: text, or a tool call. */
export type Reply = { text: string } | { tool: string; input: object };

/** What every reply reports as its usage, so a check can find it again where the extension logs it. */
export const USAGE = { input_tokens: 17, output_tokens: 5, cache_read_input_tokens: 4321, cache_creation_input_tokens: 123 };

/**
 * The Anthropic messages endpoint, answering each request with what `answer` makes of it, as a stream of the events
 * the real one sends. Every request is kept in `requests`, in order.
 */
export async function standInAnthropic(answer: (request: Request) => Reply) {
	const requests: Request[] = [];
	const server = http.createServer((req, res) => {
		const chunks: Buffer[] = [];
		req.on("data", (chunk: Buffer) => chunks.push(chunk));
		req.on("end", () => {
			const request = JSON.parse(Buffer.concat(chunks).toString()) as Request;
			requests.push(request);
			res.writeHead(200, { "content-type": "text/event-stream" });
			for (const [event, data] of events(answer(request), requests.length)) res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
			res.end();
		});
	});
	await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
	return {
		url: `http://127.0.0.1:${(server.address() as AddressInfo).port}`,
		requests,
		close: () => new Promise<void>((resolve) => server.close(() => resolve())),
	};
}

function events(reply: Reply, n: number): [string, object][] {
	const block =
		"text" in reply
			? [{ type: "text", text: "" }, { type: "text_delta", text: reply.text }]
			: [{ type: "tool_use", id: `toolu_${n}`, name: reply.tool, input: {} }, { type: "input_json_delta", partial_json: JSON.stringify(reply.input) }];
	const { output_tokens, ...input } = USAGE;
	return [
		["message_start", { type: "message_start", message: { id: `msg_${n}`, type: "message", role: "assistant", model: "claude-opus-5-5", content: [], stop_reason: null, usage: { ...input, output_tokens: 1 } } }],
		["content_block_start", { type: "content_block_start", index: 0, content_block: block[0] }],
		["content_block_delta", { type: "content_block_delta", index: 0, delta: block[1] }],
		["content_block_stop", { type: "content_block_stop", index: 0 }],
		["message_delta", { type: "message_delta", delta: { stop_reason: "text" in reply ? "end_turn" : "tool_use" }, usage: { output_tokens } }],
		["message_stop", { type: "message_stop" }],
	];
}

/** Every text of a message, and tool results' unless `results` is false. */
export function textOf(message: Request["messages"][number], results = true): string {
	if (typeof message.content === "string") return message.content;
	const blocks = message.content.filter((b) => results || b.type !== "tool_result");
	return blocks.map((b) => b.text ?? JSON.stringify(b.content ?? "")).join("\n");
}
