import { execFile } from "node:child_process";
import path from "node:path";

/**
 * Runs `program` without a shell, `input` on its stdin, else stdin closed, and returns what it printed. A failure carries what it said on
 * stderr, after the program's name and its first argument. With `anyExit`, a program that ran and exited non-zero
 * answers too, with its stdout, else its stderr: for a program whose exit code is part of its answer.
 */
export function run(program: string, args: string[], options: { cwd?: string; signal?: AbortSignal; timeout?: number; anyExit?: boolean; input?: string } = {}): Promise<string> {
	const { anyExit, input, ...given } = options;
	return new Promise((resolve, reject) => {
		const child = execFile(program, args, { ...given, encoding: "utf8", maxBuffer: 16 << 20 }, (error, stdout, stderr) => {
			if (error && anyExit && typeof error.code === "number") resolve(String(stdout).trim() ? String(stdout) : String(stderr));
			else if (error) reject(new Error(`${path.basename(program)} ${args[0]}: ${String(stderr).trim() || error.message}`));
			else resolve(String(stdout));
		});
		// A program that exits before it read its input breaks the pipe; its exit says what went wrong.
		child.stdin?.on("error", () => {});
		child.stdin?.end(input);
	});
}
