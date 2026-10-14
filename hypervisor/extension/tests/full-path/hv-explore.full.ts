// `hv explore` against a real pi TUI in real tmux, on a tmux server of the check's own, with the live extension and a
// stand-in for the Anthropic endpoint. It needs tmux, so it runs from `make test-full-path`, not the fast suite.

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { standInAnthropic, standInModels } from "../stand-in-anthropic.ts";

const EXTENSION = path.resolve(import.meta.dirname, "../..");
const HV_EXPLORE = path.join(EXTENSION, "src/hv-explore.ts");
const PI = path.join(EXTENSION, "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js");

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-explore-tui-")));
const [bin, home, store, agent, profile] = ["bin", "home", "store", "agent", "optchat/profiles/hv"].map((d) => path.join(dir, d));
for (const d of [bin, home, store, agent, profile]) mkdirSync(d, { recursive: true });
// Every tmux call, hv-explore's own among them, goes to this check's server, whatever the host's tmux runs.
const realTmux = execFileSync("sh", ["-c", "command -v tmux"], { encoding: "utf8" }).trim();
writeFileSync(path.join(bin, "tmux"), `#!/bin/sh\nexec "${realTmux}" -L "${path.basename(dir)}" "$@"\n`, { mode: 0o755 });

let calls = 0;
const anthropic = await standInAnthropic(() => {
	calls++;
	appendFileSync(path.join(profile, "usage.jsonl"), `${JSON.stringify({ date: new Date().toISOString(), role: "main", usage: { cost: { total: 0.004 } } })}\n`);
	return { text: `finding ${calls}` };
});
standInModels(agent, anthropic.url);

const env = { ...process.env, PATH: `${bin}:${process.env.PATH}`, HOME: home, HV_HOME: home, HV_STORE: store, OPTCHAT_HOME: path.join(dir, "optchat"), HV_PROFILE: "hv", PI_CODING_AGENT_DIR: agent, PI_OFFLINE: "1" };
const pi = [process.execPath, PI, "--no-extensions", "--no-builtin-tools", "--no-skills", "--no-context-files", "--no-prompt-templates", "--no-session", "-e", path.join(EXTENSION, "src/live.ts"), "--model", "stand-in/claude-opus-5-5"];
/** The TUI's start, as `hv` passes it: a detached session carrying the environment pi runs in. */
const start = ["tmux", "new-session", "-d", "-s", "hypervisor", ...Object.entries(env).filter(([k]) => /^(PATH|HOME|HV_|OPTCHAT_|PI_)/.test(k)).flatMap(([k, v]) => ["-e", `${k}=${v}`]), ...pi];

after(async () => {
	try {
		execFileSync("tmux", ["kill-server"], { env, stdio: "ignore" });
	} catch {}
	await anthropic.close();
	rmSync(dir, { recursive: true, force: true });
});

const hvExplore = (...args: string[]) => execFileSync(process.execPath, [HV_EXPLORE, ...args, "--", ...start], { env, encoding: "utf8", timeout: 30_000 });
const ended = () => (existsSync(path.join(store, "explore.jsonl")) ? readFileSync(path.join(store, "explore.jsonl"), "utf8").split("\n").filter((line) => line.includes('"ended"')).length : 0);
async function runsEnded(n: number) {
	for (const deadline = Date.now() + 60_000; ended() < n && Date.now() < deadline; ) await new Promise((r) => setTimeout(r, 300));
	assert.equal(ended(), n, `run ${n} never ended; the pane reads:\n${execFileSync("tmux", ["capture-pane", "-p", "-t", "=hypervisor:"], { env, encoding: "utf8" })}`);
}

test("hv explore starts the closed TUI with the run, then types the next run into the open TUI, and --found reads it back", async () => {
	assert.match(hvExplore("2", "papers", "on", "ALife"), /TUI started/);
	await runsEnded(1);
	assert.match(hvExplore("1", "the", "news"), /typed into its pane/);
	await runsEnded(2);
	const found = execFileSync(process.execPath, [HV_EXPLORE, "--found"], { env, encoding: "utf8" });
	assert.match(found, /toward the news:\n\nstep 1, 1000 tokens:\nfinding 3\n\nEnded after 1 step, 1000 tokens: stopped by 1 step\./);
});
