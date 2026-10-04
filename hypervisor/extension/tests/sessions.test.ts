// The session layer: what a message to a session's inbox looks like on the wire, how a session is found, what spawn,
// look and delegate start, what the watch makes of the registry, and the events and `hv tell` messages that reach the
// agent. tmux and claude are stand-ins on PATH that record how they were called and answer as this file says.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, beforeEach, test } from "node:test";
import fc from "fast-check";
import { entriesOf } from "../src/entries.ts";
import { eventMessage, eventsIn } from "../src/events.ts";
import { post, type Told, take } from "../src/inbox.ts";
import { delegate, find, frame, look, registry, reportBack, type Session, slug, spawn, spawnedWindows, tell } from "../src/sessions.ts";
import { changes, type Seen, watch, watched } from "../src/watch.ts";

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-sessions-")));
after(() => rmSync(dir, { recursive: true, force: true }));

const bin = path.join(dir, "bin");
const calls = path.join(dir, "calls.jsonl");
const answers = path.join(dir, "answers.json");
mkdirSync(bin);
for (const program of ["tmux", "claude"]) {
	const file = path.join(bin, program);
	writeFileSync(
		file,
		`#!${process.execPath}
const fs = require("node:fs");
const argv = process.argv.slice(2);
fs.appendFileSync(${JSON.stringify(calls)}, JSON.stringify({ program: ${JSON.stringify(program)}, argv, cwd: process.cwd() }) + "\\n");
const said = JSON.parse(fs.readFileSync(${JSON.stringify(answers)}, "utf8"))[${JSON.stringify(program)} + " " + argv[0]] ?? { out: "" };
process.stdout.write(said.out ?? "");
process.exit(said.code ?? 0);
`,
	);
	chmodSync(file, 0o755);
}
process.env.PATH = `${bin}:${process.env.PATH}`;

/** Sets what the stand-ins answer, by program and first argument, and forgets earlier calls. */
function answering(said: Record<string, { out?: string; code?: number }>) {
	writeFileSync(answers, JSON.stringify(said));
	rmSync(calls, { force: true });
}
const called = (): { program: string; argv: string[]; cwd: string }[] =>
	readFileSync(calls, "utf8")
		.trim()
		.split("\n")
		.map((line) => JSON.parse(line));
beforeEach(() => answering({}));

/** A home of its own, with a repo directory in it, an empty store, and Claude Code trusted in the whole home. */
function home() {
	const at = mkdtempSync(path.join(dir, "home-"));
	mkdirSync(path.join(at, "my.repo"));
	writeFileSync(path.join(at, ".claude.json"), JSON.stringify({ projects: { [at]: { hasTrustDialogAccepted: true } } }));
	return { home: at, store: path.join(at, "store"), repo: path.join(at, "my.repo") };
}

// Claude Code 2.1.288's own reading of a cross-session message, transcribed from its bundle: the envelope's optional
// attributes in their fixed order, then the body on the lines between the tags.
const ENVELOPE =
	/^<cross-session-message(?: from="([A-Za-z0-9%:_/.\\-]+)")?(?: from-session="([A-Za-z0-9_-]{1,80})")?(?: hop-chain="([0-9a-f,]+)")?(?: from-name="([^"<>\n\r]+)")?(?: from-mode="(bypass|prompting)")?(?: from-plugin="([^"<>\n\r]+)")?>\n([\s\S]*)\n<\/cross-session-message>$/;

test("a message to a session's inbox is one line, a user message Claude Code reads as a cross-session message from the hypervisor", () => {
	fc.assert(
		fc.property(fc.string({ unit: "binary" }), (text) => {
			const line = frame(text);
			assert.equal(line.indexOf("\n"), line.length - 1, "one line, newline-terminated");
			const sent = JSON.parse(line);
			assert.equal(sent.type, "user");
			assert.equal(sent.priority, "next", "queued for the session's next turn, as Claude Code's own sends are");
			const parsed = ENVELOPE.exec(sent.message.content);
			assert.ok(parsed, "the envelope parses");
			assert.equal(parsed[4], "hypervisor");
			assert.equal(parsed[1], undefined, "no reply address");
			assert.equal(parsed[5], undefined, "no permission class, so a prompting session delivers it");
			assert.equal(parsed[7], text);
		}),
	);
});

test("a window name is letters, digits, - and _, starting with neither - nor _", () => {
	assert.equal(slug("hypervisor-orchestrators"), "hypervisor-orchestrators");
	assert.equal(slug(".dotfiles"), "dotfiles");
	assert.equal(slug("fix the #(rm) bug!"), "fix-the-rm-bug");
	assert.equal(slug("--settings"), "settings");
	fc.assert(fc.property(fc.string(), (text) => assert.match(slug(text), /^([A-Za-z0-9][A-Za-z0-9_-]*)?$/)));
});

test("spawn starts the repo's tmux session with the window, runs claude in auto mode with the brief, and records the window", async () => {
	const { home: at, store, repo } = home();
	answering({ "tmux has-session": { code: 1 }, "tmux new-session": { out: "%5 4242\n" } });
	assert.equal(await spawn({ home: at, store }, { dir: "my.repo", name: "board fix", brief: " fix the board " }), `Started my-repo:board-fix in ${repo}. max steps in with: tmux switch-client -t %5`);
	const opened = called().find((c) => c.argv[0] === "new-session")!;
	assert.deepEqual(opened.argv, ["new-session", "-d", "-s", "my-repo", "-n", "board-fix", "-c", repo, "-P", "-F", "#{pane_id} #{pane_pid}", "claude", "--permission-mode", "auto", "--name", "board-fix", "--", `fix the board\n\n${reportBack(store)}`]);
	assert.deepEqual(
		(await spawnedWindows(store)).map(({ at: _, ...w }) => w),
		[{ pane: "%5", pid: 4242, window: "my-repo:board-fix", dir: repo }],
	);
});

test("spawn opens a window in a repo session that runs, and refuses a window name it already has", async () => {
	const { home: at, store, repo } = home();
	answering({ "tmux list-windows": { out: "zsh\nother\n" }, "tmux new-window": { out: "%9 77\n" } });
	await spawn({ home: at, store }, { dir: repo, name: "board-fix", brief: "b" });
	assert.deepEqual(called().find((c) => c.argv[0] === "new-window")!.argv.slice(0, 5), ["new-window", "-d", "-t", "=my-repo:", "-n"]);
	answering({ "tmux list-windows": { out: "zsh\nboard-fix\n" } });
	await assert.rejects(spawn({ home: at, store }, { dir: repo, name: "board-fix", brief: "b" }), /my-repo:board-fix exists already/);
	assert.ok(!called().some((c) => c.argv[0] === "new-window"));
	await assert.rejects(spawn({ home: at, store }, { dir: "nowhere", name: "x", brief: "b" }), /nowhere is not a directory/);
});

test("spawn names the tmux session for the repo the directory lies in, a linked worktree's for its main one", async () => {
	const { home: at, store, repo } = home();
	mkdirSync(path.join(repo, ".git", "worktrees", "wt"), { recursive: true });
	mkdirSync(path.join(repo, "sub", "deeper"), { recursive: true });
	const worktree = path.join(at, "my.repo-ticket");
	mkdirSync(worktree);
	writeFileSync(path.join(worktree, ".git"), `gitdir: ${repo}/.git/worktrees/wt\n`);
	const plain = path.join(at, "notes");
	mkdirSync(plain);
	for (const [where, session] of [[path.join(repo, "sub", "deeper"), "my-repo"], [worktree, "my-repo"], [plain, "notes"]]) {
		answering({ "tmux has-session": { code: 1 }, "tmux new-session": { out: "%5 4242\n" } });
		await spawn({ home: at, store }, { dir: where, name: "w", brief: "b" });
		const opened = called().find((c) => c.argv[0] === "new-session")!.argv;
		assert.equal(opened[opened.indexOf("-s") + 1], session, where);
		assert.equal(opened[opened.indexOf("-c") + 1], where, "claude runs where it was asked to");
	}
});

test("spawn says when Claude Code has never been trusted where it starts, since its trust dialog then holds the brief", async () => {
	const { home: at, store, repo } = home();
	answering({ "tmux has-session": { code: 1 }, "tmux new-session": { out: "%5 4242\n" } });
	assert.doesNotMatch(await spawn({ home: at, store }, { dir: repo, name: "w", brief: "b" }), /trust/, "a directory below a trusted one is trusted");
	writeFileSync(path.join(at, ".claude.json"), JSON.stringify({ projects: { [at]: { hasTrustDialogAccepted: false }, [path.join(at, "other")]: { hasTrustDialogAccepted: true } } }));
	answering({ "tmux has-session": { code: 1 }, "tmux new-session": { out: "%5 4242\n" } });
	assert.match(await spawn({ home: at, store }, { dir: repo, name: "w", brief: "b" }), /\nClaude Code has no record of being trusted in ~\/my\.repo, so its trust dialog may hold the brief until max accepts it in that window\.$/);
	rmSync(path.join(at, ".claude.json"));
	answering({ "tmux has-session": { code: 1 }, "tmux new-session": { out: "%5 4242\n" } });
	assert.match(await spawn({ home: at, store }, { dir: repo, name: "w", brief: "b" }), /trust dialog may hold the brief/, "no config at all");
});

/** A registry entry for `pid` in `home`'s Claude Code config directory `config`. */
function registered(at: string, pid: number, fields: object, config = ".claude") {
	mkdirSync(path.join(at, config, "sessions"), { recursive: true });
	writeFileSync(path.join(at, config, "sessions", `${pid}.json`), JSON.stringify({ pid, cwd: at, status: "idle", ...fields }));
}

test("look lists what claude agents lists, the sessions of other config directories after it, and marks the ones spawn opened", async () => {
	const { home: at, store, repo } = home();
	const child = spawnSync(process.execPath, ["-e", "0"]); // a pid that is not alive: its entry is left out
	registered(at, process.pid, { name: "orch-1", cwd: repo, tmux: "my-repo:@1.%5" });
	registered(at, process.ppid, { name: "work-6a", status: "busy" }, ".claude-work");
	registered(at, child.pid!, { name: "gone" });
	mkdirSync(store);
	writeFileSync(path.join(store, "spawned.jsonl"), `${JSON.stringify({ at: "t", pane: "%5", pid: process.pid, window: "my-repo:board-fix", dir: repo })}\n`);
	const agents = [
		{ pid: process.pid, cwd: repo, kind: "interactive", name: "orch-1", status: "idle" },
		{ id: "38c26b54", cwd: "/elsewhere", kind: "background", name: "fix tikz", state: "blocked" },
	];
	answering({ "claude agents": { out: JSON.stringify(agents) }, "tmux list-panes": { out: "%5\tmy-repo:board-fix\n" } });
	assert.equal(
		await look({ home: at, store }, {}),
		["orch-1 · idle · ~/my.repo · my-repo:board-fix · spawned by you", "fix tikz · blocked · /elsewhere · background", "work-6a · busy · ~ · no tmux"].join("\n"),
	);
	answering({ "tmux list-panes": { out: "%5\tmy-repo:board-fix\n" }, "tmux capture-pane": { out: "● READY\n\n\n\n❯\n\n" } });
	assert.equal(await look({ home: at, store }, { session: "board-fix" }), "my-repo:board-fix (orch-1) · idle · ~/my.repo\n● READY\n\n❯");
	assert.deepEqual(called().find((c) => c.argv[0] === "capture-pane")!.argv, ["capture-pane", "-p", "-J", "-t", "%5", "-S", "-50"]);
});

test("delegate runs claude -p in auto mode, in the directory given or home, and answers with what it printed", async () => {
	const { home: at, store, repo } = home();
	answering({ "claude -p": { out: "4\n" } });
	assert.equal(await delegate({ home: at, store }, { task: "2 + 2?", dir: "~/my.repo" }), "4\n");
	await delegate({ home: at, store }, { task: "2 + 2?" });
	const [inRepo, inHome] = called();
	assert.deepEqual(inRepo.argv.slice(0, 6), ["-p", "--permission-mode", "auto", "--output-format", "text", "--"]);
	assert.match(inRepo.argv[6], /^2 \+ 2\?\n\nYour answer goes back to the hypervisor/);
	assert.deepEqual([inRepo.cwd, inHome.cwd], [repo, at]);
});

const session = (pid: number, name: string, window?: string): Session => ({ pid, name, cwd: "/r", status: "idle", ...(window ? { window } : {}) });
const live = [session(11, "agents-31", "agents:hypervisor-orchestrators"), session(12, "agents-46", "agents:board"), session(13, "dotfiles-c1", "dotfiles:board"), session(14, "bg-run")];

test("a session is found by its window, the window alone, its name, or its pid; an ambiguous or unknown name is refused", () => {
	assert.equal(find(live, "agents:hypervisor-orchestrators").pid, 11);
	assert.equal(find(live, "hypervisor-orchestrators").pid, 11);
	assert.equal(find(live, "agents-46").pid, 12);
	assert.equal(find(live, "dotfiles:board").pid, 13);
	assert.equal(find(live, "14").pid, 14);
	assert.throws(() => find(live, "board"), /names several sessions: agents:board \(agents-46\), dotfiles:board \(dotfiles-c1\)/);
	assert.throws(() => find(live, "nope"), /no live session is called "nope"/);
});

test("the registry lists the live sessions of every Claude Code config directory, with the pane its tmux field names", async () => {
	const { home: at } = home();
	registered(at, process.pid, { name: "a", status: "busy", tmux: "agents:@3.%17", messagingSocketPath: "/run/x.sock" });
	registered(at, process.ppid, { name: "b" }, ".claude-work");
	registered(at, 2 ** 22 + 1, { name: "no such process" });
	registered(at, 7, { status: "idle" }, ".claude-work"); // no name
	registered(at, 8, { name: "elsewhere" }, ".config");
	writeFileSync(path.join(at, ".claude", "sessions", "3.key"), "not an entry");
	writeFileSync(path.join(at, ".claude", "sessions", "4.json"), "{ half");
	assert.deepEqual(
		(await registry(at)).sort((x, y) => x.name.localeCompare(y.name)),
		[
			{ pid: process.pid, name: "a", cwd: at, status: "busy", socket: "/run/x.sock", pane: "%17" },
			{ pid: process.ppid, name: "b", cwd: at, status: "idle" },
		],
	);
});

test("tell writes the framed message to the session's inbox socket", async () => {
	const { home: at, store } = home();
	const socket = path.join(at, "inbox.sock");
	const received: string[] = [];
	const server = createServer((c) => c.on("data", (d) => received.push(d.toString())));
	await new Promise<void>((resolve) => server.listen(socket, resolve));
	registered(at, process.pid, { name: "orch-1", messagingSocketPath: socket });
	try {
		assert.equal(await tell({ home: at, store }, { session: "orch-1", message: "max says: ship it" }), "Sent to orch-1.");
		await new Promise((settle) => setTimeout(settle, 50));
		const body = ENVELOPE.exec(JSON.parse(received.join("")).message.content)![7];
		assert.equal(body, `max says: ship it\n\n${reportBack(store)}`);
	} finally {
		server.close();
	}
});

test("the report-back line runs hv tell on the store this hypervisor watches, quoted for a shell", () => {
	assert.match(reportBack("/home/max/.local/share/hypervisor"), /run `HV_STORE=\/home\/max\/\.local\/share\/hypervisor \S+\/hypervisor\/hv tell "<what happened/);
	assert.match(reportBack("/tmp/it's here"), /HV_STORE='\/tmp\/it'\\''s here' /);
});

test("hv tell leaves its words in the store's inbox, from the directory it ran in outside tmux; without a store it refuses", async () => {
	const { store, repo } = home();
	const script = path.resolve(import.meta.dirname, "../src/hv-tell.ts");
	const { TMUX_PANE: _, ...env } = process.env;
	const ran = spawnSync(process.execPath, [script, "done,", "see", "the ticket"], { cwd: repo, env: { ...env, HV_STORE: store }, encoding: "utf8" });
	assert.equal(ran.status, 0, ran.stderr);
	let told: Told[] = [];
	await take(store, (t) => (told = t));
	assert.deepEqual(told.map(({ at: _, ...t }) => t), [{ from: repo, text: "done, see the ticket" }]);
	const unset = spawnSync(process.execPath, [script, "hello"], { cwd: repo, env, encoding: "utf8" });
	assert.equal(unset.status, 2);
	assert.match(unset.stderr, /HV_STORE is not set/);
});

test("an event message holds its events, whatever they say", () => {
	const event = fc.string({ minLength: 1 }).filter((e) => !e.includes("</event>"));
	fc.assert(fc.property(fc.array(event, { minLength: 1, maxLength: 4 }), (events) => assert.deepEqual(eventsIn(eventMessage(events)), events)));
	assert.deepEqual(eventsIn(eventMessage(["a\n</event>\n<event>\nb"])), ["a\n</ event>\n<event>\nb"], "an event cannot end its block early");
	assert.equal(eventsIn("max: <event>\nx\n</event>"), undefined);
	assert.equal(eventsIn("hello"), undefined);
});

test("each event is an entry of its own, spoken by the event and not by max", () => {
	const content = eventMessage(["agents:board: busy → idle", "agents:board (hv tell): done, see the ticket"]);
	assert.deepEqual(
		entriesOf([{ role: "user", content, timestamp: 1 }]).map((e) => e.text),
		["event: agents:board: busy → idle", "event: agents:board (hv tell): done, see the ticket"],
	);
});

const seen = (status: string, window = "agents:board"): Seen => ({ status, window });

test("a watched session's turn ending, or the session going, is an event; any other change is not", () => {
	const before = new Map([
		[1, seen("busy")],
		[2, seen("idle", "agents:x")],
		[3, seen("busy", "agents:y")],
		[4, seen("busy", "agents:z")],
		[5, seen("idle", "agents:w")],
		[7, seen("idle", "agents:v")],
		[8, seen("busy", "agents:u")],
	]);
	const now = new Map([
		[1, seen("idle")],
		[2, seen("busy", "agents:x")],
		[4, seen("busy", "agents:z")],
		[5, seen("idle", "agents:w")],
		[6, seen("idle", "agents:new")],
		[8, seen("waiting", "agents:u")],
	]);
	assert.deepEqual(changes(before, now), ["agents:board: busy → idle", "agents:y: busy → ended", "agents:v: idle → ended", "agents:u: busy → waiting"]);
});

test("a session is watched when it is the claude a spawned window was opened running, and no other in its pane", () => {
	const spawned = [
		{ at: "t", pane: "%5", pid: 1, window: "agents:board", dir: "/r" },
		{ at: "t", pane: "%6", pid: 9, window: "agents:gone", dir: "/r" },
	];
	const live = [
		{ pid: 1, status: "busy" },
		{ pid: 2, status: "busy" }, // a claude -p the orchestrator started, in the same pane
		{ pid: 3, status: "idle" },
	];
	assert.deepEqual([...watched(live, spawned)], [[1, seen("busy")]]);
});

test("the inbox hands over each message once, oldest first, and keeps them when taking them fails", async () => {
	const { store } = home();
	for (const text of ["first", "second", "third"]) await post(store, { at: "t", from: "agents:board", text });
	writeFileSync(path.join(store, "inbox", "0-broken.json"), "{");
	await assert.rejects(
		take(store, () => {
			throw new Error("not now");
		}),
	);
	let texts: string[] = [];
	await take(store, (told) => (texts = told.map((t) => t.text)));
	assert.deepEqual(texts, ["first", "second", "third"]);
	assert.deepEqual(readdirSync(path.join(store, "inbox")), []);
	await take(store, (told) => (texts = told.map((t) => t.text)));
	assert.deepEqual(texts, []);
});

/** A watch over `home`'s registry and store whose looks are this test's to start, delivering into `delivered`. */
function watching(at: string, store: string, ready = () => true) {
	const delivered: string[][] = [];
	const failures: unknown[] = [];
	const w = watch({ home: at, store }, 2 ** 30, (events) => delivered.push(events), (error) => failures.push(error), ready);
	return { ...w, delivered, failures, settled: () => new Promise((settle) => setTimeout(settle, 100)) };
}

/** A home whose registry holds this process as the claude a spawned window runs, in `status`. */
function spawnedHere(status: string) {
	const { home: at, store } = home();
	registered(at, process.pid, { name: "orch-1", status });
	mkdirSync(store);
	writeFileSync(path.join(store, "spawned.jsonl"), `${JSON.stringify({ at: "t", pane: "%5", pid: process.pid, window: "my-repo:board-fix", dir: at })}\n`);
	return { home: at, store, entry: path.join(at, ".claude", "sessions", `${process.pid}.json`) };
}

test("the watch takes a registry file caught mid-write for no change, and a live session's turn ending for one", async () => {
	const { home: at, store, entry } = spawnedHere("busy");
	const w = watching(at, store);
	try {
		await w.settled();
		writeFileSync(entry, "{");
		await w.look();
		assert.deepEqual(w.delivered, [], "the session's process lives, so it has not ended");
		registered(at, process.pid, { name: "orch-1", status: "idle" });
		await w.look();
		assert.deepEqual(w.delivered, [["my-repo:board-fix: busy → idle"]]);
	} finally {
		w.stop();
	}
});

test("the watch holds its events while pi cannot take them, the inbox untouched, and hands them over once it can", async () => {
	const { home: at, store } = spawnedHere("busy");
	let ready = false;
	const w = watching(at, store, () => ready);
	try {
		await w.settled();
		registered(at, process.pid, { name: "orch-1", status: "idle" });
		await post(store, { at: "t", from: "my-repo:board-fix", text: "done" });
		await w.look();
		assert.deepEqual(w.delivered, []);
		assert.equal(readdirSync(path.join(store, "inbox")).length, 1);
		assert.deepEqual(w.failures, [], "holding is not a failure");
		ready = true;
		await w.look();
		assert.deepEqual(w.delivered, [["my-repo:board-fix: busy → idle", "my-repo:board-fix (hv tell): done"]]);
		await w.look();
		assert.equal(w.delivered.length, 1, "each event once");
	} finally {
		w.stop();
	}
});

test("a look whose delivery fails leaves its events for the next look, and two looks at once deliver once", async () => {
	const { home: at, store } = spawnedHere("busy");
	const delivered: string[][] = [];
	let refuse = true;
	const failures: unknown[] = [];
	const w = watch(
		{ home: at, store },
		2 ** 30,
		(events) => {
			if (refuse) throw new Error("not now");
			delivered.push(events);
		},
		(error) => failures.push(error),
	);
	try {
		await new Promise((settle) => setTimeout(settle, 100));
		registered(at, process.pid, { name: "orch-1", status: "idle" });
		await w.look();
		assert.equal(failures.length, 1);
		refuse = false;
		await Promise.all([w.look(), w.look()]);
		assert.deepEqual(delivered, [["my-repo:board-fix: busy → idle"]]);
	} finally {
		w.stop();
	}
});
