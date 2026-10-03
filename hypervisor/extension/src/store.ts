import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

/** The store's command line (`hv_store.py --help`), the one home of the log and the view. */
const SCRIPT = fileURLToPath(new URL("../../store/hv_store.py", import.meta.url));

/** A command the store refused, with the reason it printed. */
export class Refused extends Error {
	name = "Refused";
}

export type Store = ReturnType<typeof store>;

/** The store at `dir`, one process per command. Every argument after the command is positional, so none reads as a flag. */
export function store(dir: string) {
	const run = (command: string[], stdin = "") => hvStore(dir, command, stdin);
	return {
		init: () => run(["init"]),
		/** Logs `text` as one entry and returns its number. */
		append: async (text: string, gist = "") => Number((await run(["append", ...(gist ? [`--gist=${gist}`] : [])], text)).trim().slice(1)),
		view: () => run(["view"]),
		/** For each count of entries from 1 to `ahead`, how many of the view's lines it starts with once they are logged. */
		stays: async (ahead: number) => (await run(["stays", `--ahead=${ahead}`])).split("\n").filter(Boolean).map(Number),
		zoom: (block: string) => run(["zoom", "--", block]),
		recall: (regex: string) => run(["recall", "--", regex]),
		raw: (id: number) => run(["raw", "--", String(id)]),
		due: async () => (await run(["due"])).split("\n").filter(Boolean),
		body: (block: string) => run(["body", "--", block]),
		compress: (block: string, line: string) => run(["compress", "--", block], line),
	};
}

function hvStore(dir: string, command: string[], stdin: string): Promise<string> {
	return new Promise((resolve, reject) => {
		const child = spawn("uv", ["run", "--quiet", SCRIPT, "--dir", dir, ...command], { stdio: ["pipe", "pipe", "pipe"] });
		const out: Buffer[] = [];
		const err: Buffer[] = [];
		child.stdout.on("data", (chunk: Buffer) => out.push(chunk));
		child.stderr.on("data", (chunk: Buffer) => err.push(chunk));
		child.on("error", reject);
		child.on("close", (code: number | null) => {
			const said = Buffer.concat(err).toString().trim();
			if (code === 0) resolve(Buffer.concat(out).toString());
			else reject(new Refused(said.replace(/^hv_store: /, "") || `hv_store ${command[0]} exited ${code}`));
		});
		child.stdin.end(stdin);
	});
}
