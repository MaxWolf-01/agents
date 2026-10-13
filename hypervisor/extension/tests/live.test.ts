// The live hypervisor's extension, loaded beside stand-ins for pi-optchat's tools: which tools end up active, and how
// what an orchestrator reports reaches OptChat.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, readlinkSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { post, waiting } from "../src/inbox.ts";
import { live, MEMORY } from "../src/live.ts";
import { MODEL } from "../src/pi.ts";
import { load } from "./properties/stand-in.ts";

const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-home-")));
const stores: string[] = [];
/** A store of the test's own, so no test reads what another left in its inbox. */
function newStore() {
	stores.push(realpathSync(mkdtempSync(path.join(tmpdir(), "hv-store-"))));
	return stores.at(-1)!;
}
after(() => {
	for (const dir of [home, ...stores]) rmSync(dir, { recursive: true, force: true });
});

/** pi-optchat's tools by name, as the fork registers them: `spawn` and `tell` start and steer pi subagents with pi's coding tools. */
const OPTCHAT = ["zoom", "date", "spawn", "tell", "search"];
function optchat(pi: ExtensionAPI) {
	for (const name of OPTCHAT) pi.registerTool({ name, label: name, description: name, parameters: {} as never, execute: async () => ({ content: [], details: undefined }) });
}

/** The extension loaded after OptChat's tools, with pi's event bus answering each report with `takes()`. */
async function loaded(takes: () => boolean, store = newStore()) {
	const reports: { channel: string; text: string }[] = [];
	const listeners = new Map<string, (data: unknown) => void>();
	const bus = {
		emit: (channel: string, data: { text: string; taken?: boolean }) => {
			reports.push({ channel, text: data.text });
			if (takes()) data.taken = true;
		},
		on: (channel: string, listener: (data: unknown) => void) => {
			listeners.set(channel, listener);
			return () => listeners.delete(channel);
		},
	};
	const extension = await load((pi) => {
		optchat(pi);
		live({ store, home })(new Proxy(pi, { get: (target, key) => (key === "events" ? bus : target[key as keyof ExtensionAPI]) }));
	}, home);
	/** The lines the extension adds when OptChat asks for the status line, as OptChat builds a request. */
	const status = () => {
		const data = { lines: [] as string[] };
		listeners.get("optchat:status")?.(data);
		return data.lines;
	};
	const stop = async () => {
		for (const handler of extension.handlers.get("session_shutdown") ?? []) await handler({ type: "session_shutdown" }, extension.context);
	};
	return { ...extension, reports, status, stop };
}

test("lifelong-hypervisor#P4: the live set is OptChat's zoom and date, the session tools, the inbox, wait and the explorer's read tools, and OptChat's subagent tools are inactive", async () => {
	const { active, stop } = await loaded(() => true);
	await stop();
	const SESSIONS = ["start_session", "tell_session", "look", "delegate"];
	const READ = ["read", "ls", "find", "grep", "memex"];
	assert.deepEqual([...active].sort(), [...MEMORY, ...SESSIONS, "inbox", "wait", ...READ].sort());
});

test("a plain hv tell starts no turn and is listed on the status line; a ping goes to OptChat as a report, and stays in the inbox until OptChat takes it", async () => {
	const store = newStore();
	const at = new Date().toISOString();
	await post(store, { at, from: "agents:board-fix", text: "done, see the ticket", via: "hv tell" });
	await post(store, { at, from: "agents:board-fix", text: "the migration needs max", ping: true, via: "hv tell" });
	const { reports, status, stop } = await loaded(() => false, store);
	try {
		await new Promise((settle) => setTimeout(settle, 100));
		assert.deepEqual(reports, [{ channel: "optchat:report", text: "[agents:board-fix] hv tell: the migration needs max" }]);
		assert.equal(waiting(store).length, 2, "nothing took the ping: the inbox keeps it for the next look");
		assert.deepEqual(status(), ["Unread in your inbox: agents:board-fix 1 message, 20 B, 0m old."], "the ping is not listed: it is on its way");
	} finally {
		await stop();
	}
});

test("a ping OptChat takes leaves the inbox for read/", async () => {
	const store = newStore();
	await post(store, { at: new Date().toISOString(), from: "agents:board-fix", text: "the migration needs max", ping: true, via: "hv tell" });
	const { reports, stop } = await loaded(() => true, store);
	try {
		await new Promise((settle) => setTimeout(settle, 100));
		assert.equal(reports.length, 1);
		assert.deepEqual(waiting(store), []);
		assert.equal(readdirSync(path.join(store, "inbox", "read")).length, 1);
	} finally {
		await stop();
	}
});

test("the inbox tool lists what waits without its text, and reads one message or all from a sender as work, out of the inbox", async () => {
	const store = newStore();
	const { tools, stop } = await loaded(() => false, store);
	await stop();
	const inbox = tools.get("inbox")!;
	const call = (params: object) => inbox.execute("call", params as never, undefined, undefined, undefined as never);
	const at = new Date().toISOString();
	for (const [from, text] of [["agents:a", "a's first"], ["agents:b", "b's only"], ["agents:a", "a's second"]]) await post(store, { at, from, text, via: "hv tell" });
	const listed = textOf(await call({}));
	assert.doesNotMatch(listed, /first|only|second/, "the listing holds no message's text");
	const ids = waiting(store).map((m) => m.id);
	for (const id of ids) assert.match(listed, new RegExp(id));
	const one = await call({ id: ids[1] });
	const sent = `(sent ${at.slice(0, 16)}Z)`;
	assert.equal(textOf(one), `[agents:b] hv tell: b's only ${sent}`);
	assert.deepEqual(one.details, { optchat: "work" }, "pi-optchat logs it as work");
	assert.equal(textOf(await call({ from: "agents:a" })), `[agents:a] hv tell: a's first ${sent}\n\n[agents:a] hv tell: a's second ${sent}`);
	assert.deepEqual(waiting(store), []);
	assert.equal(readdirSync(path.join(store, "inbox", "read")).length, 3);
	assert.match(textOf(await call({ id: ids[1] })), /No unread message with id/);
	assert.equal(readdirSync(path.join(store, "inbox", "read")).length, 3, "a message is read once");
});

const textOf = (result: { content: { type: string; text?: string }[] }) => result.content.map((c) => c.text ?? "").join("");

test("hv starts pi in tmux with the fork's OptChat and this extension, on the profile, its turns cached for an hour", () => {
	const at = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-launch-")));
	try {
		const bin = path.join(at, "bin"), fork = path.join(at, "fork"), hvStore = path.join(at, "store"), calls = path.join(at, "tmux.calls");
		for (const dir of [bin, path.join(fork, "src"), path.join(hvStore, "optchat", "profiles", "hv")]) mkdirSync(dir, { recursive: true });
		writeFileSync(path.join(fork, "src", "index.ts"), "");
		const instructions = path.join(hvStore, "optchat", "profiles", "hv", "AGENTS.md");
		writeFileSync(instructions, "the instructions as an earlier start copied them");
		// A tmux whose server runs no session yet: it records each call, one argument a line, and refuses has-session.
		writeFileSync(path.join(bin, "tmux"), `#!/bin/sh\nprintf '%s\\n' "$@" '--' >> "${calls}"\n[ "$1" = has-session ] && exit 1\nexit 0\n`, { mode: 0o755 });
		const env = { PATH: `${bin}:${process.env.PATH}`, HOME: at, HV_STORE: hvStore, OPTCHAT_FORK: fork, ANTHROPIC_OAUTH_TOKEN: "token" };
		const ran = spawnSync(path.resolve(import.meta.dirname, "../../hv"), [], { env, encoding: "utf8" });
		assert.equal(ran.status, 0, ran.stderr);
		const started = readFileSync(calls, "utf8").split("--\n").map((call) => call.trimEnd().split("\n")).find((args) => args[0] === "new-session");
		assert.ok(started, "hv opens a tmux session");
		const after = (flag: string) => started.flatMap((arg, i) => (started[i - 1] === flag ? [arg] : []));
		assert.deepEqual(after("-e").filter((e) => !e.includes("=")), [path.resolve(import.meta.dirname, "../src/live.ts"), path.join(fork, "src", "index.ts")], "the extensions, this one first, so OptChat journals max's message with its path line");
		assert.ok(after("-e").includes("PI_CACHE_RETENTION=long"));
		assert.deepEqual(after("--optchat-profile"), ["hv"]);
		assert.deepEqual(after("--model"), [MODEL]);
		for (const off of ["--no-extensions", "--no-builtin-tools", "--no-skills", "--no-context-files"]) assert.ok(started.includes(off), off);
		assert.equal(readlinkSync(instructions), path.resolve(import.meta.dirname, "../../live/AGENTS.md"), "the profile's instructions link to live/'s, over the copy an earlier start left");
	} finally {
		rmSync(at, { recursive: true, force: true });
	}
});

test("each message max types is saved as the next numbered file, and reaches the hypervisor with that file's path under it", async () => {
	const at = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-inputs-")));
	try {
		const inputs = path.join(at, ".local", "share", "hypervisor-inputs");
		mkdirSync(inputs, { recursive: true });
		// Numbering goes on from the highest file there, not from how many there are.
		writeFileSync(path.join(inputs, "1.txt"), "first");
		writeFileSync(path.join(inputs, "9.txt"), "ninth");
		writeFileSync(path.join(inputs, "notes.md"), "not one of max's messages");
		const extension = await load((pi) => live({ store: newStore(), home: at })(pi), at);
		const input = async (text: string, source = "interactive") => {
			const results = await Promise.all((extension.handlers.get("input") ?? []).map((handler) => handler({ type: "input", text, source }, extension.context)));
			return results[0] as { action: string; text?: string };
		};
		const paste = "line one\nline two\n\nline four";
		assert.deepEqual(await input(paste), { action: "transform", text: `${paste}\n\n(saved as ~/.local/share/hypervisor-inputs/10.txt)` });
		assert.equal(readFileSync(path.join(inputs, "10.txt"), "utf8"), paste, "the file holds the message as typed, so its line numbers are the message's");
		const returned = await input(`${paste}\n\n(saved as ~/.local/share/hypervisor-inputs/10.txt)`);
		assert.equal(returned.text, `${paste}\n\n(saved as ~/.local/share/hypervisor-inputs/11.txt)`, "a message pi handed back to the editor and max sent again gets one path line, its new one");
		assert.equal(readFileSync(path.join(inputs, "11.txt"), "utf8"), paste);
		assert.deepEqual(await input("[agents:board-fix] hv tell: the migration needs max", "extension"), { action: "continue" }, "a report another extension sends is not max's");
		assert.deepEqual(await input("  \n"), { action: "continue" });
		assert.deepEqual(readdirSync(inputs).sort(), ["1.txt", "10.txt", "11.txt", "9.txt", "notes.md"]);
		for (const handler of extension.handlers.get("session_shutdown") ?? []) await handler({ type: "session_shutdown" }, extension.context);
	} finally {
		rmSync(at, { recursive: true, force: true });
	}
});
