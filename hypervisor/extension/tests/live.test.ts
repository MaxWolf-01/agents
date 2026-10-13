// The live hypervisor's extension, loaded beside stand-ins for pi-optchat's tools: which tools end up active, and how
// what an orchestrator reports reaches OptChat.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { post } from "../src/inbox.ts";
import { live, MEMORY } from "../src/live.ts";
import { MODEL } from "../src/pi.ts";
import { load } from "./properties/stand-in.ts";

const store = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-store-")));
const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-home-")));
after(() => {
	rmSync(store, { recursive: true, force: true });
	rmSync(home, { recursive: true, force: true });
});

/** pi-optchat's tools by name, as the fork registers them: `spawn` and `tell` start and steer pi subagents with pi's coding tools. */
const OPTCHAT = ["zoom", "date", "spawn", "tell", "search"];
function optchat(pi: ExtensionAPI) {
	for (const name of OPTCHAT) pi.registerTool({ name, label: name, description: name, parameters: {} as never, execute: async () => ({ content: [], details: undefined }) });
}

/** The extension loaded after OptChat's tools, with pi's event bus answering each report with `takes()`. */
async function loaded(takes: () => boolean) {
	const reports: { channel: string; text: string }[] = [];
	const bus = {
		emit: (channel: string, data: { text: string; taken?: boolean }) => {
			reports.push({ channel, text: data.text });
			if (takes()) data.taken = true;
		},
		on: () => () => {},
	};
	const extension = await load((pi) => {
		optchat(pi);
		live({ store, home })(new Proxy(pi, { get: (target, key) => (key === "events" ? bus : target[key as keyof ExtensionAPI]) }));
	}, home);
	const stop = async () => {
		for (const handler of extension.handlers.get("session_shutdown") ?? []) await handler({ type: "session_shutdown" }, extension.context);
	};
	return { ...extension, reports, stop };
}

test("lifelong-hypervisor#P4: the live set is OptChat's zoom and date, the session tools and the explorer's read tools, and OptChat's subagent tools are inactive", async () => {
	const { active, stop } = await loaded(() => true);
	await stop();
	const SESSIONS = ["start_session", "tell_session", "look", "delegate"];
	const READ = ["read", "ls", "find", "grep", "memex"];
	assert.deepEqual([...active].sort(), [...MEMORY, ...SESSIONS, ...READ].sort());
});

test("an orchestrator's hv tell goes to OptChat as a report, and stays in the inbox until OptChat takes it", async () => {
	let takes = false;
	await post(store, { at: "t", from: "agents:board-fix", text: "done, see the ticket" });
	const { reports, stop } = await loaded(() => takes);
	try {
		await new Promise((settle) => setTimeout(settle, 100));
		assert.deepEqual(reports, [{ channel: "optchat:report", text: "[agents:board-fix] hv tell: done, see the ticket" }]);
		assert.equal(readdirSync(path.join(store, "inbox")).length, 1, "nothing took it: the inbox keeps it");
		takes = true;
		await new Promise((settle) => setTimeout(settle, 3500));
		assert.equal(reports.length, 2, "offered again at the next look");
		assert.equal(readdirSync(path.join(store, "inbox")).length, 0);
	} finally {
		await stop();
	}
});

test("hv starts pi in tmux with the fork's OptChat and this extension, on the profile, its turns cached for an hour", () => {
	const at = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-launch-")));
	try {
		const bin = path.join(at, "bin"), fork = path.join(at, "fork"), hvStore = path.join(at, "store"), calls = path.join(at, "tmux.calls");
		for (const dir of [bin, path.join(fork, "src"), path.join(hvStore, "optchat", "profiles", "hv")]) mkdirSync(dir, { recursive: true });
		writeFileSync(path.join(fork, "src", "index.ts"), "");
		// A tmux whose server runs no session yet: it records each call, one argument a line, and refuses has-session.
		writeFileSync(path.join(bin, "tmux"), `#!/bin/sh\nprintf '%s\\n' "$@" '--' >> "${calls}"\n[ "$1" = has-session ] && exit 1\nexit 0\n`, { mode: 0o755 });
		const env = { PATH: `${bin}:${process.env.PATH}`, HOME: at, HV_STORE: hvStore, OPTCHAT_FORK: fork, ANTHROPIC_OAUTH_TOKEN: "token" };
		const ran = spawnSync(path.resolve(import.meta.dirname, "../../hv"), [], { env, encoding: "utf8" });
		assert.equal(ran.status, 0, ran.stderr);
		const started = readFileSync(calls, "utf8").split("--\n").map((call) => call.trimEnd().split("\n")).find((args) => args[0] === "new-session");
		assert.ok(started, "hv opens a tmux session");
		const after = (flag: string) => started.flatMap((arg, i) => (started[i - 1] === flag ? [arg] : []));
		assert.deepEqual(after("-e").filter((e) => !e.includes("=")), [path.join(fork, "src", "index.ts"), path.resolve(import.meta.dirname, "../src/live.ts")], "the extensions, OptChat first");
		assert.ok(after("-e").includes("PI_CACHE_RETENTION=long"));
		assert.deepEqual(after("--optchat-profile"), ["hv"]);
		assert.deepEqual(after("--model"), [MODEL]);
		for (const off of ["--no-extensions", "--no-builtin-tools", "--no-skills", "--no-context-files"]) assert.ok(started.includes(off), off);
	} finally {
		rmSync(at, { recursive: true, force: true });
	}
});
