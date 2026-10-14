// lifelong-hypervisor#P4 at the tool registry: the live extension is loaded into a stand-in for pi, and its tools and
// handlers run while its processes and writes are watched.

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import fc from "fast-check";
import { watchEffects } from "./effects.ts";
import { HOSTILE, paramsFor } from "./params.ts";
import { harnessProblems, strings, toolProblems } from "./rules.ts";
import { execute, load, standIn, within } from "./stand-in.ts";

const store = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-store-")));
const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-home-")));
// Jarvis's mailbox as the check's own: a key in the scratch home, so tell_jarvis reaches ssh, which the watch records
// and never starts. The host is under `.invalid`, which no resolver answers, so an ssh that did start would reach no VPS.
const jarvis = { host: "jarvis.invalid", key: path.join(home, ".ssh", "hypervisor-jarvis") };
mkdirSync(path.dirname(jarvis.key));
writeFileSync(jarvis.key, "");
const effects = watchEffects(store);
after(() => {
	effects.stop();
	rmSync(store, { recursive: true, force: true });
	rmSync(home, { recursive: true, force: true });
});
const { live } = await import("../../src/live.ts");

/** How long a tool or handler runs before the check moves on; what it does after that is stray. */
const LIMIT = 1000;

test("lifelong-hypervisor#P4: no tool runs a shell or writes outside the store, whatever its arguments", async () => {
	let extension!: Awaited<ReturnType<typeof load>>;
	const atLoad = await effects.during(async () => {
		extension = await load(live({ store, home, jarvis }), home);
	});
	assert.deepEqual(harnessProblems(atLoad, store), [], "loading the extension");
	for (const [event, handlers] of extension.handlers) {
		const seen = await effects.during(() => Promise.all(handlers.map((handler) => within(LIMIT, async () => handler(standIn({ type: event }), extension.context)))));
		assert.deepEqual(harnessProblems(seen, store), [], `its ${event} handler`);
	}
	let mailed = 0;
	for (const tool of extension.tools.values()) {
		await fc.assert(
			fc.asyncProperty(paramsFor(tool.parameters, HOSTILE), async (params) => {
				const seen = await effects.during(() => execute(tool, params, extension.context, LIMIT));
				assert.deepEqual(toolProblems(seen, store, strings(params), jarvis), [], `${tool.name} ${JSON.stringify(params)}`);
				if (seen.launches.some((l) => l.program === "ssh")) mailed++;
			}),
			{ numRuns: 25 },
		);
	}
	assert.ok(mailed >= 10, `tell_jarvis reached ssh in ${mailed} runs of 25, too few to judge what it starts`);
	// The last run's tool may still be going: give it as long again before reading what came after the limits. A
	// tool still running past that reaches no assertion.
	await new Promise((settle) => setTimeout(settle, LIMIT));
	assert.deepEqual(effects.stray, { launches: [], writes: [] }, "effects after a tool's or handler's time ran out");
});

test("lifelong-hypervisor#P4: a tool may start ssh only as Jarvis's mailbox, and with no string the model sent", () => {
	const mailbox = ["-i", jarvis.key, "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", jarvis.host];
	const problems = (args: string[], given: string[] = []) => toolProblems({ launches: [{ program: "ssh", args, shell: false }], writes: [] }, store, given, jarvis);
	for (const request of [["tell"], ["fetch"], ["delete", "20261014T0800Z-thesis.md", "note_2"]]) assert.deepEqual(problems([...mailbox, ...request]), [], request.join(" "));
	const others: [string, string[]][] = [
		["another host", [...mailbox.slice(0, -1), "jarvis", "tell"]],
		["another key", ["-i", path.join(home, ".ssh", "id_ed25519"), ...mailbox.slice(2), "tell"]],
		["the agent's keys offered", [...mailbox.slice(0, 4), ...mailbox.slice(6), "tell"]],
		["an option more", ["-o", "ProxyCommand=sh -c id", ...mailbox, "tell"]],
		["a command of its own", [...mailbox, "rm", "-rf", "/"]],
		["the message in the argv", [...mailbox, "tell", "hello Jarvis"]],
		["fetch with arguments", [...mailbox, "fetch", "x"]],
		["delete with nothing to delete", [...mailbox, "delete"]],
		["delete of no message's name", [...mailbox, "delete", "../../etc/passwd"]],
		["no request", mailbox],
	];
	for (const [what, args] of others) assert.notDeepEqual(problems(args), [], what);
	assert.notDeepEqual(problems([...mailbox, "delete", "thesis-note.md"], ["thesis"]), [], "a name carrying a string the model sent");
	assert.notDeepEqual(toolProblems({ launches: [{ program: "ssh", args: [...mailbox, "tell"], shell: false }], writes: [] }, store, []), [], "ssh with no mailbox given");
	assert.notDeepEqual(toolProblems({ launches: [{ program: "ssh", args: [...mailbox, "tell"], shell: true }], writes: [] }, store, [], jarvis), [], "the mailbox's ssh through a shell");
});
