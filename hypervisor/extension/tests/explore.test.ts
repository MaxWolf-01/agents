// The explorer's tools over a small home, beside the P5 properties: a search from home passes over every denied root,
// and memex's answer passes through the same denylist (hypervisor-property-checks D6), run against a stand-in for
// memex's command line that answers with notes from a denied root, their text, and notes that are open.

import assert from "node:assert/strict";
import { chmodSync, mkdirSync, mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
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
	".ssh/id_ed25519": SECRET,
	".ssh/notes.md": SECRET,
	[`.password-store/${HIDDEN}.md`]: SECRET,
};
for (const [file, text] of Object.entries(files)) {
	mkdirSync(path.dirname(path.join(home, file)), { recursive: true });
	writeFileSync(path.join(home, file), text);
}
symlinkSync("../.ssh/notes.md", path.join(home, "notes/linked.md"));

/**
 * The stand-in prints what memex prints: `vault:list` the vaults and their directories, and a search or a find each
 * vault's notes by their path from its root. A vault `keys` sits on ~/.ssh; `notes` names one note through a symlink
 * into it and one by `..` out of its root, and quotes a denied note's text as `--full` would.
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
writeFileSync(memex, `#!/bin/sh\ncase "$1" in\n${Object.entries(said).map(([command, out]) => `${command}) cat <<'EOF'\n${out}\nEOF\n;;`).join("\n")}\nesac\n`);
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
			assert.ok(!/id_ed25519|notes\.md|linked/.test(out), `${command} ${vault}: a denied note's path\n${out}`);
			if (vault !== "keys") assert.match(out, /^notes\n {2}~\/notes\/today\.md\n {2}~\/notes\/deep\/plan\.md/, `${command} ${vault}: the open notes under their vault, as read takes them`);
		}
	}
});
