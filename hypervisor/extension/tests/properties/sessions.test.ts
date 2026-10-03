// lifelong-hypervisor#P4 at the session tools, past the directory check the registry's check rarely gets by: every
// directory a tool is given exists, so each run reaches the programs it starts, which are watched and never run.

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import fc from "fast-check";
import { watchEffects } from "./effects.ts";
import { paramsFor } from "./params.ts";
import { strings, toolProblems } from "./rules.ts";
import { execute, standIn } from "./stand-in.ts";

const store = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-store-")));
const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-home-")));
mkdirSync(path.join(home, "repo with spaces; and $(x)"));
const effects = watchEffects(store);
after(() => {
	effects.stop();
	rmSync(store, { recursive: true, force: true });
	rmSync(home, { recursive: true, force: true });
});
const { sessionTools } = await import("../../src/tools.ts");

const HOSTILE = fc.oneof(
	fc.string(),
	fc.constantFrom("; touch pwned", "$(touch pwned)", "`touch pwned`", "x\nrm -rf ~", "-rf", "--help", "--settings", "--dangerously-skip-permissions", "#(touch pwned)", "##(touch pwned)", "a#{pane_id}"),
);
const DIRS = fc.constantFrom("", "~", home, "repo with spaces; and $(x)", "~/repo with spaces; and $(x)");

test("lifelong-hypervisor#P4: the session tools run no shell, start nothing but tmux and claude in auto mode, and write only the store", async () => {
	const context = standIn({ cwd: home, hasUI: false });
	for (const tool of sessionTools({ home, claude: path.join(home, ".claude"), store })) {
		await fc.assert(
			fc.asyncProperty(paramsFor(tool.parameters, HOSTILE, { dir: DIRS }), async (params) => {
				const seen = await effects.during(() => execute(tool, params, context, 1000));
				assert.deepEqual(toolProblems(seen, store, strings(params)), [], `${tool.name} ${JSON.stringify(params)}`);
				if (tool.name === "spawn" && seen.launches.some((l) => l.args[0] === "new-session" || l.args[0] === "new-window"))
					assert.ok(seen.launches.some((l) => l.program === "tmux" && l.args.includes("claude")), "a window spawn opens runs claude");
			}),
			{ numRuns: 200 },
		);
	}
	assert.deepEqual(effects.stray, { launches: [], writes: [] });
});
