import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { entriesOf, head, type Kind } from "./entries.ts";
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

/** A turn the log could not take, from the entry where it stopped. */
export interface LostRecord {
	at: string;
	error: string;
	entries: string[];
}

export interface Journal {
	fork(record: ForkRecord): Promise<void>;
	lost(record: LostRecord): Promise<void>;
}

/**
 * The log and the view across turns. A finished turn is logged once the turn before it is, and its due compressions
 * are then written, all of one round in parallel, one round after another across turns. The view waits for the turns
 * handed over to be logged, and for a compression only while the store refuses to render without it.
 */
export function memory(store: Store, journal: Journal) {
	let logged: Promise<void> = Promise.resolve();
	let written: Promise<void> = Promise.resolve();
	const progress = signal();
	/** Turns lost since the last view, which the next view says. */
	const lost: string[] = [];

	async function forked(kind: ForkRecord["kind"], of: string, finished: Finished, ask: string): Promise<string | undefined> {
		const calls: Call[] = [];
		const at = new Date().toISOString();
		try {
			const { line } = await fork(finished, ask, calls);
			await journal.fork({ at, kind, of, calls, line });
			return line;
		} catch (error) {
			await journal.fork({ at, kind, of, calls, error: String(error) });
			return undefined;
		}
	}

	async function log(messages: AgentMessage[], finished: Finished | undefined, kind: Kind) {
		const entries = entriesOf(messages, kind);
		const gists = await Promise.all(entries.map((e) => (e.whose && finished ? forked("gist", head(e.text), finished, gistAsk(e.whose)) : undefined)));
		for (const [i, entry] of entries.entries()) {
			try {
				await store.append(entry.text, gists[i]);
			} catch (error) {
				const at = new Date().toISOString();
				lost.push(`(not logged: the turn ending ${at.slice(0, 16)}, from its entry "${head(entry.text)}" on: ${error})`);
				await journal.lost({ at, error: String(error), entries: entries.slice(i).map((e) => e.text) });
				return;
			}
		}
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
		/** Logs a finished run's messages, a turn or an explore step, and writes the compressions that become due; returns at once. */
		finish(messages: AgentMessage[], finished: Finished | undefined, kind: Kind = "turn") {
			logged = logged.then(() => log(messages, finished, kind)).catch(() => {});
			written = Promise.all([written, logged])
				.then(() => compress(finished))
				.catch(() => {})
				.finally(() => progress.fire());
		},
		/**
		 * The view to wake to, its header last, after a line for each turn lost since the last view, which the budget
		 * does not count; the store's refusal in its place when what it needs cannot be written.
		 */
		async view(): Promise<string> {
			await logged;
			const notes = lost.splice(0);
			for (;;) {
				const waited = Promise.race([written.then(() => "done"), progress.next]);
				try {
					const [header, ...lines] = (await store.view()).trimEnd().split("\n");
					return [...lines, ...notes, header].join("\n");
				} catch (error) {
					if (!(error instanceof Refused)) {
						lost.unshift(...notes);
						throw error;
					}
					if ((await waited) === "done") return [`(no view: ${error.message})`, ...notes].join("\n");
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
