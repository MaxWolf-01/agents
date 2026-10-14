// The seam to Jarvis: a message tell_jarvis sends lands in Jarvis's inbox, and what Jarvis leaves in its outbox
// reaches the hypervisor's inbox by `hv fetch`. ssh is a stand-in on PATH that runs the real mailbox script, the key's
// forced command, against a workspace in a scratch directory, as sshd would with the request in SSH_ORIGINAL_COMMAND.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { after, test } from "node:test";
import { inbox } from "../src/inbox.ts";
import { fetchFromJarvis, type JarvisConfig } from "../src/jarvis.ts";
import { jarvisTool } from "../src/tools.ts";
import { resultText } from "./helpers.ts";

const MAILBOX = fileURLToPath(new URL("../../jarvis-mailbox", import.meta.url));
/** The biggest report the mailbox takes: its `max_bytes`. */
const MAX_BYTES = Number(/^max_bytes=(\d+)$/m.exec(readFileSync(MAILBOX, "utf8"))![1]);
const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-jarvis-")));
after(() => rmSync(dir, { recursive: true, force: true }));

const bin = path.join(dir, "bin");
mkdirSync(bin);
writeFileSync(
	path.join(bin, "ssh"),
	`#!/usr/bin/env bash
# Real ssh offers the agent's keys before -i's, and max's own key logs in as root, past the forced command.
[[ " $* " == *" IdentityAgent=none "* ]] || { echo "ssh: the agent's keys would be offered before the mailbox key" >&2; exit 255; }
while [[ $1 == -* ]]; do shift 2; done
shift
SSH_ORIGINAL_COMMAND="$*" exec ${JSON.stringify(MAILBOX)}
`,
);
chmodSync(path.join(bin, "ssh"), 0o755);
process.env.PATH = `${bin}:${process.env.PATH}`;

/** A VPS of its own: Jarvis's workspace with its inbox, the hypervisor's store on the laptop, and a mailbox key. */
function laptopAndJarvis() {
	const at = mkdtempSync(path.join(dir, "case-"));
	const workspace = path.join(at, "workspace");
	mkdirSync(path.join(workspace, "inbox"), { recursive: true });
	const key = path.join(at, "key");
	writeFileSync(key, "");
	process.env.JARVIS_WORKSPACE = workspace;
	const config: JarvisConfig = { host: "jarvis", key };
	return { config, workspace, store: path.join(at, "store"), outbox: path.join(workspace, "outbox/hypervisor") };
}

/** Runs the mailbox as the key's forced command, with `request` as what the laptop asked for. */
function mailbox(workspace: string, request: string | undefined, input = "") {
	const env = { ...process.env, JARVIS_WORKSPACE: workspace, SSH_ORIGINAL_COMMAND: request };
	if (request === undefined) delete env.SSH_ORIGINAL_COMMAND;
	return spawnSync(MAILBOX, { env, input, encoding: "utf8" });
}

test("a message tell_jarvis sends waits in Jarvis's inbox as one report from the hypervisor, whole and as written", async () => {
	const { config, workspace } = laptopAndJarvis();
	const message = "max's thesis deadline moved to 2026-11-20 (from the jku mail he forwarded).\nPut it in his calendar. — ü ✓";
	const answer = resultText(await jarvisTool(config).execute("call", { message } as never, undefined, undefined, undefined as never));
	const reports = readdirSync(path.join(workspace, "inbox"));
	assert.equal(reports.length, 1, "one report, and no dotfile left behind");
	assert.match(reports[0], /^hypervisor-.*\.md$/);
	assert.equal(readFileSync(path.join(workspace, "inbox", reports[0]), "utf8"), `${message}\n`);
	assert.ok(answer.includes(reports[0]), "the hypervisor learns under what name it waits");
});

test("Jarvis's messages, left while the laptop was off, reach the hypervisor's inbox from jarvis, oldest first, and leave the outbox", async () => {
	const { config, workspace, store, outbox } = laptopAndJarvis();
	mkdirSync(outbox, { recursive: true });
	// Named against their age, so the order can only come from when Jarvis wrote them.
	writeFileSync(path.join(outbox, "a-later.md"), "The thesis deadline is in your calendar now.\n");
	writeFileSync(path.join(outbox, "b-earlier.md"), "max asked me to tell you: no coding on Sunday.\n");
	utimesSync(path.join(outbox, "a-later.md"), new Date("2026-10-14T08:00:00Z"), new Date("2026-10-14T08:00:00Z"));
	utimesSync(path.join(outbox, "b-earlier.md"), new Date("2026-10-13T21:00:00Z"), new Date("2026-10-13T21:00:00Z"));
	writeFileSync(path.join(outbox, ".being-written.md"), "half a mess");

	assert.equal(await fetchFromJarvis(config, inbox(store)), 2);
	assert.match(inbox(store).statusLine(Date.parse("2026-10-14T09:00:00Z")) ?? "", /^Unread in your inbox: jarvis 2 messages, .*, 12h to 1h old\.$/);
	assert.deepEqual(await inbox(store).read({ from: "jarvis" }), [
		"[jarvis] max asked me to tell you: no coding on Sunday. (sent 2026-10-13T21:00Z)",
		"[jarvis] The thesis deadline is in your calendar now. (sent 2026-10-14T08:00Z)",
	]);
	assert.deepEqual(readdirSync(outbox), [".being-written.md"], "a message Jarvis is still writing stays for the next fetch");
	assert.equal(await fetchFromJarvis(config, inbox(store)), 0, "a fetched message arrives once");
	assert.equal(mailbox(workspace, "fetch").stdout, "", "and an outbox Jarvis never made fetches nothing");
});

test("the mailbox key runs tell, fetch and delete of an outbox message, and refuses a shell or any other path", () => {
	const { workspace, outbox } = laptopAndJarvis();
	mkdirSync(outbox, { recursive: true });
	writeFileSync(path.join(workspace, "secret"), "x");
	for (const request of [undefined, "", "bash", "cat /etc/shadow", "delete ../secret", "delete ../../workspace/secret", "delete *", "tell; rm -rf /"]) {
		const ran = mailbox(workspace, request, "hello");
		assert.notEqual(ran.status, 0, `${request} is refused`);
	}
	assert.deepEqual(readdirSync(workspace).sort(), ["inbox", "outbox", "secret"]);
	assert.deepEqual(readdirSync(path.join(workspace, "inbox")), []);
});

test("an empty message and one over the mailbox's limit leave nothing in Jarvis's inbox", async () => {
	const { config, workspace } = laptopAndJarvis();
	for (const input of ["", "x".repeat(MAX_BYTES + 1)]) assert.notEqual(mailbox(workspace, "tell", input).status, 0);
	await assert.rejects(jarvisTool(config).execute("call", { message: "  \n" } as never, undefined, undefined, undefined as never) as Promise<unknown>, /empty/);
	assert.deepEqual(readdirSync(path.join(workspace, "inbox")), []);
});

test("without its key, tell_jarvis says where the key should be", async () => {
	const { config } = laptopAndJarvis();
	const missing = { ...config, key: path.join(dir, "no-such-key") };
	await assert.rejects(jarvisTool(missing).execute("call", { message: "hi" } as never, undefined, undefined, undefined as never) as Promise<unknown>, /no mailbox key at .*no-such-key/);
});
