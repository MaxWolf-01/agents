import path from "node:path";
import type { Launch, Seen } from "./effects.ts";
import { under } from "./effects.ts";

/**
 * The programs a tool may start: tmux and claude for sessions, uv for the store, memex for the explorer. Stricter than
 * P4, which bans only a shell: a tool that needs another program is a call its slice escalates.
 */
export const PROGRAMS = new Set(["tmux", "claude", "uv", "memex"]);
const SHELLS = new Set(["sh", "bash", "zsh", "dash", "ksh", "csh", "tcsh", "fish", "nu", "pwsh"]);

/** What the extension itself may not do, loading or handling an event: run a shell, or write outside the store. */
export function harnessProblems(seen: Seen, store: string): string[] {
	return [
		...seen.launches.filter((l) => l.shell || SHELLS.has(path.basename(l.program))).map((l) => `ran a shell: ${shown(l)}`),
		...seen.writes.filter((file) => file === "fd" || !under(file, store)).map((file) => `wrote ${file}`),
	];
}

/**
 * What a tool may not start, on top of the harness's rules. `given` holds the strings the model sent it: a shell that
 * receives one of them runs the model's command.
 */
export function launchProblems(launch: Launch, given: string[]): string[] {
	const program = path.basename(launch.program);
	if (launch.shell || SHELLS.has(program)) return [`ran a shell: ${shown(launch)}`];
	if (!PROGRAMS.has(program)) return [`started ${shown(launch)}`];
	if (program === "tmux") return tmuxProblems(launch.args, given);
	if (program === "claude") return claudeProblems(launch.args);
	if (program === "uv") return uvProblems(launch.args);
	return [];
}

/** Every string leaf of a tool's arguments long enough not to turn up in a fixed command by chance. */
export function strings(value: unknown): string[] {
	if (typeof value === "string") return value.length >= 4 ? [value] : [];
	if (Array.isArray(value)) return value.flatMap(strings);
	if (typeof value === "object" && value !== null) return Object.values(value).flatMap(strings);
	return [];
}

function shown({ program, args }: Launch): string {
	return [program, ...args].join(" ");
}

// tmux commands by full name and alias; a unique prefix of a full name also names it.
const TMUX_SHELL = ["run-shell", "run", "if-shell", "if", "pipe-pane", "pipep", "display-popup", "popup", "confirm-before", "confirm", "command-prompt", "source-file", "source"];
// Typing into a pane is the user's own channel (the parent's Tell), and a pane runs what it is typed.
const TMUX_TYPES = ["send-keys", "send", "send-prefix", "paste-buffer", "pasteb"];
// The commands that start a program in a pane, with the flags of each that take a value. tmux runs a command given
// as one argument through `sh -c`, and one given as several directly.
const TMUX_STARTS: Record<string, string> = {
	"new-window": "ceFnt",
	neww: "ceFnt",
	"new-session": "ceFfnstxy",
	new: "ceFfnstxy",
	"split-window": "ceFlt",
	splitw: "ceFlt",
	"respawn-pane": "cet",
	respawnp: "cet",
	"respawn-window": "cet",
	respawnw: "cet",
};

function tmuxProblems(args: string[], given: string[]): string[] {
	const global = afterOptions(args, "cfLST");
	if (global.flags.includes("c")) return [`tmux -c runs a shell command: tmux ${args.join(" ")}`];
	const problems: string[] = [];
	for (const [name, ...rest] of commands(global.rest)) {
		if (!name) continue;
		if (TMUX_SHELL.some((c) => names(name, c))) problems.push(`tmux ${name} runs a shell command`);
		if (TMUX_TYPES.some((c) => names(name, c))) problems.push(`tmux ${name} types into a pane`);
		const starts = Object.keys(TMUX_STARTS).find((c) => names(name, c));
		if (!starts) continue;
		const command = afterOptions(rest, TMUX_STARTS[starts]).rest;
		if (command.length === 1 && given.some((text) => command[0].includes(text))) problems.push(`tmux ${name} hands the model's text to a shell: ${command[0]}`);
		if (command.length > 1) problems.push(...launchProblems({ program: command[0], args: command.slice(1), shell: false }, given));
	}
	return problems;
}

function names(given: string, command: string): boolean {
	return given === command || (given.length >= 3 && command.startsWith(given) && command.includes("-"));
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

// A Claude Code session with these runs its side effects without the permission classifier judging them (P4).
const UNGUARDED = /^--(dangerously-skip-permissions|allow-dangerously-skip-permissions|allowedTools|allowed-tools)(=|$)/;

function claudeProblems(args: string[]): string[] {
	return args.flatMap((arg, i) =>
		UNGUARDED.test(arg) || arg === "--permission-mode=bypassPermissions" || (arg === "--permission-mode" && args[i + 1] === "bypassPermissions")
			? [`claude ${arg}: a session the classifier does not judge`]
			: [],
	);
}

const UV_VALUED = new Set(["--with", "--with-editable", "--with-requirements", "--python", "-p", "--project", "--directory", "--env-file", "--extra", "--group", "--index", "--default-index", "--package", "--cache-dir", "--config-file"]);

/** uv starts the store and nothing else: `uv run [options] <dir>/hv_store.py ...`. */
function uvProblems(args: string[]): string[] {
	if (args[0] !== "run") return [`uv ${args.join(" ")}: only the store runs through uv`];
	let i = 1;
	while (i < args.length && args[i].startsWith("-")) {
		if (args[i] === "--") {
			i++;
			break;
		}
		i += UV_VALUED.has(args[i]) ? 2 : 1;
	}
	return path.basename(args[i] ?? "") === "hv_store.py" ? [] : [`uv run ${args.slice(i).join(" ")}: only the store runs through uv`];
}
