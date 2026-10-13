import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

/** A message for the hypervisor: what `hv tell` left, or a spawned session's turn ending, which the watch leaves. */
export interface Told {
	at: string;
	/** Where it came from: its tmux window as `session:window`, or its directory. */
	from: string;
	text: string;
	/** Starts a turn at once, where any other message waits in the inbox until the hypervisor reads it. */
	ping?: boolean;
}

/** A message in the inbox, with the short id the inbox tool knows it by and its size in bytes. */
export interface Waiting extends Told {
	id: string;
	bytes: number;
	file: string;
}

/** The store's inbox: a file per message, named so that names sort oldest first. Its `read/` keeps every message read. */
const INBOX = "inbox";
const READ = "read";

/** Leaves `told` in the store's inbox. The file appears whole, so a reader never sees half of it. */
export async function post(store: string, told: Told): Promise<void> {
	const dir = path.join(store, INBOX);
	await mkdir(dir, { recursive: true });
	// Within a millisecond, the process's own clock keeps its messages in the order it posted them.
	const name = `${Date.now().toString().padStart(15, "0")}-${process.hrtime.bigint().toString().padStart(20, "0")}-${process.pid}`;
	await writeFile(path.join(dir, `.${name}`), JSON.stringify(told));
	await rename(path.join(dir, `.${name}`), path.join(dir, `${name}.json`));
}

/**
 * Every message in the store's inbox, oldest first; a file that does not parse is left out. Synchronous, since pi asks
 * for the status line while it builds a request.
 */
export function waiting(store: string): Waiting[] {
	const dir = path.join(store, INBOX);
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
		return told ? [{ ...told, id: createHash("sha256").update(name).digest("hex").slice(0, 6), bytes: Buffer.byteLength(told.text), file }] : [];
	});
}

/** Moves `messages` into the inbox's `read/`, out of what waits. */
export async function markRead(store: string, messages: Waiting[]): Promise<void> {
	const dir = path.join(store, INBOX, READ);
	await mkdir(dir, { recursive: true });
	await Promise.all(messages.map((m) => rename(m.file, path.join(dir, path.basename(m.file)))));
}

/** A message as the hypervisor reads it, and as memory keeps it: `[from] time text`. */
export function shown(told: Told): string {
	return `[${told.from}] ${told.at.slice(0, 16)} ${told.text}`;
}

/** The line that ends each turn's request while messages wait: per sender, how many, how many bytes, how old. Never their text. */
export function unreadLine(unread: Told[], now: number): string | undefined {
	if (!unread.length) return undefined;
	const senders = Map.groupBy(unread, (m) => m.from);
	const listed = [...senders].map(([from, messages]) => {
		const bytes = messages.reduce((sum, m) => sum + Buffer.byteLength(m.text), 0);
		const ages = [messages[0], messages.at(-1)!].map((m) => age(now - Date.parse(m.at)));
		const span = ages[0] === ages[1] ? ages[0] : `${ages[0]} to ${ages[1]}`;
		return `${from} ${messages.length} ${messages.length === 1 ? "message" : "messages"}, ${size(bytes)}, ${span} old`;
	});
	return `[Hypervisor inbox] Unread: ${listed.join("; ")}.`;
}

/** A span of `ms` as the inbox shows an age: in minutes, in hours below two days, else in days. */
export function age(ms: number): string {
	const minutes = Math.max(0, Math.floor(ms / 60_000));
	if (minutes < 60) return `${minutes}m`;
	if (minutes < 48 * 60) return `${Math.floor(minutes / 60)}h`;
	return `${Math.floor(minutes / (24 * 60))}d`;
}

function size(bytes: number): string {
	return bytes < 1000 ? `${bytes} B` : `${(bytes / 1000).toFixed(1)} kB`;
}

function parsed(text: string): Told | undefined {
	try {
		const told = JSON.parse(text);
		if (typeof told.text !== "string") return undefined;
		return { at: String(told.at), from: String(told.from), text: told.text, ...(told.ping === true ? { ping: true } : {}) };
	} catch {
		return undefined;
	}
}
