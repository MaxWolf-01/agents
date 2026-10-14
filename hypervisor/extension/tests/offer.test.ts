// `hv offer`, as the timer runs it: a fixture statusline cache in a home of the test's own, a stand-in for `hv tell`
// that records what it is told, and a stand-in notify-send.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { inbox } from "../src/inbox.ts";
import { lines } from "../src/journal.ts";

const HV_OFFER = path.resolve(import.meta.dirname, "../src/hv-offer.ts");
const HV = path.resolve(import.meta.dirname, "../../hv");
const HOUR = 3600_000;

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-offer-")));
after(() => rmSync(dir, { recursive: true, force: true }));

/** A home with a statusline cache, a store, and stand-ins that append their arguments to `told` and `notified`. */
function fixture(name: string) {
	const at = path.join(dir, name);
	const f = { home: path.join(at, "home"), store: path.join(at, "store"), bin: path.join(at, "bin"), told: path.join(at, "told"), notified: path.join(at, "notified") };
	for (const d of [path.join(f.home, ".cache", "claude-statusline"), f.store, f.bin]) mkdirSync(d, { recursive: true });
	writeFileSync(path.join(f.bin, "notify-send"), `#!/bin/sh\nprintf '%s\\n' "$*" >> "${f.notified}"\n`, { mode: 0o755 });
	writeFileSync(path.join(f.bin, "tell"), `#!/bin/sh\nprintf '%s\\n' "$*" >> "${f.told}"\n`, { mode: 0o755 });
	writeFileSync(path.join(f.bin, "tell-fails"), "#!/bin/sh\nexit 3\n", { mode: 0o755 });
	return f;
}
type Fixture = ReturnType<typeof fixture>;

/** What Claude Code hands the statusline, kept as the session's file: the account's week, read `ago` ms before now. */
function reading(f: Fixture, session: string, week: { used: number; resetsIn: number; ago?: number; account?: string }) {
	const now = Date.now();
	const input = { session_id: session, config_dir: path.join(f.home, week.account ?? ".claude"), written_at: (now - (week.ago ?? 0)) / 1000, rate_limits: { seven_day: { used_percentage: week.used, resets_at: (now + week.resetsIn) / 1000 } } };
	writeFileSync(path.join(f.home, ".cache", "claude-statusline", `${session}.json`), JSON.stringify(input));
}

/** `hv offer` with `tell` as its way to hv tell: what it printed, and its exit code. */
function offer(f: Fixture, tell = "tell") {
	const run = spawnSync(process.execPath, [HV_OFFER, "--", path.join(f.bin, tell), "--ping"], { env: { ...process.env, PATH: `${f.bin}:${process.env.PATH}`, HOME: f.home, HV_STORE: f.store }, encoding: "utf8", timeout: 30_000 });
	return { out: `${run.stdout}${run.stderr}`, code: run.status };
}

const told = (f: Fixture) => (existsSync(f.told) ? readFileSync(f.told, "utf8").trimEnd().split("\n") : []);
const offers = (f: Fixture) => lines<{ offer?: number }>(f.store, "explore.jsonl").then((all) => all.filter((line) => line.offer !== undefined));

test("12 hours before the reset, with more than a fifth of the week unused, the hypervisor is pinged the offer once, and max notified", async () => {
	const f = fixture("due");
	reading(f, "s", { used: 40, resetsIn: 6 * HOUR });
	for (let hour = 0; hour < 3; hour++) assert.equal(offer(f).code, 0);
	assert.equal(told(f).length, 1, "one offer for the week, however often the timer runs");
	assert.match(told(f)[0]!, /^--ping Explore offer: .*60% of it unused\. Ask him whether you should explore for up to 50 steps until 95% of the week is used.*`\/explore 50 --until-week 95 <direction>`.*No answer means no run, and once that reset has passed, the offer has lapsed\./);
	assert.equal(readFileSync(f.notified, "utf8").trimEnd().split("\n").length, 1);
	assert.equal((await offers(f)).length, 1);
	assert.match(offer(f).out, /^No offer: this week's was made already/);
});

test("a week not due an offer is pinged nothing: too early, nearly used, already reset, or due only on another account", async () => {
	const weeks = {
		early: { used: 10, resetsIn: 13 * HOUR },
		used: { used: 85, resetsIn: 6 * HOUR },
		reset: { used: 10, resetsIn: -HOUR },
		other: { used: 10, resetsIn: 6 * HOUR, account: ".claude-pro" },
	};
	for (const [name, week] of Object.entries(weeks)) {
		const f = fixture(name);
		reading(f, "s", week);
		const run = offer(f);
		assert.equal(run.code, 0, run.out);
		assert.match(run.out, /^No offer/, name);
		assert.deepEqual(told(f), [], name);
		assert.equal(existsSync(f.notified), false, name);
		assert.deepEqual(await offers(f), [], name);
	}
});

test("the newest reading of the week decides: a week used up since an older reading is not offered", () => {
	const f = fixture("newest");
	reading(f, "old", { used: 30, resetsIn: 6 * HOUR, ago: 2 * HOUR });
	reading(f, "new", { used: 90, resetsIn: 6 * HOUR });
	const run = offer(f);
	assert.equal(run.code, 0, run.out);
	assert.match(run.out, /^No offer: .*, 90% used/);
	assert.deepEqual(told(f), []);
});

test("an offer hv tell failed to deliver is not recorded, so the next run makes it", async () => {
	const f = fixture("failed");
	reading(f, "s", { used: 40, resetsIn: 6 * HOUR });
	assert.equal(offer(f, "tell-fails").code, 1);
	assert.deepEqual(await offers(f), []);
	assert.equal(offer(f).code, 0);
	assert.equal(told(f).length, 1);
});

test("last week's offer does not stand for this week's", () => {
	const f = fixture("next-week");
	writeFileSync(path.join(f.store, "explore.jsonl"), `${JSON.stringify({ at: new Date(Date.now() - 7 * 24 * HOUR).toISOString(), offer: Date.now() - 7 * 24 * HOUR + 6 * HOUR, used: 30 })}\n`);
	reading(f, "s", { used: 40, resetsIn: 6 * HOUR });
	const run = offer(f);
	assert.equal(run.code, 0, run.out);
	assert.equal(told(f).length, 1);
});

test("hv offer reaches the hypervisor through hv tell, as a ping in its inbox", async () => {
	const f = fixture("hv");
	reading(f, "s", { used: 40, resetsIn: 6 * HOUR });
	const run = spawnSync(HV, ["offer"], { env: { ...process.env, PATH: `${f.bin}:${process.env.PATH}`, HOME: f.home, HV_STORE: f.store, TMUX_PANE: "" }, encoding: "utf8", timeout: 30_000 });
	assert.equal(run.status, 0, `${run.stdout}${run.stderr}`);
	let pings: string[] = [];
	await inbox(f.store).takePings((taken) => ((pings = taken), false));
	assert.equal(pings.length, 1);
	assert.match(pings[0]!, /^\[.*\] hv tell: Explore offer: max's week resets at /);
});
