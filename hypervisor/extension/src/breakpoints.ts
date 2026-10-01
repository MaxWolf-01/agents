import { VIEW_OPEN } from "./swap.ts";

type Block = { type: string; text?: string; cache_control?: unknown };
type Message = { role: string; content: string | Block[] };
type Payload = { system?: string | Block[]; tools?: Block[]; messages?: Message[] };

/** Anthropic reads at most four cache breakpoints in one request. */
const MOST = 4;

/**
 * A request as the Anthropic provider sends it, with cache breakpoints moved into the view, or nothing for a payload of
 * another shape. pi puts one on each system block, the last tool and the last message. The cache reads tools, then
 * system, then messages, so the last system block's breakpoint covers the tools and the blocks before it; those
 * breakpoints go, and the view gets them, where its lines change least from one turn to the next (`stableEnds`).
 */
export function placeBreakpoints(payload: unknown): unknown {
	if (!isPayload(payload)) return undefined;
	const mark = [...(Array.isArray(payload.system) ? payload.system : []), ...(payload.tools ?? [])].find((b) => b.cache_control)?.cache_control;
	const system = Array.isArray(payload.system) ? payload.system.map((b, i, all) => (i === all.length - 1 ? b : bare(b))) : payload.system;
	const out: Payload = { ...payload, ...(system === undefined ? {} : { system }), ...(payload.tools ? { tools: payload.tools.map(bare) } : {}) };
	const at = (payload.messages ?? []).findIndex(isView);
	if (!mark || at < 0) return out;
	const spare = MOST - count(out);
	const messages = [...(payload.messages ?? [])];
	const [first, ...rest] = messages[at].content as Block[];
	messages[at] = { ...messages[at], content: [...split(first.text ?? "", spare, mark), ...rest] };
	return { ...out, messages };
}

/**
 * Where the view's lines are likeliest to match the next turn's: after the last line of a block of at least 128
 * entries, and of at least 32. A view of single entries only grows at its end, so all of it holds. Past the budget,
 * the cover is recomputed for every log length, so much of the view moves from one turn to the next wherever it is split.
 */
export function stableEnds(lines: string[]): number[] {
	const sizes = lines.map((line) => {
		const block = /^\S+ #(\d+)-(\d+) /.exec(line);
		return block ? Number(block[2]) - Number(block[1]) + 1 : /^\S+ #\d+ /.test(line) ? 1 : 0;
	});
	const after = (size: number) => sizes.findLastIndex((s) => s >= size) + 1;
	const ends = sizes.some((s) => s > 1) ? [after(128), after(32)] : [after(1)];
	return [...new Set(ends)].filter((end) => end > 0).sort((a, b) => a - b);
}

/** The view's text in blocks, each of the first `spare` ends of `stableEnds` closing one with a breakpoint. */
function split(text: string, spare: number, mark: unknown): Block[] {
	const lines = text.slice(VIEW_OPEN.length).split("\n");
	const ends = stableEnds(lines).slice(0, Math.max(0, spare));
	const blocks: Block[] = [];
	let from = 0;
	for (const end of ends) {
		const to = VIEW_OPEN.length + lines.slice(0, end).join("\n").length + 1;
		blocks.push({ type: "text", text: text.slice(from, to), cache_control: mark });
		from = to;
	}
	if (from < text.length) blocks.push({ type: "text", text: text.slice(from) });
	return blocks;
}

function isPayload(payload: unknown): payload is Payload {
	if (typeof payload !== "object" || payload === null) return false;
	const { system, tools, messages } = payload as Payload;
	const blocks = (list: unknown) => Array.isArray(list) && list.every((b) => typeof b === "object" && b !== null);
	return (system === undefined || typeof system === "string" || blocks(system)) && (tools === undefined || blocks(tools)) && (messages === undefined || blocks(messages));
}

function isView(message: Message): boolean {
	const first = Array.isArray(message.content) ? message.content[0] : undefined;
	return message.role === "user" && first?.type === "text" && typeof first.text === "string" && first.text.startsWith(VIEW_OPEN);
}

function bare<T extends object>(block: T): T {
	const { cache_control: _, ...rest } = block as T & { cache_control?: unknown };
	return rest as T;
}

function count(payload: Payload): number {
	const blocks = [...(Array.isArray(payload.system) ? payload.system : []), ...(payload.tools ?? []), ...(payload.messages ?? []).flatMap((m) => (Array.isArray(m.content) ? m.content : []))];
	return blocks.filter((b) => b?.cache_control).length;
}
