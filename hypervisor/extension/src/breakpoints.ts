import { VIEW_OPEN } from "./swap.ts";

type Block = { type: string; text?: string; cache_control?: { ttl?: string } };
type Message = { role: string; content: string | Block[] };
type Payload = { system?: string | Block[]; tools?: Block[]; messages?: Message[] };

/** Anthropic reads at most four cache breakpoints in one request. */
const MOST = 4;
/** How many entries ahead the view's breakpoints are placed for; a turn logs about this many or fewer. */
export const AHEAD = 16;
/** How long a cache entry lives after the request that wrote or read it, by the breakpoint's `ttl`. */
const LIFETIME: Record<string, number> = { "5m": 5 * 60_000, "1h": 60 * 60_000 };
const VIEW_LINE = /^\S+ #\d+(?:-\d+)? /;

/** The view's first lines, as a request sent them closed by a breakpoint, and when the entry that wrote expires. */
export interface Written {
	lines: string[];
	expires: number;
}

/**
 * A request as the Anthropic provider sends it, with cache breakpoints moved into the view, or nothing for a payload of
 * another shape. pi puts one on each system block, the last tool and the last message. The cache reads tools, then
 * system, then messages, so the last system block's breakpoint covers the tools and the blocks before it; those
 * breakpoints go, and the view gets as many of them as are left, after its first `ends` lines in the order given
 * (`viewEnds`). The view is sent as a text block
 * per line: the cache finds an entry an earlier request wrote only where this request has a block boundary at the
 * same point, and looks for one up to 20 blocks back from each breakpoint.
 */
export function placeBreakpoints(payload: unknown, ends: number[] = []): unknown {
	if (!isPayload(payload)) return undefined;
	const mark = [...(Array.isArray(payload.system) ? payload.system : []), ...(payload.tools ?? [])].find((b) => b.cache_control)?.cache_control;
	const system = Array.isArray(payload.system) ? payload.system.map((b, i, all) => (i === all.length - 1 ? b : bare(b))) : payload.system;
	const out: Payload = { ...payload, ...(system === undefined ? {} : { system }), ...(payload.tools ? { tools: payload.tools.map(bare) } : {}) };
	const at = (payload.messages ?? []).findIndex(isView);
	if (!mark || at < 0) return out;
	const closed = new Set(ends.slice(0, MOST - count(out)));
	const messages = [...(payload.messages ?? [])];
	const [first, ...rest] = messages[at].content as Block[];
	const lines = perLine(first.text ?? "").map((text, i): Block => ({ type: "text", text, ...(closed.has(i + 1) ? { cache_control: mark } : {}) }));
	messages[at] = { ...messages[at], content: [...lines, ...rest] };
	return { ...out, messages };
}

/**
 * After how many of the view's lines to place its breakpoints, the one that matters most first, since a request has
 * room for only as many as pi leaves. The first goes where an entry an earlier request wrote still matches, the
 * longest such prefix, so this request reads it. The rest go where the next turn's view is likeliest to start with
 * the same lines: `stays[k - 1]` is how many lines it starts with after k more entries (the store's `stays`), and
 * each end chosen adds the most bytes kept over those k. Only the view's own lines count: a note or the header after
 * them changes every turn.
 */
export function viewEnds(lines: string[], stays: number[], written: Written[], now: number): number[] {
	const shown = lines.findIndex((line) => !VIEW_LINE.test(line));
	const view = shown < 0 ? lines.length : shown;
	const bytes = [0];
	for (const line of lines.slice(0, view)) bytes.push(bytes.at(-1)! + Buffer.byteLength(line) + 1);
	const matching = written.filter((w) => w.expires > now && w.lines.length <= view && w.lines.every((line, i) => line === lines[i]));
	const read = Math.max(0, ...matching.map((w) => w.lines.length));
	const kept = (ends: number[]) => stays.reduce((sum, stay) => sum + bytes[Math.max(0, ...ends.filter((end) => end <= stay))], 0);
	const ends = read ? [read] : [];
	const candidates = [...new Set(stays)].filter((stay) => stay > 0 && stay <= view);
	while (ends.length < MOST) {
		const best = candidates.reduce<number | undefined>((top, c) => (top === undefined || kept([...ends, c]) > kept([...ends, top]) ? c : top), undefined);
		if (best === undefined || kept([...ends, best]) <= kept(ends)) break;
		ends.push(best);
	}
	return ends;
}

/** `written` with the entries a request sent wrote or read in the view, each living as long as its breakpoint says. */
export function remember(written: Written[], payload: unknown, now: number): Written[] {
	const view = isPayload(payload) ? payload.messages?.find(isView) : undefined;
	if (!view) return written;
	const sent: Written[] = [];
	let text = "";
	for (const block of view.content as Block[]) {
		text += block.text ?? "";
		if (block.cache_control) sent.push({ lines: text.slice(VIEW_OPEN.length).replace(/\n$/, "").split("\n"), expires: now + (LIFETIME[block.cache_control.ttl ?? "5m"] ?? LIFETIME["5m"]) });
	}
	const same = (a: Written, b: Written) => a.lines.length === b.lines.length && a.lines.every((line, i) => line === b.lines[i]);
	return [...written.filter((w) => w.expires > now && !sent.some((s) => same(s, w))), ...sent];
}

/** The view's text as a block per line, the tag that opens it in the first and the one that closes it on its own. */
function perLine(text: string): string[] {
	const [open, ...rest] = text.split(/(?<=\n)/);
	return rest.length ? [open + rest[0], ...rest.slice(1)] : [open];
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
