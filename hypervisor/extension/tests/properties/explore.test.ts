// lifelong-hypervisor#P5 at the explorer's read tools, over a fixture home: every denied root holds a secret in its
// files' content and in a file's name, and symlinks lead into the denied roots from the open part of home and from
// outside it. A process holds the secret in its environment, under /proc. Paths into a denied root are generated in
// every spelling that reaches it, and searches and listings sweep the parts around them. memex runs as a stand-in that
// names, among the notes it finds, the path it was asked for and notes in denied roots, and quotes the secret.

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import type { ToolDefinition } from "@earendil-works/pi-coding-agent";
import fc from "fast-check";
import { exploreTools } from "../../src/explore.ts";
import { paramsFor } from "./params.ts";
import { execute, standIn } from "./stand-in.ts";

const SECRET = "c4n4ry-content-7f3a91";
const HIDDEN = "c4n4ry-name-52bd07";
const OPEN = "open-content-e05c";

/**
 * The denied roots under home: keys, credential stores, browser profiles and caches, and the hypervisor's store's
 * `pi/`, which holds its own pi's credentials. `~/work` is readable, and so is `~/.dotfiles/secrets` but for the
 * store at `creds`.
 */
const DENIED = [
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
	".config/BraveSoftware",
	".cache/chromium",
	".config/rclone",
	".config/sops",
	".docker",
	".pi/agent/auth.json",
	".codex/auth.json",
	".dotfiles/secrets/creds",
	".local/share/hypervisor/pi",
];
/** The hypervisor's store, where it lies unless `$HV_STORE` moves it. */
const STORE = ".local/share/hypervisor";
const FILES = new Set([".netrc", ".git-credentials", ".claude/.credentials.json", ".pi/agent/auth.json", ".codex/auth.json"]);
/** Open files, some beside a denied root or named like one, so a check by prefix refuses them. */
const READABLE = [
	"workshop/plan.md",
	"notes/today.md",
	"work/notes.md",
	".config/nvim/init.lua",
	".claude/settings.json",
	".pi/agent/settings.json",
	".codex/config.toml",
	".dotfiles/secrets/readme.md",
	".dotfiles/secrets/creds-old.md",
];
/** Symlinks in the open part of home, from the link to its target. */
const LINKS: Record<string, string> = {
	"notes/to-work": "../work",
	"notes/to-docker": "../.docker",
	"notes/chain": "to-docker",
	"notes/key": "../.ssh/notes.txt",
	"notes/up": "..",
	"workshop/creds": "../.claude/.credentials.json",
	"notes/open": "../workshop/plan.md",
};

const home = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-explore-")));
const outside = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-outside-")));
const bin = realpathSync(mkdtempSync(path.join(tmpdir(), "hv-memex-")));
// It lives as long as its stdin stays open, so it ends with the check however the check ends.
const holder = spawn(process.execPath, ["-e", "process.stdin.on('end', () => process.exit()).resume()"], { env: { HV_TOKEN: SECRET }, stdio: ["pipe", "ignore", "ignore"] });
after(() => {
	holder.kill();
	rmSync(home, { recursive: true, force: true });
	rmSync(outside, { recursive: true, force: true });
	rmSync(bin, { recursive: true, force: true });
});
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
symlinkSync(path.join(home, ".gnupg"), path.join(outside, "gpg"));
symlinkSync(`/proc/${holder.pid}`, path.join(home, "notes/to-proc"));

/**
 * memex as it prints: `vault:list` the vaults and their directories, and a search or a find each vault's notes by
 * their path from its root, with a quoted note's text as `--full` prints it. Every answer names the query itself as
 * a note, so the paths generated for the read tools reach memex's judgment too.
 */
const memex = path.join(bin, "memex");
const notes = ["notes/today.md", `.ssh/${HIDDEN}.txt`, `notes/to-ssh/${HIDDEN}.txt`, `notes/up/.docker/${HIDDEN}.txt`, `${STORE}/pi/${HIDDEN}.txt`, `/proc/${holder.pid}/environ`];
writeFileSync(
	memex,
	`#!/bin/sh
case "$1" in
vault:list) printf '%s\\n' 'home (model: none)' '  ${home}' keys '  ${home}/.ssh' ;;
*) for query; do :; done
	printf 'home\\n'; printf '  %s\\n' "$query" ${notes.map((note) => `'${note}'`).join(" ")}
	printf 'keys\\n  %s\\n  notes.txt\\n\\n%s\\n' '${HIDDEN}.txt' '${SECRET}' ;;
esac
`,
);
chmodSync(memex, 0o755);

const name = fc.stringMatching(/^[a-z][a-z0-9_-]{0,7}$/);
/** Below a denied directory: a file it holds, a directory, or a name that is not there, any number of levels down. */
const tail = fc.array(fc.oneof(fc.constantFrom("notes.txt", "deep", "inner.txt"), name), { maxLength: 3 });
/** A detour that comes back where it left: `x/..`, `x/y/../..`, or `.`. */
const detour = fc.oneof(fc.constant("."), fc.array(name, { minLength: 1, maxLength: 2 }).map((names) => [...names, ...names.map(() => "..")].join("/")));

/** Segments joined, with a detour spliced in at each place `detours` names. */
function spliced(segments: string[], detours: [number, string][]): string {
	const out = [...segments];
	for (const [at, d] of detours) out.splice(at % (out.length + 1), 0, d);
	return out.join("/");
}

/** A path into a denied root, from home: the root itself, below it, or through a symlink to it, with detours. */
const intoDenied = fc
	.tuple(
		fc.oneof(
			fc.constantFrom(...DENIED).map((root) => root.split("/")),
			fc.constantFrom(...DENIED).map((root) => ["notes", "up", ...root.split("/")]),
			// Each leads into a denied directory. The kernel walks `..` from where a link points, not from the link,
			// so the last is ~/.ssh and not ~/notes/.ssh.
			fc.constantFrom<string[]>(["notes", "to-docker"], ["notes", "chain"], ["notes", "to-ssh"], ["notes", "to-docker", "..", ".ssh"], ["notes", "to-proc"]),
		),
		tail,
		fc.array(fc.tuple(fc.nat(), detour), { maxLength: 2 }),
	)
	.map(([route, below, detours]) => spliced(FILES.has(route.join("/")) ? route : [...route, ...below], detours));
/** Links straight to a denied file. */
const toDeniedFile = fc.constantFrom("notes/key", "workshop/creds");
/** Places around the denied roots that a search or a listing passes through. */
const around = fc.constantFrom("", "notes", "notes/up", ".config", ".claude", "workshop", "work", ".local", STORE, ".cache", ".pi/agent", ".codex", ".dotfiles/secrets");

/** The spellings of a path from home that name the place itself: absolute, under `~/`, relative, doubled slashes, /proc. */
function spellings(rel: string): fc.Arbitrary<string> {
	return fc.constantFrom(path.join(home, rel), `~/${rel}`, rel === "" ? "." : rel, `${home}//${rel.replaceAll("/", "//")}`, `/proc/self/root${home}/${rel}`);
}
/** Those, and spellings a tool may reject outright: a trailing slash, a URL. */
const anySpelling = (rel: string) => fc.oneof(spellings(rel), fc.constantFrom(`${home}/${rel}/`, `file://${home}/${rel}`));
/** A path into a denied root from outside home, through a symlink there. */
const fromOutside = fc.tuple(tail, fc.constantFrom(`${outside}/gpg`, `/proc/self/root${outside}/gpg`)).map(([below, link]) => [link, ...below].join("/"));
/**
 * A path under /proc: to the process holding the secret, by its pid or as `self`, and below. Only names that stay
 * in /proc: `root`, `cwd` and `exe` there are links out of it.
 */
const inProc = fc
	.tuple(fc.constantFrom("/proc", `/proc/${holder.pid}`, "/proc/self", `/proc/self/root/proc/${holder.pid}`), fc.array(fc.constantFrom("environ", "cmdline", "status", "task", "fd"), { maxLength: 2 }))
	.map(([at, below]) => [at, ...below].join("/"));

/** Search patterns that match the secret's file or text without spelling the secret itself. */
const searches = fc.constantFrom("c4n4ry", "7f3a9[0-9]", "52bd0", ".", "*", "**/*", "**", "");

const target = fc.oneof(
	fc.oneof(intoDenied, toDeniedFile).chain(anySpelling).map((spelled) => ({ spelled, denied: true })),
	fc.oneof(fromOutside, inProc).map((spelled) => ({ spelled, denied: true })),
	around.chain(anySpelling).map((spelled) => ({ spelled, denied: false })),
);
/** A tool, and arguments that point every string at the target or search with it; `path` always names the target. */
const attack = (tools: ToolDefinition[]) =>
	fc.tuple(fc.constantFrom(...tools), target).chain(([tool, { spelled, denied }]) =>
		paramsFor(tool.parameters, fc.oneof(searches, fc.constant(spelled)), { path: fc.constant(spelled) }).map((params) => ({ tool, params, denied })),
	);

const context = standIn({ cwd: home });

test("lifelong-hypervisor#P5: the explorer reads nothing under a denied root, however the path is spelled", async () => {
	const tools = exploreTools({ home, store: path.join(home, STORE), memex });
	await fc.assert(
		fc.asyncProperty(attack(tools), async ({ tool, params, denied }) => {
			const { end, said } = await execute(tool, params, context, 5000);
			assert.notEqual(end, "late", `${tool.name} ${JSON.stringify(params)} did not finish in 5s`);
			if (tool.name === "memex") assert.equal(end, "returned", `memex ${JSON.stringify(params)} did not answer:\n${said}`);
			assert.ok(!said.includes(SECRET) && !said.includes(HIDDEN), `${tool.name} ${JSON.stringify(params)} read a denied file:\n${said}`);
			if (denied && "path" in params) assert.equal(end, "threw", `${tool.name} did not refuse ${JSON.stringify(params)}`);
		}),
		{ numRuns: 300 },
	);
});

// Refusing everything would satisfy the property above; the explorer has to read the open part of home.
test("lifelong-hypervisor#P5: a file outside the denied roots reads back through the read tools", async () => {
	const tools = exploreTools({ home, store: path.join(home, STORE), memex }).filter((tool) => "path" in ((tool.parameters as { properties?: object }).properties ?? {}));
	await fc.assert(
		fc.asyncProperty(fc.constantFrom(...READABLE, "notes/open", "notes/to-work/notes.md", "notes/up/.dotfiles/secrets/readme.md").chain(spellings), async (spelled) => {
			const reads = await Promise.all(tools.map((tool) => execute(tool, minimal(tool, spelled), context, 5000)));
			assert.ok(reads.some(({ said }) => said.includes(OPEN)), `no read tool read ${spelled}`);
		}),
	);
});

/** The fewest arguments a tool takes: the path, and each other required one at a plain value. */
function minimal(tool: ToolDefinition, spelled: string): Record<string, unknown> {
	const schema = tool.parameters as { properties: Record<string, { type?: string }>; required?: string[] };
	const plain: Record<string, unknown> = { string: "e05c", number: 1, integer: 1, boolean: false };
	return Object.fromEntries((schema.required ?? []).map((key) => [key, plain[schema.properties[key]?.type ?? "string"]]).concat([["path", spelled]]));
}
