import { execFile } from "node:child_process";
import path from "node:path";

/**
 * Runs `program` without a shell, its stdin closed, and returns what it printed. A failure carries what it said on
 * stderr, after the program's name and its first argument.
 */
export function run(program: string, args: string[], options: { cwd?: string; signal?: AbortSignal; timeout?: number } = {}): Promise<string> {
	return new Promise((resolve, reject) => {
		const child = execFile(program, args, { ...options, encoding: "utf8", maxBuffer: 16 << 20 }, (error, stdout, stderr) => {
			if (error) reject(new Error(`${path.basename(program)} ${args[0]}: ${String(stderr).trim() || error.message}`));
			else resolve(String(stdout));
		});
		child.stdin?.end();
	});
}
