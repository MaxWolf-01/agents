// lifelong-hypervisor#P4 at the session tools, past the checks the registry's check rarely gets by: every directory a
// tool is given exists and a session it names is often live, so each run reaches the programs it starts, which are
// watched and never run, and the inbox socket it writes to.

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import fc from "fast-check";
import { watchEffects } from "./effects.ts";
import { HOSTILE, paramsFor } from "./params.ts";
import { strings, toolProblems } from "./rules.ts";
import { execute, standIn } from "./stand-in.ts";

const store = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-store-")));
const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-home-")));
/** Directories a model could name, those tmux would read a format in among them. */
const NAMED = ["repo with spaces; and $(x)", "x#(touch pwned)", "x##(y)", "a#{pane_id}"];
for (const name of NAMED) mkdirSync(path.join(home, name));
// Two live sessions, this process and its parent, one named as a model would and one as a hostile string, each in a
// pane of its own with an inbox socket that counts the messages it takes.
const socket = path.join(home, "inbox.sock");
let delivered = 0;
const inbox = createServer((c) => {
	delivered++;
	c.resume();
});
await new Promise<void>((resolve) => inbox.listen(socket, resolve));
mkdirSync(path.join(home, ".claude", "sessions"), { recursive: true });
for (const [pid, name, pane] of [[process.pid, "orch", "%5"], [process.ppid, "#(touch pwned)", "%6"]] as const)
	writeFileSync(path.join(home, ".claude", "sessions", `${pid}.json`), JSON.stringify({ pid, name, cwd: home, status: "idle", tmux: `agents:@1.${pane}`, messagingSocketPath: socket }));
const effects = watchEffects(store);
after(() => {
	effects.stop();
	inbox.close();
	rmSync(store, { recursive: true, force: true });
	rmSync(home, { recursive: true, force: true });
});
const { sessionTools } = await import("../../src/tools.ts");

const DIRS = fc.constantFrom("", "~", home, ...NAMED, ...NAMED.map((name) => `~/${name}`), ...NAMED.map((name) => path.join(home, name)));
const SESSIONS = fc.oneof(HOSTILE, fc.constantFrom("orch", String(process.pid), "#(touch pwned)"));

test("lifelong-hypervisor#P4: the session tools run no shell, start nothing but tmux and claude in auto mode, and write only the store", async () => {
	const context = standIn({ cwd: home, hasUI: false });
	let opened = 0;
	let captured = 0;
	for (const tool of sessionTools({ home, store })) {
		await fc.assert(
			fc.asyncProperty(paramsFor(tool.parameters, HOSTILE, { dir: DIRS, session: SESSIONS }), async (params) => {
				const seen = await effects.during(() => execute(tool, params, context, 1000));
				assert.deepEqual(toolProblems(seen, store, strings(params)), [], `${tool.name} ${JSON.stringify(params)}`);
				if (tool.name === "start_session" && seen.launches.some((l) => l.args[0] === "new-session" || l.args[0] === "new-window")) {
					opened++;
					assert.ok(seen.launches.some((l) => l.program === "tmux" && l.args.includes("claude")), "a window spawn opens runs claude");
				}
				if (seen.launches.some((l) => l.args[0] === "capture-pane")) captured++;
			}),
			{ numRuns: 200 },
		);
	}
	assert.ok(opened >= 20, `spawn opened a window in ${opened} runs of 200, too few to judge what it starts`);
	assert.ok(captured >= 20, `look read a pane in ${captured} runs of 200, too few to judge what it runs`);
	assert.ok(delivered >= 20, `tell reached the inbox socket in ${delivered} runs of 200, too few to judge what it sends`);
	assert.deepEqual(effects.stray, { launches: [], writes: [] });
});
