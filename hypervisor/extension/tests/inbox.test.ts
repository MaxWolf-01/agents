// The hypervisor's inbox: a plain message waits until the hypervisor reads it, a ping until the watch takes it to
// start a turn, and each is handled once. Every check runs on a store of its own in a scratch directory.

import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import fc from "fast-check";
import { inbox } from "../src/inbox.ts";
import { watch } from "../src/watch.ts";

const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-inbox-")));
after(() => rmSync(dir, { recursive: true, force: true }));
const newStore = () => mkdtempSync(path.join(dir, "store-"));

const AT = "2026-10-13T14:07:00.000Z";
/** The id a listing line gives its message. */
const idOf = (line: string) => line.split("  ")[0];

/** One step of a run against the inbox: a post, a read by listed id or by sender, or a take whose delivery takes, refuses or fails. */
type Step =
	| { post: { from: string; text: string; ping: boolean; via: boolean; writer: 0 | 1 } }
	| { read: { pick: number; by: "id" | "from" } }
	| { take: "taken" | "refused" | "failed" };

const SENDERS = ["agents:board-fix", "agents:hypervisor", "~/repos/notes", "wait api-build"];
const step: fc.Arbitrary<Step> = fc.oneof(
	{ weight: 3, arbitrary: fc.record({ from: fc.constantFrom(...SENDERS), text: fc.string(), ping: fc.boolean(), via: fc.boolean(), writer: fc.constantFrom(0 as const, 1 as const) }).map((post) => ({ post })) },
	{ weight: 2, arbitrary: fc.record({ pick: fc.nat(), by: fc.constantFrom("id" as const, "from" as const) }).map((read) => ({ read })) },
	{ weight: 2, arbitrary: fc.constantFrom("taken" as const, "refused" as const, "failed" as const).map((take) => ({ take })) },
);

test("every message is delivered or read exactly once, a ping never shows in the listing or the status line, and a ping nobody took stays for the next take", async () => {
	await fc.assert(
		fc.asyncProperty(fc.array(step, { maxLength: 30 }), async (steps) => {
			const store = newStore();
			// The watch's inbox, and another on the same store, as `hv tell` posts from a process of its own.
			const inboxes = [inbox(store), inbox(store)];
			const [hypervisor] = inboxes;
			// What the inbox should hold, oldest first: each message's tag, sender and whether it is a ping.
			let model: { tag: string; from: string; ping: boolean }[] = [];
			/** Every tag handed over: read, or delivered by a take that took it. */
			const handled: string[] = [];
			const tags = (said: string[]) => said.flatMap((s) => [...s.matchAll(/#(\d+)#/g)].map((m) => m[1]));
			const take = async (outcome: "taken" | "refused" | "failed") => {
				let offered: string[] = [];
				await hypervisor
					.takePings((pings) => {
						offered = pings;
						if (outcome === "failed") throw new Error("not now");
						return outcome === "taken";
					})
					.catch(() => {});
				const pings = model.filter((m) => m.ping);
				assert.deepEqual(tags(offered), pings.map((m) => m.tag), "a take offers every waiting ping, oldest first, and nothing else");
				if (outcome === "taken") {
					handled.push(...tags(offered));
					model = model.filter((m) => !m.ping);
				}
			};
			const read = async (which: { id?: string; from?: string }, expected: string[]) => {
				const said = await hypervisor.read(which);
				assert.deepEqual(tags(said), expected, "a read hands over what it asked for, oldest first");
				handled.push(...tags(said));
				model = model.filter((m) => !expected.includes(m.tag));
			};
			let posted = 0;
			for (const s of steps) {
				if ("post" in s) {
					const { from, text, ping, via, writer } = s.post;
					const tag = String(posted++);
					await inboxes[writer].post({ at: AT, from, text: `#${tag}# ${text}`, ...(ping ? { ping } : {}), ...(via ? { via: "hv tell" } : {}) });
					model.push({ tag, from, ping });
				} else if ("read" in s) {
					const plain = model.filter((m) => !m.ping);
					const listing = hypervisor.list();
					if (!plain.length) await read({ from: SENDERS[s.read.pick % SENDERS.length] }, []);
					else if (s.read.by === "id") await read({ id: idOf(listing[s.read.pick % listing.length]) }, [plain[s.read.pick % plain.length].tag]);
					else {
						const from = plain[s.read.pick % plain.length].from;
						await read({ from }, plain.filter((m) => m.from === from).map((m) => m.tag));
					}
				} else await take(s.take);

				const plain = model.filter((m) => !m.ping);
				assert.deepEqual(
					hypervisor.list().map((line) => line.split("  ")[1]),
					plain.map((m) => m.from),
					"the listing has a line for each plain message that waits, and none for a ping",
				);
				const counted = [...(hypervisor.statusLine() ?? "").matchAll(/ (\d+) messages?,/g)].reduce((sum, m) => sum + Number(m[1]), 0);
				assert.equal(counted, plain.length, "the status line counts the plain messages that wait, and no ping");
				assert.equal(hypervisor.statusLine() === undefined, plain.length === 0);
			}
			// Drain what still waits: then every message has been handed over, and none twice.
			for (const from of SENDERS) await read({ from }, model.filter((m) => !m.ping && m.from === from).map((m) => m.tag));
			await take("taken");
			assert.deepEqual(handled.map(Number).sort((a, b) => a - b), [...Array(posted).keys()], "every message handed over exactly once");
			assert.equal(readdirSync(path.join(store, "inbox", "read")).length, posted, "read/ keeps every message");
		}),
		{ numRuns: 150 },
	);
});

test("the listing gives id, sender, size and age, never the text; a file that does not parse is left out, and ids stay as they were", async () => {
	const store = newStore();
	const box = inbox(store);
	const now = Date.parse("2026-10-13T15:00:00Z");
	await box.post({ at: "2026-10-13T12:00:00Z", from: "agents:board", text: "the board renders" });
	await box.post({ at: "2026-10-13T14:55:00Z", from: "~/repos/notes", text: "x".repeat(1500) });
	await box.post({ at: "2026-10-13T14:59:00Z", from: "agents:board", text: "third" });
	writeFileSync(path.join(store, "inbox", "0-broken.json"), "{");
	const listed = box.list(now);
	assert.deepEqual(
		listed.map((line) => line.slice(line.indexOf("  ") + 2)),
		["agents:board  17 B  3h old", "~/repos/notes  1.5 kB  5m old", "agents:board  5 B  1m old"],
	);
	await box.read({ id: idOf(listed[1]) });
	assert.deepEqual(box.list(now), [listed[0], listed[2]]);
});

test("the status line lists the unread by sender, with count, size and age, and never their text", async () => {
	const box = inbox(newStore());
	const now = Date.parse("2026-10-13T15:00:00Z");
	assert.equal(box.statusLine(now), undefined);
	await box.post({ at: "2026-10-13T12:00:00Z", from: "agents:board", text: "the board renders, see the PR" });
	await box.post({ at: "2026-10-13T14:55:00Z", from: "~/repos/notes", text: "x".repeat(1500) });
	await box.post({ at: "2026-10-13T14:58:30Z", from: "agents:board", text: "and the CI is green" });
	await box.post({ at: "2026-10-13T14:59:00Z", from: "agents:board", text: "needs max", ping: true });
	assert.equal(box.statusLine(now), "Unread in your inbox: agents:board 2 messages, 48 B, 3h to 1m old; ~/repos/notes 1 message, 1.5 kB, 5m old.");
});

test("the watch hands each ping over once, the plain message beside it waiting; two takes at once deliver once", async () => {
	const store = newStore();
	const box = inbox(store);
	const delivered: string[][] = [];
	const failures: unknown[] = [];
	const w = watch(box, 2 ** 30, (pings) => void delivered.push(pings), (error) => failures.push(error));
	try {
		await w.started;
		await box.post({ at: AT, from: "my-repo:board-fix", text: "done" });
		await box.post({ at: AT, from: "my-repo:board-fix", text: "the migration needs max", ping: true, via: "hv tell" });
		await Promise.all([w.look(), w.look()]);
		await w.look();
		assert.deepEqual(delivered, [["[my-repo:board-fix] hv tell: the migration needs max"]]);
		assert.equal(box.list().length, 1);
		assert.deepEqual(failures, []);
	} finally {
		w.stop();
	}
});

test("a take whose delivery fails goes to failed, and its ping is offered again at the next take", async () => {
	const box = inbox(newStore());
	const offered: string[][] = [];
	const failures: unknown[] = [];
	let refuse = true;
	const w = watch(
		box,
		2 ** 30,
		(pings) => {
			offered.push(pings);
			if (refuse) throw new Error("not now");
		},
		(error) => failures.push(error),
	);
	try {
		await w.started;
		await box.post({ at: AT, from: "my-repo:board-fix", text: "needs max", ping: true });
		await w.look();
		assert.equal(failures.length, 1);
		refuse = false;
		await w.look();
		await w.look();
		assert.deepEqual(offered, [["[my-repo:board-fix] needs max"], ["[my-repo:board-fix] needs max"]]);
	} finally {
		w.stop();
	}
});
