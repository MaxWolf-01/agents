import { execFile } from "node:child_process";
import { appendFile, mkdir, readdir, readFile, stat } from "node:fs/promises";
import { createConnection } from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Where the session tools find things: max's home, Claude Code's config directory, and the hypervisor's store. */
export interface Places {
	home: string;
	/** Claude Code's config directory, whose `sessions/` lists every live session on this machine. */
	claude: string;
	store: string;
}

/** A live Claude Code session: its registry entry, and the tmux window its pane is in. */
export interface Session {
	pid: number;
	name: string;
	cwd: string;
	/** `busy`, `idle`, or whatever else Claude Code writes there. */
	status: string;
	startedAt: number;
	/** The inbox socket, where a cross-session message is delivered. */
	socket?: string;
	/** The tmux pane, as `%N`. */
	pane?: string;
	/** The tmux window, as `session:window`; unknown when tmux does not list the pane. */
	window?: string;
}

/** A window spawn opened, as `spawned.jsonl` in the store keeps it. */
export interface Spawned {
	at: string;
	pane: string;
	window: string;
	dir: string;
}

/** The `hv` script, which an orchestrator runs to report back. */
const HV = fileURLToPath(new URL("../../hv", import.meta.url));
const SPAWNED = "spawned.jsonl";
/** How long a delegated task runs before it is stopped. */
const DELEGATE_MS = 15 * 60_000;
/** How many lines of a pane `look` shows. */
const PANE_LINES = 50;

/** The line every orchestrator's brief and every message the hypervisor tells ends with. */
export const REPORT_BACK = `To report back to the hypervisor, the agent that keeps track of max's sessions, run \`${HV} tell "<what happened, and where max should look>"\`: when you finish, and when you need max.`;
const BRIEFLY = "Your answer goes back to the hypervisor, an agent that coordinates max's sessions and pays for every word it reads: answer with what it asked for and nothing else, as briefly as the answer allows.";

/**
 * Opens a tmux window named `name` in the tmux session of the repo at `dir`, running interactive Claude Code in auto
 * mode with `brief` as its first prompt. The repo's tmux session is started if it does not run yet.
 */
export async function spawn(places: Places, { dir, name, brief }: { dir: string; name: string; brief: string }): Promise<string> {
	const where = await directory(places.home, dir);
	const window = slug(name);
	const group = slug(path.basename(where));
	if (!window) throw new Error(`"${name}" leaves no window name; use letters, digits, - or _`);
	if (!brief.trim()) throw new Error("the brief is empty");
	const claude = ["claude", "--permission-mode", "auto", "--name", window, "--", `${brief.trim()}\n\n${REPORT_BACK}`];
	const running = await run("tmux", ["has-session", "-t", `=${group}`]).then(
		() => true,
		() => false,
	);
	if (running && (await run("tmux", ["list-windows", "-t", `=${group}`, "-F", "#{window_name}"])).split("\n").includes(window))
		throw new Error(`${group}:${window} exists already; look at it, or give the new one another name`);
	const at = ["-n", window, "-c", where, "-P", "-F", "#{pane_id}"];
	const opened = running ? ["new-window", "-d", "-t", `=${group}:`, ...at] : ["new-session", "-d", "-s", group, ...at];
	const pane = (await run("tmux", [...opened, ...claude])).trim();
	const spawned: Spawned = { at: new Date().toISOString(), pane, window: `${group}:${window}`, dir: where };
	await mkdir(places.store, { recursive: true });
	await appendFile(path.join(places.store, SPAWNED), `${JSON.stringify(spawned)}\n`);
	return `Started ${spawned.window} in ${where}. max steps in with: tmux switch-client -t ${pane || `=${group}:${window}`}`;
}

/** Sends `message` to a session's inbox socket, as a cross-session message from the hypervisor. */
export async function tell(places: Places, { session, message }: { session: string; message: string }): Promise<string> {
	if (!message.trim()) throw new Error("the message is empty");
	const target = find(await sessions(places), session);
	if (!target.socket) throw new Error(`${label(target)} has no inbox socket, so it cannot be messaged`);
	await deliver(target.socket, frame(`${message.trim()}\n\n${REPORT_BACK}`));
	return `Sent to ${label(target)}.`;
}

/** Every session `claude agents` lists, a line each; or one session's state and the tail of its pane. */
export async function look(places: Places, { session }: { session?: string }): Promise<string> {
	const live = await sessions(places);
	if (session === undefined) {
		const spawned = new Set((await spawnedWindows(places.store)).map((s) => s.pane));
		const agents = JSON.parse((await run("claude", ["agents", "--json"])).trim() || "[]") as Agent[];
		return agents.map((agent) => listed(agent, live.find((s) => s.pid === agent.pid), spawned, places.home)).join("\n");
	}
	const target = find(live, session);
	const head = `${label(target)} · ${target.status} · ${tilde(target.cwd, places.home)}`;
	if (!target.pane) return `${head}\n(no tmux pane)`;
	const pane = await run("tmux", ["capture-pane", "-p", "-J", "-t", target.pane, "-S", `-${PANE_LINES}`]);
	return `${head}\n${pane.replace(/\n{3,}/g, "\n\n").trimEnd()}`;
}

/** Runs `task` in a one-shot Claude Code session in auto mode, in `dir` or max's home, and returns its answer. */
export async function delegate(places: Places, { task, dir }: { task: string; dir?: string }, signal?: AbortSignal): Promise<string> {
	if (!task.trim()) throw new Error("the task is empty");
	const cwd = dir === undefined ? places.home : await directory(places.home, dir);
	const stop = AbortSignal.any([AbortSignal.timeout(DELEGATE_MS), ...(signal ? [signal] : [])]);
	return run("claude", ["-p", "--permission-mode", "auto", "--output-format", "text", "--", `${task.trim()}\n\n${BRIEFLY}`], { cwd, signal: stop });
}

/** The live sessions in Claude Code's registry, each with its tmux window where tmux lists its pane. */
export async function sessions(places: Pick<Places, "claude">): Promise<Session[]> {
	const [entries, windows] = await Promise.all([registry(path.join(places.claude, "sessions")), panes()]);
	return entries.map((entry) => ({ ...entry, ...(entry.pane && windows.has(entry.pane) ? { window: windows.get(entry.pane) } : {}) }));
}

/**
 * The live sessions Claude Code's registry lists, read from its files alone. An entry whose process is gone is left
 * out: a session that crashed leaves its file behind.
 */
export async function registry(dir: string): Promise<Session[]> {
	const files = (await readdir(dir).catch(() => [])).filter((file) => /^\d+\.json$/.test(file));
	const read = await Promise.all(files.map((file) => readFile(path.join(dir, file), "utf8").then(entry, () => undefined)));
	return read.filter((s): s is Session => s !== undefined && alive(s.pid));
}

/** The windows spawn opened, from the store, oldest first. */
export async function spawnedWindows(store: string): Promise<Spawned[]> {
	const text = await readFile(path.join(store, SPAWNED), "utf8").catch(() => "");
	return text.split("\n").flatMap((line) => {
		try {
			return line ? [JSON.parse(line) as Spawned] : [];
		} catch {
			return [];
		}
	});
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
 */
export function frame(text: string): string {
	const content = `<cross-session-message from-name="hypervisor">\n${text}\n</cross-session-message>`;
	return `${JSON.stringify({ type: "user", message: { role: "user", content }, priority: "next" })}\n`;
}

/** `text` as a tmux name: runs of anything but letters, digits, `_` and `-` become one `-`, with none at its ends. */
export function slug(text: string): string {
	return text.replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^[-_]+|-+$/g, "");
}

interface Agent {
	pid?: number;
	id?: string;
	name?: string;
	cwd?: string;
	kind?: string;
	status?: string;
	state?: string;
}

function listed(agent: Agent, session: Session | undefined, spawned: Set<string>, home: string): string {
	const where = session?.window ?? (session ? "no tmux" : "background");
	const mine = session?.pane && spawned.has(session.pane) ? " · spawned by you" : "";
	return [agent.name ?? agent.id ?? "?", agent.status ?? agent.state ?? "?", tilde(agent.cwd ?? "?", home), where].join(" · ") + mine;
}

function entry(text: string): Session | undefined {
	try {
		const e = JSON.parse(text);
		if (typeof e.pid !== "number") return undefined;
		return {
			pid: e.pid,
			name: String(e.name ?? e.pid),
			cwd: String(e.cwd ?? ""),
			status: String(e.status ?? "unknown"),
			startedAt: Number(e.startedAt ?? 0),
			...(typeof e.messagingSocketPath === "string" ? { socket: e.messagingSocketPath } : {}),
			...(typeof e.tmux === "string" && /%\d+$/.test(e.tmux) ? { pane: e.tmux.slice(e.tmux.lastIndexOf("%")) } : {}),
		};
	} catch {
		return undefined;
	}
}

function alive(pid: number): boolean {
	try {
		process.kill(pid, 0);
		return true;
	} catch (error) {
		return (error as NodeJS.ErrnoException).code === "EPERM";
	}
}

/** Every tmux pane's window, as `session:window`; none when no tmux server runs. */
async function panes(): Promise<Map<string, string>> {
	const out = await run("tmux", ["list-panes", "-a", "-F", "#{pane_id}\t#{session_name}:#{window_name}"]).catch(() => "");
	return new Map(out.split("\n").flatMap((line) => (line.includes("\t") ? [line.split("\t", 2) as [string, string]] : [])));
}

/**
 * A directory the model named, absolute, under `~/`, or relative to max's home. One with a `#` in its path is refused,
 * since tmux reads its start directory as a format.
 */
async function directory(home: string, dir: string): Promise<string> {
	const where = path.resolve(home, dir.replace(/^~(?=\/|$)/, home));
	if (where.includes("#")) throw new Error(`${where}: a directory with # in its path cannot start a tmux window`);
	const found = await stat(where).catch(() => undefined);
	if (!found?.isDirectory()) throw new Error(`${where} is not a directory`);
	return where;
}

function tilde(dir: string, home: string): string {
	return dir === home || dir.startsWith(`${home}/`) ? `~${dir.slice(home.length)}` : dir;
}

function deliver(socket: string, line: string): Promise<void> {
	return new Promise((resolve, reject) => {
		const connection = createConnection(socket);
		connection.setTimeout(5000, () => connection.destroy(new Error(`${socket}: no answer within 5 s`)));
		connection.on("error", reject);
		connection.on("close", (failed) => (failed ? undefined : resolve()));
		connection.end(line);
	});
}

/** Runs `program` without a shell and returns what it printed; a failure carries what it said on stderr. */
function run(program: string, args: string[], options: { cwd?: string; signal?: AbortSignal } = {}): Promise<string> {
	return new Promise((resolve, reject) => {
		execFile(program, args, { ...options, encoding: "utf8", maxBuffer: 16 << 20 }, (error, stdout, stderr) => {
			if (error) reject(new Error(`${program} ${args[0]}: ${String(stderr).trim() || error.message}`));
			else resolve(String(stdout));
		});
	});
}
