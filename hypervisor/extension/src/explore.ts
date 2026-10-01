import { execFile } from "node:child_process";
import type { Dirent } from "node:fs";
import { open, readdir, readlink, realpath, stat } from "node:fs/promises";
import path from "node:path";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ToolDefinition } from "@earendil-works/pi-coding-agent";
import type { Config } from "./index.ts";
import { answer } from "./tools.ts";

/**
 * The denied roots under home, as ruled under `hypervisor-property-checks` D5: keys, credential stores, browser
 * profiles and caches. `/proc` is denied too, since a process's environment there can hold a token, and so is the
 * hypervisor's store, which holds its own pi's credentials.
 */
const DENIED = [
	".ssh",
	".gnupg",
	".password-store",
	".local/share/keyrings",
	".aws",
	".config/gh",
	".netrc",
	".git-credentials",
	".claude/.credentials.json",
	".mozilla",
	".config/google-chrome",
	".config/chromium",
	".config/BraveSoftware",
	".cache/chromium",
	".config/rclone",
	".config/sops",
	".docker",
	".pi/agent/auth.json",
	".codex/auth.json",
	".dotfiles/secrets/creds",
];
const DENIED_ANYWHERE = ["/proc"];

/** Directories a search or a listing of matches walks past: what they hold is history or vendored code, not max's. */
const PASSED = new Set([".git", "node_modules"]);
/** How many entries one search visits before it stops and says so. */
const VISITS = 20_000;
const READ_LINES = 2000;
const READ_BYTES = 50_000;
/** Files larger than this are read only up to it. */
const FILE_BYTES = 5_000_000;
/** A search skips files larger than this. */
const GREP_FILE_BYTES = 1_000_000;
const MATCHES = 100;
const FOUND = 200;
const LISTED = 500;
const LINE_CHARS = 200;

export type ExploreConfig = Pick<Config, "home"> &
	Partial<Pick<Config, "store">> & {
		/** The memex program, `memex` on `PATH` unless named. */
		memex?: string;
	};

/**
 * The explorer's read tools. A tool takes what it reads as `path`: absolute, under `~/`, or relative to `home`. It
 * throws on a path under a denied root, judged once `..` and symlinks are resolved, and a search or listing passes over
 * those roots. memex's results pass through the same judgment.
 */
export function exploreTools(config: ExploreConfig): ToolDefinition[] {
	const pathParam = Type.String({ description: "Absolute, under ~/, or relative to home." });
	return [
		defineTool({
			name: "read",
			label: "Read",
			description: `Read a text file, ${READ_LINES} lines or ${READ_BYTES / 1000} kB at most per call; offset and limit page through a longer one.`,
			parameters: Type.Object({
				path: pathParam,
				offset: Type.Optional(Type.Integer({ description: "The first line to read, from 1." })),
				limit: Type.Optional(Type.Integer({ description: `How many lines to read, at most ${READ_LINES}.` })),
			}),
			execute: async (_id, { path: spelled, offset, limit }) => answer(await readText(await (await places(config)).open(spelled), offset, limit)),
		}),
		defineTool({
			name: "ls",
			label: "List",
			description: "List a directory: a directory ends in /, a symlink shows where it points, and a denied path says so and is not opened.",
			parameters: Type.Object({ path: pathParam }),
			execute: async (_id, { path: spelled }) => {
				const where = await places(config);
				return answer(await list(where, await where.open(spelled)));
			},
		}),
		defineTool({
			name: "find",
			label: "Find",
			description: `Find files and directories under a path whose name, or path from there when the pattern holds a /, matches a glob such as *.md or projects/**/README.md. Passes over ${[...PASSED].join(" and ")}; prints ${FOUND} at most.`,
			parameters: Type.Object({ path: pathParam, pattern: Type.String({ description: "A glob." }) }),
			execute: async (_id, { path: spelled, pattern }, signal) => {
				const where = await places(config);
				return answer(await find(where, await where.open(spelled), pattern, signal));
			},
		}),
		defineTool({
			name: "grep",
			label: "Grep",
			description: `Search the text files under a path, or one file, for a JavaScript regular expression, ignoring case. Prints each matching line with its file and line number, ${MATCHES} at most. Passes over ${[...PASSED].join(" and ")}, binary files and files over ${GREP_FILE_BYTES / 1_000_000} MB.`,
			parameters: Type.Object({
				path: pathParam,
				pattern: Type.String({ description: "A regular expression." }),
				glob: Type.Optional(Type.String({ description: "Only files whose name matches this glob, such as *.md." })),
			}),
			execute: async (_id, { path: spelled, pattern, glob }, signal) => {
				const where = await places(config);
				return answer(await grep(where, await where.open(spelled), new RegExp(pattern, "i"), glob, signal));
			},
		}),
		defineTool({
			name: "memex",
			label: "memex",
			description:
				"Search max's markdown vaults with memex. `search` ranks notes by meaning, for a question in a sentence or a few; `find` matches note titles, aliases and paths, fuzzily. Prints the notes' paths, which read takes.",
			parameters: Type.Object({
				command: Type.Union([Type.Literal("search"), Type.Literal("find")]),
				query: Type.String(),
				vault: Type.Optional(Type.String({ description: "One vault's name; every vault when left out." })),
				limit: Type.Optional(Type.Integer({ description: "How many notes, at most 50." })),
			}),
			execute: async (_id, { command, query, vault, limit }, signal) =>
				answer(await memex(config.memex ?? "memex", await places(config), { command, query, vault, limit }, signal)),
		}),
	] as ToolDefinition[];
}

type Places = Awaited<ReturnType<typeof places>>;

const inside = (real: string, root: string) => real === root || real.startsWith(`${root}/`);

/**
 * Where a path the model sent leads, and whether the explorer may go there. The denied roots are resolved once per
 * tool call, kept both as spelled and as they resolve, for a root that is a symlink or lies below one.
 */
async function places({ home, store }: ExploreConfig) {
	const spelled = [...DENIED.map((root) => path.join(home, root)), ...DENIED_ANYWHERE, ...(store ? [store] : [])];
	const resolved = await Promise.all(spelled.map((root) => realpath(root).catch(() => root)));
	const roots = [...new Set([...spelled, ...resolved])];

	return {
		home,
		/** Whether a resolved path lies in a denied root. */
		denied(real: string): boolean {
			return roots.some((root) => inside(real, root));
		},
		/**
		 * The resolved path `spelled` leads to. The kernel resolves it as spelled, so a `..` after a symlink leaves
		 * from where the link points; a denied place throws, and so does one that is not there.
		 */
		async open(spelled: string): Promise<string> {
			const absolute = spelled === "~" ? home : spelled.startsWith("~/") ? `${home}/${spelled.slice(2)}` : spelled.startsWith("/") ? spelled : `${home}/${spelled}`;
			const real = await realpath(absolute).catch((error: NodeJS.ErrnoException) => {
				throw new Error(`${spelled}: ${error.code === "ENOENT" ? "no such file or directory" : error.code}`);
			});
			if (this.denied(real)) throw new Error(`${spelled}: denied, the explorer does not read keys, credentials, browser profiles or the hypervisor's own store`);
			return real;
		},
		/** A resolved path as the model reads it: under `~/` when it is in home. */
		shown(real: string): string {
			return inside(real, home) ? `~${real.slice(home.length)}` : real;
		},
	};
}

async function readText(file: string, offset = 1, limit = READ_LINES): Promise<string> {
	const info = await stat(file);
	if (info.isDirectory()) throw new Error("a directory: ls lists it");
	if (!info.isFile()) throw new Error("not a regular file");
	const handle = await open(file, "r");
	let bytes: Buffer;
	try {
		bytes = Buffer.alloc(Math.min(info.size, FILE_BYTES));
		await handle.read(bytes, 0, bytes.length, 0);
	} finally {
		await handle.close();
	}
	if (binary(bytes)) return `(a binary file, ${info.size} bytes)`;
	const lines = bytes.toString("utf8").split("\n");
	const first = Math.max(1, offset);
	const out: string[] = [];
	let size = 0;
	for (let n = first; n <= lines.length && n < first + Math.min(Math.max(1, limit), READ_LINES); n++) {
		size += Buffer.byteLength(lines[n - 1]) + 1;
		if (size > READ_BYTES && out.length) break;
		out.push(lines[n - 1]);
	}
	const last = first + out.length - 1;
	const more = last < lines.length ? `\n(lines ${first}-${last} of ${lines.length}${info.size > FILE_BYTES ? `, of the first ${FILE_BYTES} bytes` : ""}; offset ${last + 1} reads on)` : "";
	return out.join("\n") + more;
}

function binary(bytes: Buffer): boolean {
	return bytes.subarray(0, 8000).includes(0);
}

async function list(where: Places, dir: string): Promise<string> {
	const entries = (await readdir(dir, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name));
	const lines = await Promise.all(entries.slice(0, LISTED).map((entry) => listed(where, dir, entry)));
	return [...lines, ...(entries.length > LISTED ? [`(${entries.length - LISTED} more entries)`] : [])].join("\n");
}

async function listed(where: Places, dir: string, entry: Dirent): Promise<string> {
	const at = path.join(dir, entry.name);
	if (entry.isSymbolicLink()) {
		const real = await realpath(at).catch(() => undefined);
		if (real === undefined) return `${entry.name}@ → (broken)`;
		return where.denied(real) ? `${entry.name}@ → (denied)` : `${entry.name}@ → ${await readlink(at)}`;
	}
	if (where.denied(at)) return `${entry.name} (denied)`;
	return entry.isDirectory() ? `${entry.name}/` : entry.name;
}

/**
 * Every entry under `root` that is not denied, depth first, without following a symlink into a directory: each file
 * with the resolved path it reads from, and each directory. A symlinked file is resolved, and passed over when it leads
 * into a denied root. Stops after `VISITS` entries, or when `signal` aborts.
 */
async function* walk(where: Places, root: string, signal?: AbortSignal): AsyncGenerator<{ at: string; real: string; dir: boolean } | { stopped: string }> {
	if (!(await stat(root)).isDirectory()) {
		yield { at: root, real: root, dir: false };
		return;
	}
	const stack = [root];
	let visits = 0;
	while (stack.length) {
		const dir = stack.pop()!;
		const entries = await readdir(dir, { withFileTypes: true }).catch(() => [] as Dirent[]);
		for (const entry of entries.sort((a, b) => b.name.localeCompare(a.name))) {
			const stopped = signal?.aborted ? "the call was stopped" : ++visits > VISITS ? `stopped after ${VISITS} entries` : undefined;
			if (stopped) {
				yield { stopped };
				return;
			}
			const at = path.join(dir, entry.name);
			if (entry.isSymbolicLink()) {
				const real = await realpath(at).catch(() => undefined);
				if (real === undefined || where.denied(real)) continue;
				const info = await stat(real).catch(() => undefined);
				if (info?.isFile()) yield { at, real, dir: false };
			} else if (!where.denied(at)) {
				if (entry.isDirectory()) {
					yield { at, real: at, dir: true };
					if (!PASSED.has(entry.name)) stack.push(at);
				} else if (entry.isFile()) yield { at, real: at, dir: false };
			}
		}
	}
}

async function find(where: Places, root: string, pattern: string, signal?: AbortSignal): Promise<string> {
	const found: string[] = [];
	for await (const item of walk(where, root, signal)) {
		if ("stopped" in item) {
			found.push(`(${item.stopped})`);
			break;
		}
		const rel = path.relative(root, item.at) || path.basename(item.at);
		if (!path.matchesGlob(pattern.includes("/") ? rel : path.basename(item.at), pattern)) continue;
		if (found.length === FOUND) {
			found.push(`(more than ${FOUND} found)`);
			break;
		}
		found.push(item.dir ? `${rel}/` : rel);
	}
	return found.join("\n");
}

async function grep(where: Places, root: string, pattern: RegExp, glob: string | undefined, signal?: AbortSignal): Promise<string> {
	const matches: string[] = [];
	for await (const item of walk(where, root, signal)) {
		if ("stopped" in item) {
			matches.push(`(${item.stopped})`);
			break;
		}
		if (item.dir || (glob && !path.matchesGlob(path.basename(item.at), glob))) continue;
		const text = await searchable(item.real);
		if (text === undefined) continue;
		const rel = path.relative(root, item.at) || path.basename(item.at);
		for (const [i, line] of text.split("\n").entries()) {
			if (!pattern.test(line)) continue;
			if (matches.length === MATCHES) return [...matches, `(more than ${MATCHES} matches)`].join("\n");
			matches.push(`${rel}:${i + 1}: ${Array.from(line).slice(0, LINE_CHARS).join("")}`);
		}
	}
	return matches.join("\n");
}

/** A file's text, unless it is too large or binary to search. */
async function searchable(file: string): Promise<string | undefined> {
	const info = await stat(file).catch(() => undefined);
	if (!info?.isFile() || info.size > GREP_FILE_BYTES) return undefined;
	const handle = await open(file, "r").catch(() => undefined);
	if (!handle) return undefined;
	try {
		const bytes = Buffer.alloc(info.size);
		await handle.read(bytes, 0, info.size, 0);
		return binary(bytes) ? undefined : bytes.toString("utf8");
	} finally {
		await handle.close();
	}
}

interface MemexAsk {
	command: "search" | "find";
	query: string;
	vault?: string;
	limit?: number;
}

/**
 * memex's answer, rebuilt from what it names: memex prints each note's path from its vault's root, and a path counts
 * only once it resolves, under one of those roots, to a file outside every denied root. Anything else memex printed,
 * such as a note's text, is dropped, so no text from a denied root reaches the model.
 */
async function memex(program: string, where: Places, ask: MemexAsk, signal?: AbortSignal): Promise<string> {
	const run = (args: string[]) =>
		new Promise<string>((resolve, reject) =>
			execFile(program, args, { cwd: where.home, signal, timeout: 300_000, maxBuffer: 10_000_000 }, (error, stdout, stderr) =>
				error ? reject(new Error(`memex ${args[0]}: ${String(stderr).trim() || error.message}`)) : resolve(String(stdout)),
			),
		);
	const vaults = vaultRoots(await run(["vault:list"]));
	const limit = Math.min(Math.max(1, ask.limit ?? (ask.command === "search" ? 5 : 10)), 50);
	const said = await run([ask.command, `--limit=${limit}`, ...(ask.vault === undefined ? [] : [`--vault=${ask.vault}`]), "--", ask.query]);

	const found = new Map<string, string[]>();
	let vault = ask.vault;
	for (const line of said.split("\n")) {
		const text = line.trim();
		if (!text) continue;
		if (!line.startsWith(" ") && vaults.has(text)) {
			vault = text;
			continue;
		}
		const note = await notePath(where, vault === undefined ? [...vaults.values()].flat() : (vaults.get(vault) ?? []), text);
		if (note) found.set(vault ?? "", [...(found.get(vault ?? "") ?? []), note]);
	}
	if (!found.size) return `no notes for "${ask.query}"`;
	return [...found].map(([name, notes]) => [...(name ? [name] : []), ...notes.map((n) => `  ${n}`)].join("\n")).join("\n");
}

/** The vaults `memex vault:list` prints: each name on a line of its own, its directories indented below it. */
function vaultRoots(listing: string): Map<string, string[]> {
	const vaults = new Map<string, string[]>();
	let name: string | undefined;
	for (const line of listing.split("\n")) {
		if (!line.trim()) continue;
		if (line.startsWith(" ") && name !== undefined) vaults.get(name)!.push(line.trim());
		else if (!line.startsWith(" ")) vaults.set((name = line.replace(/ \(model: .*\)$/, "").trim()), []);
	}
	return vaults;
}

/**
 * The note a line of memex's names, shown as the read tools take it: the line resolved under each root, as long as one
 * of those is a file outside the denied roots and none is a file inside them.
 */
async function notePath(where: Places, roots: string[], line: string): Promise<string | undefined> {
	const candidates = path.isAbsolute(line) ? [line] : roots.map((root) => `${root}/${line}`);
	let note: string | undefined;
	for (const candidate of candidates) {
		const real = await realpath(candidate).catch(() => undefined);
		if (real === undefined || !(await stat(real)).isFile()) continue;
		if (where.denied(real)) return undefined;
		note ??= real;
	}
	return note === undefined ? undefined : where.shown(note);
}
