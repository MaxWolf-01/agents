import path from "node:path";
import type { Launch, Seen } from "./effects.ts";
import { under } from "./effects.ts";

/**
 * The programs a tool may start: tmux and claude for sessions, memex for the explorer, job for wait.
 * Stricter than P4, which bans only a shell: a tool that needs another program is a call its slice escalates.
 */
const PROGRAMS = new Set(["tmux", "claude", "memex", "job"]);
/** Shells, and the programs that run another program named in their arguments. */
const SHELLS = new Set(["sh", "bash", "zsh", "dash", "ksh", "csh", "tcsh", "fish", "nu", "pwsh", "env", "xargs", "nohup", "setsid", "timeout", "nice", "stdbuf", "sudo"]);

/**
 * What the extension may not do, loading or handling an event: write outside the store, run one of the shells and
 * runners above, or ask tmux or claude for what a tool may not. Any other program a handler starts is its slice's
 * review to read: a handler is the harness, not the model's tool.
 */
export function harnessProblems(seen: Seen, store: string): string[] {
	const ours = (l: Launch) => PROGRAMS.has(path.basename(l.program));
	return [...writeProblems(seen, store), ...seen.launches.flatMap((l) => (ours(l) ? launchProblems(l, []) : shellProblems(l)))];
}

/** What a tool may not do: the harness's rules, and no program outside the closed set. */
export function toolProblems(seen: Seen, store: string, given: string[]): string[] {
	return [...writeProblems(seen, store), ...seen.launches.flatMap((l) => launchProblems(l, given))];
}

/** Every string leaf of a tool's arguments long enough not to turn up in a fixed command by chance. */
export function strings(value: unknown): string[] {
	if (typeof value === "string") return value.length >= 4 ? [value] : [];
	if (Array.isArray(value)) return value.flatMap(strings);
	if (typeof value === "object" && value !== null) return Object.values(value).flatMap(strings);
	return [];
}

function writeProblems(seen: Seen, store: string): string[] {
	return seen.writes.filter((file) => file === "fd" || !under(file, store)).map((file) => `wrote ${file}`);
}

function shellProblems(launch: Launch): string[] {
	return launch.shell || SHELLS.has(path.basename(launch.program)) ? [`ran a shell: ${commandLine(launch)}`] : [];
}

/** `given` holds the strings the model sent: a shell or a tmux format that receives one of them runs the model's command. */
function launchProblems(launch: Launch, given: string[]): string[] {
	const program = path.basename(launch.program);
	const shell = shellProblems(launch);
	if (shell.length) return shell;
	if (!PROGRAMS.has(program)) return [`started ${commandLine(launch)}`];
	if (program === "tmux") return tmuxProblems(launch.args, given);
	if (program === "claude") return claudeProblems(launch.args);
	if (program === "job") return jobProblems(launch.args);
	return [];
}

function commandLine({ program, args }: Launch): string {
	return [program, ...args].join(" ");
}

// The tmux commands a tool may run, by full name and alias, with the flags of each that take a value. The rest either
// run a shell command (run-shell, if-shell, a hook, a default-command), or type into a pane, which is the user's own
// channel (`lifelong-hypervisor`'s Tell) and runs what it is typed.
const TMUX: Record<string, string> = {
	"new-session": "ceFfnstxy",
	new: "ceFfnstxy",
	"new-window": "ceFnt",
	neww: "ceFnt",
	"has-session": "t",
	has: "t",
	"list-sessions": "Ff",
	ls: "Ff",
	"list-windows": "Fft",
	lsw: "Fft",
	"list-panes": "Fft",
	lsp: "Fft",
	"capture-pane": "bEStT",
	capturep: "bEStT",
	"display-message": "cdFt",
	display: "cdFt",
	"select-window": "t",
	selectw: "t",
	"rename-window": "t",
	renamew: "t",
	"kill-window": "t",
	killw: "t",
};
// The ones that start a program in a pane. tmux runs a command given as one argument through `sh -c`, and one given
// as several directly; one plain word is the same either way.
const STARTS = new Set(["new-session", "new", "new-window", "neww"]);

function tmuxProblems(args: string[], given: string[]): string[] {
	const global = afterOptions(args, "cfLST");
	if (global.flags.includes("c")) return [`tmux -c runs a shell command: tmux ${args.join(" ")}`];
	const problems: string[] = [];
	for (const [name, ...rest] of commands(global.rest)) {
		if (!name) continue;
		if (!Object.hasOwn(TMUX, name)) {
			problems.push(`tmux ${name} is not among the commands a tool may run`);
			continue;
		}
		const command = STARTS.has(name) ? afterOptions(rest, TMUX[name]).rest : [];
		// tmux reads a command's arguments as formats, all but the program it starts, and runs a `#(...)` in a
		// format through a shell; `##` is a literal `#`.
		for (const arg of rest.slice(0, rest.length - command.length)) if (arg.replaceAll("##", "").includes("#(")) problems.push(`tmux runs the format ${arg} through a shell`);
		if (command.length === 1 && /[^\w./-]/.test(command[0])) problems.push(`tmux ${name} runs ${command[0]} through sh -c`);
		else if (command.length) problems.push(...launchProblems({ program: command[0], args: command.slice(1), shell: false }, given));
	}
	return problems;
}

/** tmux's command list split at each lone `;`. */
function commands(args: string[]): string[][] {
	const out: string[][] = [[]];
	for (const arg of args) {
		if (arg === ";") out.push([]);
		else out[out.length - 1].push(arg);
	}
	return out;
}

/** getopt's reading of `args`: the option letters, and what follows them. `valued` are the letters that take a value. */
function afterOptions(args: string[], valued: string): { flags: string; rest: string[] } {
	let flags = "";
	let i = 0;
	for (; i < args.length && args[i].startsWith("-") && args[i] !== "-"; i++) {
		if (args[i] === "--") return { flags, rest: args.slice(i + 1) };
		const letters = args[i].slice(1);
		const at = [...letters].findIndex((l) => valued.includes(l));
		flags += at >= 0 ? letters.slice(0, at + 1) : letters;
		if (at === letters.length - 1) i++; // its value is the next argument
	}
	return { flags, rest: args.slice(i) };
}

/** claude's commands that start no session. */
const CLAUDE_COMMANDS = new Set(["agents", "--version", "-v", "--help", "-h"]);
// Flags that let a session act without the classifier judging it, or change what it permits.
const UNGUARDED = /^--(dangerously-skip-permissions|allow-dangerously-skip-permissions|allowedTools|allowed-tools|settings|permission-prompt-tool)(=|$)/;

/** A session runs in auto mode, where the classifier judges its side effects (`lifelong-hypervisor`'s safety boundary, P4). */
function claudeProblems(args: string[]): string[] {
	if (CLAUDE_COMMANDS.has(args[0])) return [];
	const problems = args.filter((arg) => UNGUARDED.test(arg)).map((arg) => `claude ${arg}: changes what the classifier judges`);
	const mode = args.flatMap((arg, i) => (arg === "--permission-mode" ? [args[i + 1]] : arg.startsWith("--permission-mode=") ? [arg.slice(arg.indexOf("=") + 1)] : []));
	if (mode.length !== 1 || mode[0] !== "auto") problems.push(`claude ${args.join(" ")}: a session not in auto mode`);
	return problems;
}

/** job's flags that wait takes, each with a value. */
const JOB_WAIT = new Set(["--deadline", "--stall", "--watch"]);

/**
 * job runs `probe`, or `wait <name>` with a deadline and its other flags, and nothing that starts or stops a job: a job
 * runs its command through a shell. A value that starts with `-` would reach grep, or job, as an option.
 */
function jobProblems(args: string[]): string[] {
	if (args.length === 1 && args[0] === "probe") return [];
	const shown = `job ${args.join(" ")}`;
	if (args[0] !== "wait" || !args[1] || args[1].startsWith("-")) return [`${shown}: job runs probe, or wait on a named job`];
	const flags = args.slice(2);
	const problems: string[] = [];
	for (let i = 0; i < flags.length; i += 2) {
		if (!JOB_WAIT.has(flags[i])) problems.push(`${shown}: ${flags[i]} is not a flag wait takes`);
		else if (flags[i + 1] === undefined || flags[i + 1].startsWith("-")) problems.push(`${shown}: ${flags[i]} has no value`);
	}
	if (!flags.includes("--deadline")) problems.push(`${shown}: a wait with no deadline`);
	return problems;
}
