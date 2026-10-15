// `hv mail`: the hypervisor's inbox on the laptop and Jarvis's on the VPS, read and unread, as one timeline. ssh is a
// stand-in on PATH that runs the remote script in a shell of its own, so Jarvis's inbox is a scratch directory.

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, realpathSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { inbox } from "../src/inbox.ts";
import { parse } from "../src/hv-mail.ts";
import { HV, hypervisorInbox, instant, jarvisInbox, type Mail, render, timeline } from "../src/mail.ts";

const HV_MAIL = path.resolve(import.meta.dirname, "../src/hv-mail.ts");
const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-mail-")));
after(() => rmSync(dir, { recursive: true, force: true }));

const bin = path.join(dir, "bin");
mkdirSync(bin);
// The last argument is the script; the host before it is not reached.
writeFileSync(path.join(bin, "ssh"), `#!/usr/bin/env bash\nexec bash -c "\${@: -1}"\n`);
chmodSync(path.join(bin, "ssh"), 0o755);
process.env.PATH = `${bin}:${process.env.PATH}`;

/** Jarvis's workspace with the hypervisor's two reports, one read, a job's report, and one still being written. */
function jarvisWorkspace(): string {
	const workspace = mkdtempSync(path.join(dir, "workspace-"));
	const at = path.join(workspace, "inbox");
	mkdirSync(path.join(at, "read"), { recursive: true });
	const report = (name: string, text: string, when: string) => {
		writeFileSync(path.join(at, name), `${text}\n`);
		utimesSync(path.join(at, name), new Date(when), new Date(when));
	};
	report("read/hypervisor-20261015T012600Z-41.md", "Hello world from the hypervisor.", "2026-10-15T01:26:00Z");
	report("hypervisor-20261015T090000Z-77.md", "Put the thesis deadline in max's calendar.\nIt moved to 2026-11-20.", "2026-10-15T09:00:00Z");
	report("weekly-spending.md", "Spending this week: within budget.", "2026-10-15T07:00:00Z");
	report(".hypervisor-20261015T091000Z-80.md", "half a rep", "2026-10-15T09:10:00Z");
	return workspace;
}

/** The hypervisor's store, with Jarvis's two messages, the first read, and an orchestrator's report. */
async function hypervisorStore(): Promise<string> {
	const store = mkdtempSync(path.join(dir, "store-"));
	const box = inbox(store);
	await box.post({ at: "2026-10-15T01:07:00.000Z", from: "jarvis", text: "Test from Jarvis. Nothing to do." });
	await box.read({ from: "jarvis" });
	await box.post({ at: "2026-10-15T08:30:00.000Z", from: "jarvis", text: "max asked me to tell you: the explore run can start." });
	await box.post({ at: "2026-10-15T08:00:00.000Z", from: "agents:board-fix", text: "Board fix landed." });
	return store;
}

test("the hypervisor's inbox gives every message, read ones too, as sent to the hypervisor", async () => {
	const mails = hypervisorInbox(await hypervisorStore());
	const brief = mails.map((m) => [m.from, m.to, m.read]).sort();
	assert.deepEqual(brief, [
		["agents:board-fix", HV, false],
		["jarvis", HV, false],
		["jarvis", HV, true],
	]);
});

test("Jarvis's inbox gives the hypervisor's reports, read ones too, sent when their files were written, and leaves out one still being written", async () => {
	const mails = await jarvisInbox("jarvis", { workspace: jarvisWorkspace() });
	assert.deepEqual(
		mails.map((m) => [m.at, m.from, m.to, m.read]).sort(),
		[
			["2026-10-15T01:26:00.000Z", HV, "jarvis", true],
			["2026-10-15T09:00:00.000Z", HV, "jarvis", false],
		],
	);
	assert.equal(mails.find((m) => !m.read)?.text, "Put the thesis deadline in max's calendar.\nIt moved to 2026-11-20.");
});

test("with all, Jarvis's inbox also gives its other reports, each from its file's name", async () => {
	const mails = await jarvisInbox("jarvis", { all: true, workspace: jarvisWorkspace() });
	assert.deepEqual(mails.map((m) => m.from).sort(), [HV, HV, "weekly-spending"]);
});

test("a Jarvis workspace with no inbox gives no message", async () => {
	assert.deepEqual(await jarvisInbox("jarvis", { workspace: path.join(dir, "nowhere") }), []);
});

const mail = (at: string, from: string, to: string): Mail => ({ at, from, to, text: `${from} at ${at}`, read: false });
const MAILS = [
	mail("2026-10-15T09:00:00Z", HV, "jarvis"),
	mail("2026-10-14T22:00:00Z", "jarvis", HV),
	mail("2026-10-15T08:00:00Z", "agents:board-fix", HV),
	mail("2026-10-15T07:00:00Z", "weekly-spending", "jarvis"),
	mail("2026-10-16T06:00:00Z", "jarvis", HV),
];

test("the timeline keeps what the two sent each other, oldest first, and with all everything", () => {
	assert.deepEqual(
		timeline(MAILS).map((m) => m.at),
		["2026-10-14T22:00:00Z", "2026-10-15T09:00:00Z", "2026-10-16T06:00:00Z"],
	);
	assert.equal(timeline(MAILS, { all: true }).length, 5);
});

test("since, until and -n narrow the timeline, a bare date counting its whole day in local time", () => {
	const day = { since: instant("2026-10-15"), until: instant("2026-10-15", true) };
	const local = (m: Mail) => new Date(m.at).toDateString();
	for (const m of timeline(MAILS, { all: true, ...day })) assert.equal(local(m), new Date(2026, 9, 15).toDateString());
	assert.equal(timeline(MAILS, { all: true, ...day }).length, MAILS.filter((m) => local(m) === new Date(2026, 9, 15).toDateString()).length);
	assert.deepEqual(
		timeline(MAILS, { last: 2 }).map((m) => m.at),
		["2026-10-15T09:00:00Z", "2026-10-16T06:00:00Z"],
	);
	assert.equal(timeline(MAILS, { last: 0 }).length, 0);
});

test("the command line takes the flags hv mail --help names and refuses others", () => {
	const { filter, follow, json } = parse(["--all", "--since", "2026-10-15", "-n", "3", "-f", "--json"]);
	assert.deepEqual(filter, { all: true, since: instant("2026-10-15"), last: 3 });
	assert.ok(follow && json);
	assert.throws(() => parse(["-n", "three"]), /count/);
	assert.throws(() => parse(["--since", "yesterday"]), /no date/);
	assert.throws(() => parse(["--since"]), /needs a value/);
	assert.throws(() => parse(["--from", "2026-10-15"]), /no option/);
});

test("hv mail prints both inboxes as one timeline, unread ones marked, and --json one message per line", async () => {
	const workspace = jarvisWorkspace();
	const store = await hypervisorStore();
	const env = { ...process.env, HV_STORE: store, HV_JARVIS_WORKSPACE: workspace };
	const hv = (...args: string[]) => execFileSync("node", [HV_MAIL, ...args], { env, encoding: "utf8" });
	const lines = hv("--json")
		.trim()
		.split("\n")
		.map((line) => JSON.parse(line) as Mail);
	assert.deepEqual(
		lines.map((m) => `${m.from}→${m.to}${m.read ? "" : " unread"}`),
		["jarvis→hv", `${HV}→jarvis`, "jarvis→hv unread", `${HV}→jarvis unread`],
	);
	const printed = hv("-n", "1");
	assert.equal(printed.trim(), render(lines.at(-1)!).trim());
	assert.match(printed, /hv → jarvis {2}\(unread\)\n {4}Put the thesis deadline/);
});
