// The explorer's tools over a small home, beside the P5 properties: a search from home passes over every denied root,
// and memex's answer passes through the same denylist (hypervisor-property-checks D6), run against a stand-in for
// memex's command line that answers with notes from a denied root, their text, and notes that are open.

import assert from "node:assert/strict";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { exploreTools } from "../src/explore.ts";

const SECRET = "c4n4ry-content-7f3a91";
const HIDDEN = "c4n4ry-name-52bd07";

const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-explore-tools-")));
const bin = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-memex-")));
after(() => {
	rmSync(home, { recursive: true, force: true });
	rmSync(bin, { recursive: true, force: true });
});
const files: Record<string, string> = {
	"notes/today.md": "# today\nopen note e05c",
	"notes/deep/plan.md": "the plan e05c",
	"notes/shared.md": "an open note named like a denied one",
	"notes/.git/hit.md": "e05c",
	"notes/node_modules/hit.md": "e05c",
	"notes/long.txt": Array.from({ length: 2500 }, (_, i) => `line ${i + 1}`).join("\n"),
	"notes/blob.bin": "e05c\0\0\0",
	".ssh/id_ed25519": SECRET,
	".ssh/notes.md": SECRET,
	[`.password-store/${HIDDEN}.md`]: SECRET,
	".password-store/shared.md": SECRET,
};
for (const [file, text] of Object.entries(files)) {
	mkdirSync(path.dirname(path.join(home, file)), { recursive: true });
	writeFileSync(path.join(home, file), text);
}
symlinkSync("../.ssh/notes.md", path.join(home, "notes/linked.md"));

/**
 * The stand-in prints what memex prints: `vault:list` the vaults and their directories, and a search or a find each
 * vault's notes by their path from its root. A vault `keys` sits on ~/.ssh; `notes` names one note through a symlink
 * into it, one by `..` out of its root, and one under both an open root and a denied one, and quotes a denied note's
 * text as `--full` would. Each call's arguments go to `argv`, one line a call.
 */
const said: Record<string, string> = {
	"vault:list": `keys (model: none)\n  ${home}/.ssh\nnotes\n  ${home}/notes\n  ${home}/.password-store\n`,
	search: [
		"keys",
		"  id_ed25519",
		"  notes.md",
		"",
		"notes",
		"  today.md",
		"  linked.md",
		"  ../.ssh/id_ed25519",
		`  ${HIDDEN}.md`,
		"  shared.md",
		"  deep/plan.md",
		"",
		"--- linked.md [notes] ---",
		"",
		SECRET,
		`${home}/.ssh/notes.md`,
	].join("\n"),
};
said.find = said.search;
const memex = path.join(bin, "memex");
const argv = path.join(bin, "argv");
writeFileSync(memex, `#!/bin/sh\nprintf '%s|' "$@" >> ${argv}; echo >> ${argv}\ncase "$1" in\n${Object.entries(said).map(([command, out]) => `${command}) cat <<'EOF'\n${out}\nEOF\n;;`).join("\n")}\nesac\n`);
chmodSync(memex, 0o755);

const tools = new Map(exploreTools({ home, memex }).map((tool) => [tool.name, tool]));
async function run(name: string, params: object): Promise<string> {
	const result = await tools.get(name)!.execute("check", params as never, undefined, undefined, {} as never);
	return result.content.map((part) => (part.type === "text" ? part.text : "")).join("\n");
}

test("a search or a listing from home passes over the denied roots and reads the rest", async () => {
	const grep = await run("grep", { path: "~", pattern: "e05c|c4n4ry" });
	assert.match(grep, /notes\/today\.md:2: open note e05c/);
	assert.match(grep, /notes\/deep\/plan\.md:1/);
	const find = await run("find", { path: "~", pattern: "*.md" });
	assert.match(find, /notes\/today\.md/);
	const ls = await run("ls", { path: "notes" });
	assert.match(ls, /linked\.md@ → \(denied\)/);
	for (const out of [grep, find, ls]) assert.ok(!out.includes(SECRET) && !out.includes(HIDDEN) && !out.includes(".ssh/"), out);
});

test("hypervisor-property-checks D6: memex's notes from a denied root, and their text, never reach the model", async () => {
	for (const command of ["search", "find"]) {
		for (const vault of [undefined, "notes", "keys"]) {
			const out = await run("memex", { command, query: "anything", ...(vault ? { vault } : {}) });
			assert.ok(!out.includes(SECRET) && !out.includes(HIDDEN), `${command} ${vault}: ${out}`);
			assert.ok(!/id_ed25519|notes\.md|linked|shared/.test(out), `${command} ${vault}: a denied note's path\n${out}`);
			if (vault !== "keys") assert.match(out, /^notes\n {2}~\/notes\/today\.md\n {2}~\/notes\/deep\/plan\.md/, `${command} ${vault}: the open notes under their vault, as read takes them`);
		}
	}
});

test("memex is asked with the model's query after `--`, so a query that looks like an option stays the query", async () => {
	writeFileSync(argv, "");
	await run("memex", { command: "search", query: "--full", vault: "notes", limit: 3 });
	await run("memex", { command: "find", query: "anything", limit: 500 });
	assert.deepEqual(readFileSync(argv, "utf8").trim().split("\n"), ["vault:list|", "search|--limit=3|--vault=notes|--|--full|", "vault:list|", "find|--limit=50|--|anything|"]);
});

test("a search passes over .git and node_modules, and a pattern with a / matches the path from where it starts", async () => {
	assert.doesNotMatch(await run("grep", { path: "notes", pattern: "e05c" }), /hit\.md/);
	assert.doesNotMatch(await run("find", { path: "~", pattern: "hit.md" }), /hit\.md/);
	assert.equal(await run("find", { path: "notes", pattern: "deep/*.md" }), "deep/plan.md");
	assert.equal(await run("find", { path: "~", pattern: "deep/*.md" }), "(nothing)");
});

test("read pages through a long file, and names a binary one without its bytes", async () => {
	const head = await run("read", { path: "notes/long.txt" });
	assert.ok(head.startsWith("line 1\nline 2\n"));
	assert.ok(head.endsWith("line 2000\n(lines 1-2000 of 2500; offset 2001 reads on)"), head.slice(-80));
	assert.equal(await run("read", { path: "notes/long.txt", offset: 2001, limit: 3 }), "line 2001\nline 2002\nline 2003\n(lines 2001-2003 of 2500; offset 2004 reads on)");
	assert.equal(await run("read", { path: "notes/long.txt", offset: 2499 }), "line 2499\nline 2500");
	assert.equal(await run("read", { path: "notes/blob.bin" }), "(a binary file, 7 bytes)");
});

test("the hypervisor's store, which holds its pi's credentials, is denied like the roots", async () => {
	const own = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-explore-store-")));
	try {
		const store = path.join(own, ".local/share/hypervisor");
		mkdirSync(path.join(store, "pi"), { recursive: true });
		writeFileSync(path.join(store, "pi/auth.json"), SECRET);
		writeFileSync(path.join(own, ".local/share/open.md"), "e05c");
		const [read, grep] = ["read", "grep"].map((name) => exploreTools({ home: own, store }).find((tool) => tool.name === name)!);
		await assert.rejects(read.execute("check", { path: "~/.local/share/hypervisor/pi/auth.json" } as never, undefined, undefined, {} as never), /denied/);
		const found = JSON.stringify(await grep.execute("check", { path: "~/.local", pattern: "c4n4ry|e05c" } as never, undefined, undefined, {} as never));
		assert.match(found, /share\/open\.md:1: e05c/);
		assert.doesNotMatch(found, /c4n4ry/);
	} finally {
		rmSync(own, { recursive: true, force: true });
	}
});
