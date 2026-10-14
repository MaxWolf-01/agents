import childProcess from "node:child_process";
import { EventEmitter } from "node:events";
import fs from "node:fs";
import fsPromises from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import path from "node:path";
import { PassThrough } from "node:stream";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

/** A process started: the program, its arguments, and whether a shell ran it. */
export interface Launch {
	program: string;
	args: string[];
	shell: boolean;
}

export interface Seen {
	launches: Launch[];
	/** Every path a write targeted, resolved; an open file descriptor reads as `fd`. */
	writes: string[];
}

/**
 * Watches the processes and file writes of this node process from the moment it is installed until `stop`. A process
 * is recorded and never started; a write is recorded and carried out only under `writable`. What happens inside
 * `during` is returned by it; anything else, such as a tool still running after its time ran out, is `stray`.
 * Install it before importing the code it watches, so a binding taken at load is the watched one.
 */
export function watchEffects(writable: string) {
	let watching = true;
	const stray: Seen = { launches: [], writes: [] };
	let seen = stray;

	const launch = (program: unknown, args: unknown, shell: unknown) => {
		seen.launches.push({ program: String(program), args: Array.isArray(args) ? args.map(String) : [], shell: Boolean(shell) });
	};
	const options = (args: unknown[]) => args.find((a): a is { shell?: unknown } => typeof a === "object" && a !== null && !Array.isArray(a));
	// The launch each child_process function makes from its arguments; exec and execSync always go through a shell.
	const launches: Record<string, (args: unknown[]) => void> = {
		spawn: ([file, argv, ...rest]) => launch(file, argv, options([argv, ...rest])?.shell),
		spawnSync: ([file, argv, ...rest]) => launch(file, argv, options([argv, ...rest])?.shell),
		execFile: ([file, argv, ...rest]) => launch(file, argv, options([argv, ...rest])?.shell),
		execFileSync: ([file, argv, ...rest]) => launch(file, argv, options([argv, ...rest])?.shell),
		exec: ([command]) => launch(command, [], true),
		execSync: ([command]) => launch(command, [], true),
		fork: ([module, argv]) => launch(process.execPath, [module, ...(Array.isArray(argv) ? argv : [])], false),
	};
	const results: Record<string, (args: unknown[]) => unknown> = {
		spawn: () => fakeChild(),
		fork: () => fakeChild(),
		execFile: (args) => answer(args),
		exec: (args) => answer(args),
		spawnSync: () => ({ pid: 0, status: 0, signal: null, stdout: "", stderr: "", output: [null, "", ""] }),
		execFileSync: () => "",
		execSync: () => "",
	};
	for (const [name, record] of Object.entries(launches)) {
		const original = (childProcess as any)[name];
		const watched: any = function (this: unknown, ...args: unknown[]) {
			if (!watching) return original.apply(this, args);
			record(args);
			return results[name](args);
		};
		if (original[promisify.custom])
			watched[promisify.custom] = (...args: unknown[]) => {
				if (!watching) return original[promisify.custom](...args);
				record(args);
				return Promise.resolve({ stdout: "", stderr: "" });
			};
		(childProcess as any)[name] = watched;
	}

	// Each write and the arguments that name what it changes: a rename changes both of its paths.
	const writes: Record<string, (args: unknown[]) => unknown[]> = {
		writeFile: (a) => [a[0]],
		appendFile: (a) => [a[0]],
		mkdir: (a) => [a[0]],
		mkdtemp: (a) => [a[0]],
		rm: (a) => [a[0]],
		rmdir: (a) => [a[0]],
		unlink: (a) => [a[0]],
		truncate: (a) => [a[0]],
		chmod: (a) => [a[0]],
		chown: (a) => [a[0]],
		utimes: (a) => [a[0]],
		rename: (a) => [a[0], a[1]],
		copyFile: (a) => [a[1]],
		cp: (a) => [a[1]],
		symlink: (a) => [a[1]],
		link: (a) => [a[1]],
		open: (a) => (writing(a[1]) ? [a[0]] : []),
		createWriteStream: (a) => [a[0]],
	};
	const guard = (target: any, name: string, targets: (args: unknown[]) => unknown[]) => {
		const original = target[name];
		if (typeof original !== "function") return;
		target[name] = function (this: unknown, ...args: unknown[]) {
			if (watching) {
				const paths = targets(args).map(resolved);
				seen.writes.push(...paths);
				const outside = paths.find((p) => p === "fd" || !under(p, writable));
				if (outside) throw Object.assign(new Error(`EACCES: watched write to ${outside}`), { code: "EACCES" });
			}
			return original.apply(this, args);
		};
	};
	for (const [name, targets] of Object.entries(writes)) {
		guard(fs, name, targets);
		guard(fs, `${name}Sync`, targets);
		guard(fsPromises, name, targets);
	}
	syncBuiltinESMExports();

	return {
		/** Runs `work`, and returns what it did, including what its last callbacks did. */
		async during(work: () => Promise<unknown>): Promise<Seen> {
			const now: Seen = { launches: [], writes: [] };
			seen = now;
			try {
				await work();
				await new Promise((settle) => setImmediate(settle));
			} finally {
				seen = stray;
			}
			return now;
		},
		stray,
		stop() {
			watching = false;
		},
	};
}

export function under(file: string, dir: string): boolean {
	const rel = path.relative(dir, file);
	return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

function resolved(target: unknown): string {
	if (typeof target === "number") return "fd";
	if (target instanceof URL) return path.resolve(fileURLToPath(target));
	return path.resolve(String(target));
}

function writing(flags: unknown): boolean {
	const { O_WRONLY, O_RDWR, O_CREAT, O_TRUNC, O_APPEND } = fs.constants;
	if (typeof flags === "number") return (flags & (O_WRONLY | O_RDWR | O_CREAT | O_TRUNC | O_APPEND)) !== 0;
	return typeof flags === "string" && /[wa+]/.test(flags);
}

/** What a callback-style launch answers: no output, at once, and a child that has already exited. */
function answer(args: unknown[]) {
	const done = args.findLast((a): a is (...r: unknown[]) => void => typeof a === "function");
	if (done) setImmediate(() => done(null, "", ""));
	return fakeChild();
}

/** A child process that exits 0 at once with no output, for a launch that is recorded and never run. */
function fakeChild() {
	const child = Object.assign(new EventEmitter(), {
		pid: 0,
		exitCode: null as number | null,
		stdin: new PassThrough(),
		stdout: new PassThrough(),
		stderr: new PassThrough(),
		kill: () => true,
	});
	setImmediate(() => {
		child.stdout.end();
		child.stderr.end();
		child.exitCode = 0;
		child.emit("spawn");
		child.emit("exit", 0, null);
		child.emit("close", 0, null);
	});
	return child;
}
