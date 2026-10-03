// `hv tell`: an orchestrator leaves the hypervisor a message, which reaches it as an event within seconds, starting a
// turn of its own when none runs. Run from a tmux pane, the message says which window it came from.

import { execFileSync } from "node:child_process";
import { post } from "./inbox.ts";

export const USAGE = `usage: hv tell <message>...   (or the message on stdin)

Leaves the hypervisor a message: what happened, and where max should look. It names the tmux window it was sent
from, or the directory when it runs outside tmux. It goes to the inbox of the store $HV_STORE, which hv sets.`;

if (import.meta.main) {
	const args = process.argv.slice(2);
	if (args[0] === "--help" || args[0] === "-h") {
		console.log(USAGE);
		process.exit(0);
	}
	const text = (args.length ? args.join(" ") : await stdin()).trim();
	const store = process.env.HV_STORE;
	if (!text || !store) {
		console.error(store ? USAGE : `hv tell: HV_STORE is not set; run it as hv tell\n\n${USAGE}`);
		process.exit(2);
	}
	await post(store, { at: new Date().toISOString(), from: window() ?? process.cwd(), text });
	console.log("Left for the hypervisor.");
}

/** The tmux window this runs in, as `session:window`. */
function window(): string | undefined {
	const pane = process.env.TMUX_PANE;
	if (!pane) return undefined;
	try {
		return execFileSync("tmux", ["display-message", "-p", "-t", pane, "#{session_name}:#{window_name}"], { encoding: "utf8" }).trim() || undefined;
	} catch {
		return undefined;
	}
}

async function stdin(): Promise<string> {
	if (process.stdin.isTTY) return "";
	const chunks: Buffer[] = [];
	for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
	return Buffer.concat(chunks).toString();
}
