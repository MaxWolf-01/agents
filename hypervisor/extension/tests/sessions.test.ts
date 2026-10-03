// The session layer below the tools: what a message to a session's inbox looks like on the wire, how a session is
// found, what the watch makes of the registry, and the events and `hv tell` messages that reach the agent.

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readdirSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import fc from "fast-check";
import { entriesOf } from "../src/entries.ts";
import { eventMessage, eventsIn } from "../src/events.ts";
import { post, take } from "../src/inbox.ts";
import { find, frame, registry, type Session, slug, tell } from "../src/sessions.ts";
import { changes, type Seen, watched } from "../src/watch.ts";

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-sessions-")));
after(() => rmSync(dir, { recursive: true, force: true }));

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

const session = (pid: number, name: string, window?: string): Session => ({ pid, name, cwd: "/r", status: "idle", startedAt: 0, ...(window ? { window } : {}) });
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

test("the registry lists live sessions only, with the pane its tmux field names", async () => {
	const sessions = path.join(dir, "registry");
	mkdirSync(sessions);
	const entry = (pid: number, extra = {}) => writeFileSync(path.join(sessions, `${pid}.json`), JSON.stringify({ pid, name: `s${pid}`, cwd: "/r", status: "busy", startedAt: 5, ...extra }));
	entry(process.pid, { tmux: "agents:@3.%17", messagingSocketPath: "/run/x.sock" });
	entry(2 ** 22 + 1); // no such process
	writeFileSync(path.join(sessions, "3.key"), "not an entry");
	writeFileSync(path.join(sessions, "4.json"), "{ half");
	assert.deepEqual(await registry(sessions), [{ pid: process.pid, name: `s${process.pid}`, cwd: "/r", status: "busy", startedAt: 5, socket: "/run/x.sock", pane: "%17" }]);
});

test("tell writes the framed message to the session's inbox socket", async () => {
	const claude = path.join(dir, "claude");
	mkdirSync(path.join(claude, "sessions"), { recursive: true });
	const socket = path.join(dir, "inbox.sock");
	const received: string[] = [];
	const server = createServer((c) => c.on("data", (d) => received.push(d.toString())));
	await new Promise<void>((resolve) => server.listen(socket, resolve));
	writeFileSync(path.join(claude, "sessions", `${process.pid}.json`), JSON.stringify({ pid: process.pid, name: "orch-1", cwd: dir, status: "idle", messagingSocketPath: socket }));
	try {
		assert.equal(await tell({ home: dir, claude, store: dir }, { session: "orch-1", message: "max says: ship it" }), "Sent to orch-1.");
		await new Promise((settle) => setTimeout(settle, 50));
		const body = ENVELOPE.exec(JSON.parse(received.join("")).message.content)![7];
		assert.match(body, /^max says: ship it\n\nTo report back to the hypervisor, .*\/hv tell "/);
	} finally {
		server.close();
	}
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
	]);
	const now = new Map([
		[1, seen("idle")],
		[2, seen("busy", "agents:x")],
		[4, seen("busy", "agents:z")],
		[5, seen("idle", "agents:w")],
		[6, seen("idle", "agents:new")],
	]);
	assert.deepEqual(changes(before, now), ["agents:board: busy → idle", "agents:y: busy → ended"]);
});

test("a session is watched when it runs in a pane spawn opened, started no earlier than that window", () => {
	const at = "2026-10-04T10:00:00.000Z";
	const t = Date.parse(at);
	const spawned = [{ at, pane: "%5", window: "agents:board", dir: "/r" }];
	const live = [
		{ pid: 1, pane: "%5", status: "busy", startedAt: t + 2000 },
		{ pid: 2, pane: "%5", status: "busy", startedAt: t - 3_600_000 }, // an older pane of the same number
		{ pid: 3, pane: "%6", status: "busy", startedAt: t + 2000 },
		{ pid: 4, status: "busy", startedAt: t + 2000 },
	];
	assert.deepEqual([...watched(live, spawned)], [[1, seen("busy")]]);
});

test("the inbox hands over each message once, oldest first", async () => {
	const store = path.join(dir, "store");
	for (const text of ["first", "second", "third"]) await post(store, { at: "t", from: "agents:board", text });
	writeFileSync(path.join(store, "inbox", "0-broken.json"), "{");
	assert.deepEqual((await take(store)).map((t) => t.text), ["first", "second", "third"]);
	assert.deepEqual(readdirSync(path.join(store, "inbox")), []);
	assert.deepEqual(await take(store), []);
});
