import { appendFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";

/** Appends `line` to the store's file `name` as a line of JSON, making the store's directory if it is not there yet. */
export async function append(store: string, name: string, line: object): Promise<void> {
	await mkdir(store, { recursive: true });
	await appendFile(path.join(store, name), `${JSON.stringify(line)}\n`);
}

/** The lines of the store's file `name`, oldest first; none when there is no such file, and a line that does not parse is left out. */
export async function lines<T>(store: string, name: string): Promise<T[]> {
	const text = await readFile(path.join(store, name), "utf8").catch(() => "");
	return text.split("\n").flatMap((line) => {
		try {
			return line ? [JSON.parse(line) as T] : [];
		} catch {
			return [];
		}
	});
}
