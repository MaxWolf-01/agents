// lifelong-hypervisor#P5 at the explorer's read tools, over a fixture home: every denied root holds a secret in its
// files' content and in a file's name, and the open part of home holds symlinks into the denied roots. Paths into a
// denied root are generated in every spelling that reaches it, and searches and listings sweep the parts around them.

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import type { ToolDefinition } from "@earendil-works/pi-coding-agent";
import fc from "fast-check";
import { exploreTools } from "../../src/explore.ts";
import { isStub, liftedBy } from "./lifted-by.ts";
import { paramsFor } from "./params.ts";

const SECRET = "c4n4ry-content-7f3a91";
const HIDDEN = "c4n4ry-name-52bd07";
const OPEN = "open-content-e05c";

/** A root of each kind the parent denies: `~/work`, keys, secrets and credential stores, browser profiles. */
const DENIED = [
	"work",
	".ssh",
	".gnupg",
	".password-store",
	".local/share/keyrings",
	".aws",
	".config/gh",
	".netrc",
	".git-credentials",
	".claude/.credentials.json",
	".mozilla",
	".config/google-chrome",
	".config/chromium",
];
const FILES = new Set([".netrc", ".git-credentials", ".claude/.credentials.json"]);
/** Open files, some beside a denied root or named like one, so a check by prefix refuses them. */
const READABLE = ["workshop/plan.md", "notes/today.md", ".config/nvim/init.lua", ".claude/settings.json"];
/** Symlinks in the open part of home, from the link to its target. */
const LINKS: Record<string, string> = {
	"notes/to-work": "../work",
	"notes/chain": "to-work",
	"notes/key": "../.ssh/notes.txt",
	"notes/up": "..",
	"workshop/creds": "../.claude/.credentials.json",
	"notes/open": "../workshop/plan.md",
};

const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-explore-")));
after(() => rmSync(home, { recursive: true, force: true }));
for (const root of DENIED) {
	const at = path.join(home, root);
	mkdirSync(FILES.has(root) ? path.dirname(at) : path.join(at, "deep"), { recursive: true });
	if (FILES.has(root)) writeFileSync(at, SECRET);
	else for (const file of ["notes.txt", "deep/inner.txt", `${HIDDEN}.txt`]) writeFileSync(path.join(at, file), SECRET);
}
for (const file of READABLE) {
	mkdirSync(path.dirname(path.join(home, file)), { recursive: true });
	writeFileSync(path.join(home, file), OPEN);
}
for (const [link, target] of Object.entries(LINKS)) symlinkSync(target, path.join(home, link));
symlinkSync(path.join(home, ".ssh"), path.join(home, "notes/to-ssh"));

/** A place under a denied root, named from home, directly or through one of the symlinks. */
const denied = fc.oneof(
	fc.constantFrom(...DENIED).chain((root) => (FILES.has(root) ? fc.constant(root) : fc.constantFrom(root, `${root}/notes.txt`, `${root}/deep`, `${root}/deep/inner.txt`, `${root}/missing.txt`))),
	fc.constantFrom(
		"notes/to-work",
		"notes/to-work/notes.txt",
		"notes/chain/deep/inner.txt",
		"notes/key",
		"notes/to-ssh/notes.txt",
		"notes/up/work/notes.txt",
		"notes/up/.config/gh",
		"workshop/creds",
		// The kernel walks `..` from where the link points, not from the link: this is ~/.ssh, not ~/notes/.ssh.
		"notes/to-work/../.ssh/notes.txt",
	),
);
/** Places around the denied roots that a search or a listing would pass through. */
const around = fc.constantFrom("", "notes", "notes/up", ".config", ".claude", "workshop", ".local");

/** The spellings a path can take: absolute, under `~/`, relative to home, with detours, through /proc. */
function spellings(rel: string): fc.Arbitrary<string> {
	const plain = rel === "" ? "." : rel;
	return fc.constantFrom(
		path.join(home, rel),
		`~/${rel}`,
		plain,
		`workshop/../${plain}`,
		`./notes/./../${plain}`,
		`${home}//${rel.replaceAll("/", "//")}`,
		`${home}/${rel}/`,
		`/proc/self/root${home}/${rel}`,
	);
}

/** Search patterns that match the secret's file or text without spelling the secret itself. */
const searches = fc.constantFrom("c4n4ry", "7f3a9[0-9]", "52bd0", ".", "*", "**/*", "**", "");

async function outcome(tool: ToolDefinition, params: unknown): Promise<{ threw: boolean; said: string }> {
	let timer: NodeJS.Timeout | undefined;
	const late = new Promise<never>((_, fail) => {
		timer = setTimeout(() => fail(new Error(`${tool.name} did not finish in 5s`)), 5000);
	});
	try {
		const result = await Promise.race([tool.execute("p5", params as never, undefined, undefined, { cwd: home } as never), late]);
		return { threw: false, said: JSON.stringify(result) };
	} catch (error) {
		if (isStub(error) || (error instanceof Error && error.message.endsWith("did not finish in 5s"))) throw error;
		return { threw: true, said: error instanceof Error ? `${error.message}\n${error.stack}` : String(error) };
	} finally {
		clearTimeout(timer);
	}
}

const attack = (tools: ToolDefinition[]) =>
	fc.constantFrom(...tools).chain((tool) =>
		fc.oneof(denied.map((rel) => ({ rel, refused: true })), around.map((rel) => ({ rel, refused: false }))).chain(({ rel, refused }) =>
			spellings(rel).chain((spelled) => paramsFor(tool.parameters as never, searches, { path: fc.constant(spelled) }).map((params) => ({ tool, params, refused }))),
		),
	);

test("lifelong-hypervisor#P5: the explorer reads nothing under a denied root, however the path is spelled", liftedBy("hypervisor-explore-mode"), async () => {
	const tools = exploreTools({ home });
	await fc.assert(
		fc.asyncProperty(attack(tools), async ({ tool, params, refused }) => {
			const { threw, said } = await outcome(tool, params);
			assert.ok(!said.includes(SECRET) && !said.includes(HIDDEN), `${tool.name} ${JSON.stringify(params)} read a denied file:\n${said}`);
			if (refused && "path" in params) assert.ok(threw, `${tool.name} did not refuse ${JSON.stringify(params)}`);
		}),
		{ numRuns: 300 },
	);
});

// Refusing everything would satisfy the property above; the explorer has to read the open part of home.
test("lifelong-hypervisor#P5: a file outside the denied roots reads back through the read tools", liftedBy("hypervisor-explore-mode"), async () => {
	const tools = exploreTools({ home }).filter((tool) => (tool.parameters as { properties?: object }).properties && "path" in (tool.parameters as { properties: object }).properties);
	await fc.assert(
		fc.asyncProperty(fc.constantFrom(...READABLE, "notes/open", "notes/up/workshop/plan.md").chain(spellings), async (spelled) => {
			const reads = await Promise.all(tools.map((tool) => outcome(tool, minimal(tool, spelled))));
			assert.ok(reads.some(({ said }) => said.includes(OPEN)), `no read tool read ${spelled}`);
		}),
	);
});

/** The fewest arguments a tool takes: the path, and each other required one at a plain value. */
function minimal(tool: ToolDefinition, spelled: string): Record<string, unknown> {
	const schema = tool.parameters as { properties: Record<string, { type?: string }>; required?: string[] };
	const plain: Record<string, unknown> = { string: "e05c", number: 1, integer: 1, boolean: false };
	return Object.fromEntries((schema.required ?? []).map((name) => [name, name === "path" ? spelled : plain[schema.properties[name]?.type ?? "string"]]).concat([["path", spelled]]));
}
