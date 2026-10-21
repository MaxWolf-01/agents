import { readdir, readFile, realpath, stat } from "node:fs/promises";
import { createConnection } from "node:net";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { append, lines } from "./journal.ts";
import { absolute, claudeConfigs, shown } from "./paths.ts";
import { run } from "./run.ts";

/** Where the session tools find things: max's home, whose `.claude*` directories list the live sessions, and the store. */
export interface SessionConfig {
	home: string;
	store: string;
}

/** The configuration from the environment: the store `$HV_STORE`, or `~/.local/share/hypervisor`; the home `$HV_HOME`, or home. */
export function fromEnvironment(): SessionConfig {
	return { store: process.env.HV_STORE ?? path.join(homedir(), ".local/share/hypervisor"), home: process.env.HV_HOME ?? homedir() };
}

/** A live Claude Code session: its registry entry, and the tmux window its pane is in. */
export interface Session {
	pid: number;
	name: string;
	cwd: string;
	/** `busy`, `idle`, or whatever else Claude Code writes there. */
	status: string;
	/** The inbox socket, where a cross-session message is delivered. */
	socket?: string;
	/** The tmux pane, as `%N`. */
	pane?: string;
	/** The tmux window, as `session:window`; unknown when tmux does not list the pane. */
	window?: string;
}

/** A window spawn opened, as `spawned.jsonl` in the store keeps it, with the pid of the claude it runs. */
export interface Spawned {
	at: string;
	pane: string;
	pid: number;
	window: string;
	dir: string;
}

/** The `hv` script, which an orchestrator runs to report back. */
const HV = fileURLToPath(new URL("../../hv", import.meta.url));
const SPAWNED = "spawned.jsonl";
/** How long a delegated task runs before it is stopped. */
export const DELEGATE_MINUTES = 45;
/** How long a session's inbox socket has to take a message. */
const INBOX_MS = 5000;
/** How many lines of a pane `look` shows. */
const PANE_LINES = 50;
const BRIEFLY = "Your answer goes back to the hypervisor, an agent that coordinates max's sessions and pays for every word it reads: answer with what it asked for and nothing else, as briefly as the answer allows.";

/**
 * Opens a tmux window named `name` in the tmux session of the repo `dir` lies in, running interactive Claude Code in
 * auto mode in `dir` with `prompt` as its first prompt. The repo's tmux session is started if it does not run yet.
 */
export async function spawn(config: SessionConfig, { dir, name, prompt }: { dir: string; name: string; prompt: string }): Promise<string> {
	const where = await directory(config.home, dir);
	const window = slug(name);
	const group = slug(path.basename(await repo(where)));
	if (!window) throw new Error(`"${name}" leaves no window name; use letters, digits, - or _`);
	if (!prompt.trim()) throw new Error("the prompt is empty");
	const claude = ["claude", "--permission-mode", "auto", "--name", window, "--", `${prompt.trim()}\n\n${reportBack(config.store)}`];
	const running = await run("tmux", ["has-session", "-t", `=${group}`]).then(
		() => true,
		() => false,
	);
	if (running && (await run("tmux", ["list-windows", "-t", `=${group}`, "-F", "#{window_name}"])).split("\n").includes(window))
		throw new Error(`${group}:${window} exists already; look at it, or give the new one another name`);
	// The window runs claude itself, not a shell that starts it, so the pane's process is the session's.
	const at = ["-n", window, "-c", where, "-P", "-F", "#{pane_id} #{pane_pid}"];
	const opened = running ? ["new-window", "-d", "-t", `=${group}:`, ...at] : ["new-session", "-d", "-s", group, ...at];
	const [pane, pid] = (await run("tmux", [...opened, ...claude])).trim().split(" ");
	const spawned: Spawned = { at: new Date().toISOString(), pane, pid: Number(pid), window: `${group}:${window}`, dir: where };
	await append(config.store, SPAWNED, spawned);
	const started = `Started ${spawned.window} in ${where}. max steps in with: tmux switch-client -t ${pane || `=${group}:${window}`}`;
	if (await trusted(config.home, where)) return started;
	return `${started}\nClaude Code has no record of being trusted in ${shown(config.home, where)}, so its trust dialog may hold the prompt until max accepts it in that window.`;
}

/** Sends `message` to a session's inbox socket, as a cross-session message from the hypervisor. */
export async function tell(config: SessionConfig, { session, message }: { session: string; message: string }): Promise<string> {
	if (!message.trim()) throw new Error("the message is empty");
	const target = find(await sessions(config.home), session);
	if (!target.socket) throw new Error(`${label(target)} has no inbox socket, so it cannot be messaged`);
	await deliver(target.socket, frame(`${message.trim()}\n\n${reportBack(config.store)}`));
	return `Sent to ${label(target)}.`;
}

/**
 * Without a session, a line for each session `claude agents` lists, then for each live one it does not, such as a
 * session of another Claude Code config directory. With one, its state and the tail of its pane.
 */
export async function look(config: SessionConfig, { session }: { session?: string }): Promise<string> {
	const live = await sessions(config.home);
	if (session === undefined) {
		const spawned = new Set((await spawnedWindows(config.store)).map((s) => s.pid));
		const agents = JSON.parse((await run("claude", ["agents", "--json"])).trim() || "[]") as Agent[];
		const rest = live.filter((s) => !agents.some((agent) => agent.pid === s.pid));
		const line = (fields: (string | undefined)[], pid?: number) => fields.map((f) => f ?? "?").join(" · ") + (pid !== undefined && spawned.has(pid) ? " · spawned by you" : "");
		const where = (s: Session | undefined) => s?.window ?? (s ? "no tmux" : "background");
		return [
			// An interactive session's state is its `status`, a background one's its `state`.
			...agents.map((a) => line([a.name ?? a.id, a.status ?? a.state, a.cwd && shown(config.home, a.cwd), where(live.find((s) => s.pid === a.pid))], a.pid)),
			...rest.map((s) => line([s.name, s.status, shown(config.home, s.cwd), where(s)], s.pid)),
		].join("\n");
	}
	const target = find(live, session);
	const head = `${label(target)} · ${target.status} · ${shown(config.home, target.cwd)}`;
	if (!target.pane) return `${head}\n(no tmux pane)`;
	const pane = await run("tmux", ["capture-pane", "-p", "-J", "-t", target.pane, "-S", `-${PANE_LINES}`]);
	return `${head}\n${pane.replace(/\n{3,}/g, "\n\n").trimEnd()}`;
}

/**
 * `task` checked, and where it runs resolved: refused now, not once it runs. What it returns runs the task in a one-shot
 * Claude Code session in auto mode, in `dir` or max's home, and answers with what the session answered.
 */
export async function delegation(config: SessionConfig, { task, dir }: { task: string; dir?: string }): Promise<(signal?: AbortSignal) => Promise<string>> {
	if (!task.trim()) throw new Error("the task is empty");
	const cwd = dir === undefined ? config.home : await directory(config.home, dir);
	return (signal) => {
		const stop = AbortSignal.any([AbortSignal.timeout(DELEGATE_MINUTES * 60_000), ...(signal ? [signal] : [])]);
		return run("claude", ["-p", "--permission-mode", "auto", "--output-format", "text", "--", `${task.trim()}\n\n${BRIEFLY}`], { cwd, signal: stop });
	};
}

/**
 * The line every orchestrator's prompt and every message the hypervisor tells ends with: how to report back, to the
 * inbox of the store this hypervisor watches.
 */
export function reportBack(store: string): string {
	const tell = `HV_STORE=${quoted(store)} ${quoted(HV)} tell`;
	return `To report back to the hypervisor, the agent that keeps track of max's sessions, run \`${tell} "<what happened, and where max should look>"\` when you finish; it waits in the hypervisor's inbox. When you need max, run \`${tell} --ping "<what you need from him>"\`, which reaches it at once.`;
}

/** The live sessions, each with its tmux window where tmux lists its pane. */
export async function sessions(home: string): Promise<Session[]> {
	const [entries, windows] = await Promise.all([registry(home), panes()]);
	return entries.map((entry) => ({ ...entry, ...(entry.pane && windows.has(entry.pane) ? { window: windows.get(entry.pane) } : {}) }));
}

/**
 * The live sessions the registry of every Claude Code config directory in `home` lists (`.claude`, and any
 * `.claude-<profile>`), read from its files alone. An entry whose process is gone is left out: a session that crashed
 * leaves its file behind.
 */
export async function registry(home: string): Promise<Session[]> {
	const configs = await claudeConfigs(home);
	const files = (await Promise.all(configs.map(async (config) => (await readdir(path.join(home, config, "sessions")).catch(() => [])).filter((file) => /^\d+\.json$/.test(file)).map((file) => path.join(home, config, "sessions", file))))).flat();
	const read = await Promise.all(files.map((file) => readFile(file, "utf8").then(entry, () => undefined)));
	return read.filter((s): s is Session => s !== undefined && alive(s.pid));
}

/** The windows spawn opened, from the store, oldest first. A line that does not parse names no window. */
export function spawnedWindows(store: string): Promise<Spawned[]> {
	return lines<Spawned>(store, SPAWNED);
}

/**
 * The one session `wanted` names: its tmux window as `session:window`, the window alone, its Claude Code name, or its
 * pid. A name that fits none, or several, is refused with the candidates.
 */
export function find(live: Session[], wanted: string): Session {
	const names = (s: Session) => [s.window, s.window?.slice(s.window.indexOf(":") + 1), s.name, String(s.pid)];
	const matches = live.filter((s) => names(s).includes(wanted));
	if (matches.length === 1) return matches[0];
	const listed = (matches.length ? matches : live).map(label).join(", ") || "none";
	throw new Error(matches.length ? `"${wanted}" names several sessions: ${listed}` : `no live session is called "${wanted}"; live: ${listed}`);
}

/** A session as the tools name it: its window and its Claude Code name. */
export function label(s: Session): string {
	return s.window ? `${s.window} (${s.name})` : s.name;
}

/**
 * The line a session's inbox takes: a user message wrapped as Claude Code wraps a cross-session message, so it
 * arrives as one, from "hypervisor", with no address to reply to.
 *
 * `from-mode` is the sender's permission class, `prompting` or `bypass`. The receiving session delivers a message
 * whose class matches its own, or that names none while it prompts; it holds any other for max's approval. So a
 * session in auto mode, which Claude Code counts as prompting, takes this message at once, and one that bypasses
 * permissions holds it. The hypervisor says it prompts because it has no side effect of its own that no permission
 * classifier judges (decisions/0002).
 */
export function frame(text: string): string {
	const content = `<cross-session-message from-name="hypervisor" from-mode="prompting">\n${text}\n</cross-session-message>`;
	return `${JSON.stringify({ type: "user", message: { role: "user", content }, priority: "next" })}\n`;
}

/** `text` as a tmux name: runs of anything but letters, digits, `_` and `-` become one `-`, with none at its ends. */
export function slug(text: string): string {
	return text.replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^[-_]+|-+$/g, "");
}

/** Whether a process runs. */
function alive(pid: number): boolean {
	try {
		process.kill(pid, 0);
		return true;
	} catch (error) {
		return (error as NodeJS.ErrnoException).code === "EPERM";
	}
}

/** A session as `claude agents --json` prints it: an interactive one with its pid and `status`, a background one with its id and `state`. */
interface Agent {
	pid?: number;
	id?: string;
	name?: string;
	cwd?: string;
	status?: string;
	state?: string;
}

/** A registry entry as a session, or `undefined` when it lacks what one needs. */
function entry(text: string): Session | undefined {
	try {
		const e = JSON.parse(text);
		if (typeof e.pid !== "number" || typeof e.name !== "string" || typeof e.cwd !== "string" || typeof e.status !== "string") return undefined;
		return {
			pid: e.pid,
			name: e.name,
			cwd: e.cwd,
			status: e.status,
			...(typeof e.messagingSocketPath === "string" ? { socket: e.messagingSocketPath } : {}),
			...(typeof e.tmux === "string" && /%\d+$/.test(e.tmux) ? { pane: e.tmux.slice(e.tmux.lastIndexOf("%")) } : {}),
		};
	} catch {
		return undefined;
	}
}

/** Every tmux pane's window, as `session:window`; none when no tmux server runs. */
async function panes(): Promise<Map<string, string>> {
	const out = await run("tmux", ["list-panes", "-a", "-F", "#{pane_id}\t#{session_name}:#{window_name}"]).catch(() => "");
	return new Map(out.split("\n").flatMap((line) => (line.includes("\t") ? [line.split("\t", 2) as [string, string]] : [])));
}

/** A directory the model named, resolved. One with a `#` in its path is refused, since tmux reads its start directory as a format. */
async function directory(home: string, dir: string): Promise<string> {
	const where = await realpath(absolute(home, dir)).catch(() => undefined);
	if (!where || !(await stat(where)).isDirectory()) throw new Error(`${dir} is not a directory`);
	if (where.includes("#")) throw new Error(`${where}: a directory with # in its path cannot start a tmux window`);
	return where;
}

/**
 * The repo `dir` lies in: the nearest directory at or above it holding `.git`, and for a linked worktree, whose `.git`
 * is a file naming a directory under the main one's `.git/worktrees/`, that main worktree. `dir` itself when no
 * directory above it holds `.git`.
 */
export async function repo(dir: string): Promise<string> {
	for (let at = dir; ; at = path.dirname(at)) {
		const git = path.join(at, ".git");
		const info = await stat(git).catch(() => undefined);
		if (info?.isDirectory()) return at;
		if (info?.isFile()) {
			const linked = /^gitdir: (.*)\/\.git\/worktrees\/[^/]+\/?$/m.exec(await readFile(git, "utf8").catch(() => ""));
			return linked ? path.resolve(at, linked[1]) : at;
		}
		if (at === path.dirname(at)) return dir;
	}
}

/**
 * Whether Claude Code's config in `home` records its trust dialog accepted for `dir` or a directory above it, as
 * Claude Code itself looks it up before it takes a first prompt.
 */
async function trusted(home: string, dir: string): Promise<boolean> {
	const projects = await readFile(path.join(home, ".claude.json"), "utf8")
		.then((text) => JSON.parse(text).projects ?? {})
		.catch(() => ({}));
	for (let at = dir; ; at = path.dirname(at)) {
		if (projects[at]?.hasTrustDialogAccepted === true) return true;
		if (at === path.dirname(at)) return false;
	}
}

/** `text` as one word of a POSIX shell command. */
function quoted(text: string): string {
	return /^[\w./-]+$/.test(text) ? text : `'${text.replaceAll("'", `'\\''`)}'`;
}

function deliver(socket: string, line: string): Promise<void> {
	return new Promise((resolve, reject) => {
		const connection = createConnection(socket);
		connection.setTimeout(INBOX_MS, () => connection.destroy(new Error(`${socket}: no answer within ${INBOX_MS / 1000} s`)));
		connection.on("error", reject);
		connection.on("close", (failed) => (failed ? undefined : resolve()));
		connection.end(line);
	});
}
