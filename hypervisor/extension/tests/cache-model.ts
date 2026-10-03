/**
 * The prompt cache as Anthropic's prompt-caching docs describe it: a breakpoint writes an entry for the prefix it
 * closes, and a read checks the breakpoint and up to 19 blocks before it for an entry an earlier request wrote. For
 * each request in order, its blocks flattened (tools, system, then messages), the index of the last block read from
 * cache, or -1. Entries never expire: the requests follow each other within the cache's lifetime.
 */
export function cacheReads(requests: { text?: string; cache_control?: unknown }[][]): number[] {
	const cache = new Set<string>();
	return requests.map((blocks) => {
		const prefixes = blocks.map((_, i) => JSON.stringify(blocks.slice(0, i + 1).map((b) => b.text ?? "")));
		const marked = blocks.flatMap((b, i) => (b.cache_control ? [i] : []));
		let read = -1;
		for (const at of marked) {
			for (let i = at; i > at - 20 && i >= 0; i--) {
				if (cache.has(prefixes[i])) {
					read = Math.max(read, i);
					break;
				}
			}
		}
		for (const at of marked) cache.add(prefixes[at]);
		return read;
	});
}
