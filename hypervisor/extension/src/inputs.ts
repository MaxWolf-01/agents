import { mkdir, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { shown } from "./paths.ts";

/**
 * Where max's messages are kept, one numbered file each, under his home. It lies outside the store, which the
 * explorer's read tools deny, so the hypervisor can read one back by line range like any other file.
 */
export const inputsDir = (home: string) => path.join(home, ".local/share/hypervisor-inputs");

/** The line `save` puts under max's message, naming its file. */
const SAVED = /\n\n\(saved as [^\n]*\/\d+\.txt\)$/;

/**
 * Saves `text` as the next of `dir`'s numbered files, `<n>.txt` one past the highest there, and returns `text` with a
 * line under it giving that file's path. A message that already ends in such a line, which pi hands back to the editor
 * when a queued message is dequeued, is saved again without it.
 */
export async function save(home: string, dir: string, text: string): Promise<string> {
	const bare = text.replace(SAVED, "");
	await mkdir(dir, { recursive: true });
	for (;;) {
		const taken = (await readdir(dir)).flatMap((name) => /^(\d+)\.txt$/.exec(name)?.[1] ?? []).map(Number);
		const file = path.join(dir, `${Math.max(0, ...taken) + 1}.txt`);
		try {
			// `wx`: another writer that took the number first makes this one look again.
			await writeFile(file, bare, { flag: "wx" });
			return `${bare}\n\n(saved as ${shown(home, file)})`;
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
		}
	}
}
