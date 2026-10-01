import childProcess from "node:child_process";
import { EventEmitter } from "node:events";
import fs from "node:fs";
import fsPromises from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import path from "node:path";
import { PassThrough } from "node:stream";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

/** A process a tool started: the program, its arguments, and whether a shell ran it. */
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
 * Watches the processes and file writes of this node process. Outside `during` everything passes through. Inside it,
 * a process is recorded and never started, and a write is recorded and carried out only under `writable`.
 * Install it before importing the code it watches, so a binding taken at load is the watched one.
 */
export function watchEffects(writable: string) {
	let seen: Seen | undefined;

	const launch = (program: string, args: unknown, shell: unknown) => {
		seen?.launches.push({ program, args: Array.isArray(args) ? args.map(String) : [], shell: Boolean(shell) });
	};
	const options = (args: unknown[]) => args.find((a): a is { shell?: unknown } => typeof a === "object" && a !== null && !Array.isArray(a));
	const callback = (args: unknown[]) => args.findLast((a): a is (...r: unknown[]) => void => typeof a === "function");

	const processes: Record<string, (original: (...a: any[]) => any) => (...a: any[]) => any> = {
		spawn: () => (file, ...rest) => (launch(file, rest[0], options(rest)?.shell), fakeChild()),
		execFile: () => {
			const run = (file: string, ...rest: unknown[]) => {
				launch(file, rest[0], options(rest)?.shell);
				const done = callback(rest);
				if (done) setImmediate(() => done(null, "", ""));
				return fakeChild();
			};
			return Object.assign(run, {
				[promisify.custom]: (file: string, ...rest: unknown[]) => (launch(file, rest[0], options(rest)?.shell), Promise.resolve({ stdout: "", stderr: "" })),
			});
		},
		exec: () => {
			const run = (command: string, ...rest: unknown[]) => {
				launch(command, [], true);
				const done = callback(rest);
				if (done) setImmediate(() => done(null, "", ""));
				return fakeChild();
			};
			return Object.assign(run, { [promisify.custom]: (command: string) => (launch(command, [], true), Promise.resolve({ stdout: "", stderr: "" })) });
		},
		spawnSync: () => (file, ...rest) => (launch(file, rest[0], options(rest)?.shell), { pid: 0, status: 0, signal: null, stdout: "", stderr: "", output: [null, "", ""] }),
		execFileSync: () => (file, ...rest) => (launch(file, rest[0], options(rest)?.shell), ""),
		execSync: () => (command) => (launch(command, [], true), ""),
		fork: () => (module, ...rest) => (launch(process.execPath, [module, ...(Array.isArray(rest[0]) ? rest[0] : [])], false), fakeChild()),
	};
	for (const [name, fake] of Object.entries(processes)) {
		const original = (childProcess as any)[name];
		const watched = fake(original);
		const wrapper = function (this: unknown, ...args: unknown[]) {
			return seen ? watched(...args) : original.apply(this, args);
		};
		const promised = (watched as any)[promisify.custom];
		if (promised) {
			const passed = original[promisify.custom];
			(wrapper as any)[promisify.custom] = (...args: unknown[]) => (seen ? promised(...args) : passed(...args));
		}
		(childProcess as any)[name] = wrapper;
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
			if (seen) {
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
		/** Runs `work` with the effects recorded, and returns what it did, including what its last callbacks did. */
		async during(work: () => Promise<unknown>): Promise<Seen> {
			const now: Seen = { launches: [], writes: [] };
			seen = now;
			try {
				await work();
				await new Promise((settle) => setImmediate(settle));
			} finally {
				seen = undefined;
			}
			return now;
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
	if (typeof flags === "number") return (flags & (fs.constants.O_WRONLY | fs.constants.O_RDWR | fs.constants.O_CREAT | fs.constants.O_TRUNC | fs.constants.O_APPEND)) !== 0;
	return typeof flags === "string" && /[wa+]/.test(flags);
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
