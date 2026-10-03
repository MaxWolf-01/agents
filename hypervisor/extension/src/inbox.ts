import { mkdir, readdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";

/** A message an orchestrator left for the hypervisor with `hv tell`. */
export interface Told {
	at: string;
	/** Where it came from: its tmux window as `session:window`, or its directory. */
	from: string;
	text: string;
}

/** The store's inbox: a file per message, named so that names sort oldest first. */
const INBOX = "inbox";

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
 * Hands every message in the store's inbox to `use`, oldest first, and removes them once it has taken them. A file
 * that does not parse is removed with them; when `use` throws, every message stays for the next take.
 */
export async function take(store: string, use: (told: Told[]) => void): Promise<void> {
	const dir = path.join(store, INBOX);
	const files = (await readdir(dir).catch(() => [])).filter((name) => name.endsWith(".json")).sort().map((name) => path.join(dir, name));
	const read = await Promise.all(files.map((file) => readFile(file, "utf8").then(parsed, () => undefined)));
	use(read.filter((told) => told !== undefined));
	await Promise.all(files.map((file) => rm(file, { force: true })));
}

function parsed(text: string): Told | undefined {
	try {
		const told = JSON.parse(text);
		return typeof told.text === "string" ? { at: String(told.at), from: String(told.from), text: told.text } : undefined;
	} catch {
		return undefined;
	}
}
