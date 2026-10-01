import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { entriesOf } from "./entries.ts";
import { type Call, compressionAsk, type Finished, fork, gistAsk } from "./forks.ts";
import { Refused, type Store } from "./store.ts";

/** What a fork did, as a line of the fork log. */
export interface ForkRecord {
	at: string;
	kind: "gist" | "compression";
	/** The entry's text head for a gist, LO-HI for a compression. */
	of: string;
	calls: Call[];
	line?: string;
	error?: string;
}

/**
 * The log and the view across turns. A finished turn is logged, then its due compressions are written, all of one
 * round in parallel; turns are taken one after another. The view waits for the turn before it to be logged, and for
 * a compression only while the store refuses to render without it.
 */
export function memory(store: Store, record: (fork: ForkRecord) => Promise<void>) {
	let logged: Promise<void> = Promise.resolve();
	let written: Promise<void> = Promise.resolve();
	const progress = signal();

	async function forked(kind: ForkRecord["kind"], of: string, finished: Finished, ask: string): Promise<string | undefined> {
		const calls: Call[] = [];
		const at = new Date().toISOString();
		try {
			const { line } = await fork(finished, ask, calls);
			await record({ at, kind, of, calls, line });
			return line;
		} catch (error) {
			await record({ at, kind, of, calls, error: String(error) });
			return undefined;
		}
	}

	async function log(messages: AgentMessage[], finished: Finished | undefined) {
		const entries = entriesOf(messages);
		const gists = await Promise.all(entries.map((e) => (e.whose && finished ? forked("gist", e.text.slice(0, 80), finished, gistAsk(e.whose)) : undefined)));
		for (const [i, entry] of entries.entries()) await store.append(entry.text, gists[i]);
	}

	/** Every compression `due` lists, round after round, until none is due or a round writes none. */
	async function compress(finished: Finished | undefined) {
		if (!finished) return;
		for (let blocks = await store.due(); blocks.length; blocks = await store.due()) {
			const done = await Promise.all(
				blocks.map(async (block) => {
					const line = await forked("compression", block, finished, compressionAsk(block, await store.body(block)));
					if (line === undefined) return false;
					await store.compress(block, line);
					progress.fire();
					return true;
				}),
			);
			if (!done.some(Boolean)) return;
		}
	}

	return {
		/** Logs a finished run's messages and writes the compressions that become due; returns at once. */
		finish(messages: AgentMessage[], finished: Finished | undefined) {
			logged = written.then(() => log(messages, finished));
			written = logged.then(() => compress(finished)).catch(() => {}).finally(() => progress.fire());
			logged = logged.catch(() => {});
		},
		/** The view to wake to, its header last; the store's refusal in its place when what it needs cannot be written. */
		async view(): Promise<string> {
			await logged;
			for (;;) {
				const waited = Promise.race([written.then(() => "done"), progress.next]);
				try {
					const [header, ...lines] = (await store.view()).trimEnd().split("\n");
					return [...lines, header].join("\n");
				} catch (error) {
					if (!(error instanceof Refused)) throw error;
					if ((await waited) === "done") return `(no view: ${error.message})`;
				}
			}
		},
		/** Resolves once every turn handed over is logged and compressed as far as it can be. */
		settled: () => written,
	};
}

/** A promise that resolves at the next `fire`, renewed by each. */
function signal() {
	let resolve!: (said: string) => void;
	const renew = () => new Promise<string>((r) => (resolve = r));
	const box = { next: renew(), fire: () => {} };
	box.fire = () => {
		const done = resolve;
		box.next = renew();
		done("progress");
	};
	return box;
}
