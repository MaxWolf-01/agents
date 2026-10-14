import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

/** A message for the hypervisor: what `hv tell`, background work or an explore offer left. */
export interface Told {
	at: string;
	/** Where it came from: its tmux window as `session:window`, its directory, or the work that sent it. */
	from: string;
	text: string;
	/** Starts a turn at once, where any other message waits in the inbox until the hypervisor reads it. */
	ping?: boolean;
	/** How it was sent, when that is worth saying: `hv tell`. */
	via?: string;
}

/**
 * The store's inbox. A plain message waits until the hypervisor reads it; a ping waits only for the watch to take it
 * and start a turn. Either way it is handled once: it then moves to the inbox's `read/`, which keeps every message.
 */
export interface Inbox {
	/** Leaves `told` in the inbox. The file appears whole, so a reader never sees half of it. */
	post(told: Told): Promise<void>;
	/** A line for each plain message that waits, oldest first: id, sender, size and age at `now`. Never its text. */
	list(now?: number): string[];
	/** The plain messages with id `id` and from `from`, each as the hypervisor reads it, and out of what waits. */
	read(which: { id?: string; from?: string }): Promise<string[]>;
	/**
	 * Hands every waiting ping to `deliver`, as the hypervisor gets them, and moves them to `read/` unless it returns
	 * `false`, which leaves them for the next take. While one take runs, another takes nothing.
	 */
	takePings(deliver: (pings: string[]) => boolean | void): Promise<void>;
	/** While plain messages wait: per sender, how many, how many bytes, how old at `now`. Never their text. */
	statusLine(now?: number): string | undefined;
}

/** The inbox of `store`. Synchronous where it lists, since pi asks for the status line while it builds a request. */
export function inbox(store: string): Inbox {
	const dir = path.join(store, "inbox");
	const readDir = path.join(dir, "read");
	const plain = () => waiting(dir).filter((m) => !m.ping);
	const markRead = async (messages: Waiting[]) => {
		await mkdir(readDir, { recursive: true });
		await Promise.all(messages.map((m) => rename(m.file, path.join(readDir, path.basename(m.file)))));
	};
	let taking = false;
	return {
		async post(told) {
			await mkdir(dir, { recursive: true });
			// Within a millisecond, the process's own clock keeps its messages in the order it posted them.
			const name = `${Date.now().toString().padStart(15, "0")}-${process.hrtime.bigint().toString().padStart(20, "0")}-${process.pid}`;
			await writeFile(path.join(dir, `.${name}`), JSON.stringify(told));
			await rename(path.join(dir, `.${name}`), path.join(dir, `${name}.json`));
		},
		list(now = Date.now()) {
			return plain().map((m) => `${m.id}  ${m.from}  ${size(Buffer.byteLength(m.text))}  ${age(now - Date.parse(m.at))} old`);
		},
		async read({ id, from }) {
			const chosen = plain().filter((m) => (id === undefined || m.id === id) && (from === undefined || m.from === from));
			await markRead(chosen);
			return chosen.map((m) => `${shown(m)} (sent ${m.at.slice(0, 16)}Z)`);
		},
		async takePings(deliver) {
			if (taking) return;
			taking = true;
			try {
				const pings = waiting(dir).filter((m) => m.ping);
				if (!pings.length) return;
				// read/ exists before a delivery, so a delivered ping cannot stay behind to be delivered again.
				await mkdir(readDir, { recursive: true });
				if (deliver(pings.map(shown)) === false) return;
				await markRead(pings);
			} finally {
				taking = false;
			}
		},
		statusLine(now = Date.now()) {
			const unread = plain();
			if (!unread.length) return undefined;
			const listed = [...Map.groupBy(unread, (m) => m.from)].map(([from, messages]) => {
				const bytes = messages.reduce((sum, m) => sum + Buffer.byteLength(m.text), 0);
				const ages = [messages[0], messages.at(-1)!].map((m) => age(now - Date.parse(m.at)));
				const span = ages[0] === ages[1] ? ages[0] : `${ages[0]} to ${ages[1]}`;
				return `${from} ${messages.length} ${messages.length === 1 ? "message" : "messages"}, ${size(bytes)}, ${span} old`;
			});
			return `Unread in your inbox: ${listed.join("; ")}.`;
		},
	};
}

/** A message in the inbox, with the short id the inbox tool knows it by. */
interface Waiting extends Told {
	id: string;
	file: string;
}

/** Every message in the inbox directory `dir`, oldest first, since names sort so; a file that does not parse is left out. */
function waiting(dir: string): Waiting[] {
	let names: string[];
	try {
		names = readdirSync(dir).filter((name) => name.endsWith(".json")).sort();
	} catch {
		return [];
	}
	return names.flatMap((name) => {
		const file = path.join(dir, name);
		let text: string;
		try {
			text = readFileSync(file, "utf8");
		} catch {
			return [];
		}
		const told = parsed(text);
		return told ? [{ ...told, id: createHash("sha256").update(name).digest("hex").slice(0, 6), file }] : [];
	});
}

/** A message as the hypervisor gets it, and as memory keeps it: `[from] text`, or `[from] hv tell: text`. */
function shown(told: Told): string {
	return `[${told.from}] ${told.via ? `${told.via}: ` : ""}${told.text}`;
}

/** A span of `ms` as the inbox shows an age: in minutes, in hours below two days, else in days. */
function age(ms: number): string {
	const minutes = Math.max(0, Math.floor(ms / 60_000));
	if (minutes < 60) return `${minutes}m`;
	if (minutes < 48 * 60) return `${Math.floor(minutes / 60)}h`;
	return `${Math.floor(minutes / (24 * 60))}d`;
}

/** A size as the inbox shows it. */
function size(bytes: number): string {
	return bytes < 1000 ? `${bytes} B` : `${(bytes / 1000).toFixed(1)} kB`;
}

function parsed(text: string): Told | undefined {
	try {
		const told = JSON.parse(text);
		if (typeof told.text !== "string") return undefined;
		return { at: String(told.at), from: String(told.from), text: told.text, ...(told.ping === true ? { ping: true } : {}), ...(typeof told.via === "string" ? { via: told.via } : {}) };
	} catch {
		return undefined;
	}
}
