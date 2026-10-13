// `hv explore`: explore steps on the hypervisor's own profile, as `/explore` runs them (`exploring.ts`). A profile
// takes one pi at a time, so with the hypervisor's TUI open the command is typed into its pane; with it closed, the
// run goes headless, in a pi `hv` starts over RPC, and prints each step's finding as it goes. `hv explore --found`
// prints what the latest run found.

import { execFileSync, spawn } from "node:child_process";
import path from "node:path";
import { ENDED, NOTICE, parse, REFUSED, USAGE as COMMAND } from "./exploring.ts";
import { lines } from "./journal.ts";
import { summarized } from "./recipe-run.ts";

export const USAGE = `usage: hv explore N [direction] [--tokens T] [--until-week P]
       hv explore --found

Runs up to N explore steps on the hypervisor's own memory, as /explore does in its TUI:
${COMMAND.split("\n").slice(1).join("\n")}
With the TUI open, the command is typed into its pane, and the run goes on there. With --found, prints what the
latest run found, from $HV_STORE/explore.jsonl.`;

/** The tmux session `hv` runs the TUI in. */
const SESSION = "=hypervisor";

/** A line of `explore.jsonl`: a step's finding, a run's end, or an offer. */
interface Line {
	at: string;
	run?: string;
	step?: number;
	direction?: string;
	finding?: string;
	tokens?: number;
	error?: string;
	ended?: string;
	steps?: number;
	week?: number;
}

/** What the latest run in the store's journal found, step by step, and how it ended, as text; or that no run is there. */
export async function found(store: string): Promise<string> {
	const all = (await lines<Line>(store, "explore.jsonl")).filter((line) => line.run);
	const run = all.at(-1)?.run;
	if (!run) return "No explore run yet.";
	const mine = all.filter((line) => line.run === run);
	const out = [`Explore run of ${run.slice(0, 16)}Z${mine[0]?.direction ? `, toward ${mine[0].direction}` : ""}:`];
	for (const line of mine) {
		if (line.step !== undefined) out.push(`\nstep ${line.step}, ${line.tokens} tokens:${line.error ? ` failed: ${line.error}` : `\n${line.finding}`}`);
		if (line.ended) out.push(`\nEnded after ${line.steps} steps, ${line.tokens} tokens: stopped by ${line.ended}.${line.week === undefined ? "" : ` The week at ${line.week}%.`}`);
	}
	if (!mine.some((line) => line.ended)) out.push("\nIt has not ended yet, or its pi stopped before it could.");
	return out.join("\n");
}

/** Whether the hypervisor's TUI runs, in its tmux session. */
function tuiOpen(): boolean {
	try {
		execFileSync("tmux", ["has-session", "-t", SESSION], { stdio: "ignore" });
		return true;
	} catch {
		return false;
	}
}

/**
 * Runs `/explore args` in the pi that `command` starts over RPC, printing what the run notifies, and resolves with the
 * exit code once the run has ended and the profile's summaries are written: 1 when pi or an extension failed.
 */
export function headless(args: string, command: string[], profile: string): Promise<number> {
	return new Promise((resolve) => {
		const pi = spawn(command[0]!, [...command.slice(1), "--mode", "rpc"], { stdio: ["pipe", "pipe", "inherit"] });
		pi.stdout!.setEncoding("utf8");
		let buffer = "";
		let code = 0;
		let ending = false;
		const end = async (failed: boolean) => {
			if (ending) return;
			ending = true;
			if (failed) code = 1;
			else await summarized(profile);
			pi.stdin!.end();
		};
		pi.on("close", (exit) => resolve(code || (ending ? 0 : exit || 1)));
		pi.stdout!.on("data", (chunk: string) => {
			buffer += chunk;
			for (let at = buffer.indexOf("\n"); at >= 0; at = buffer.indexOf("\n")) {
				const line = buffer.slice(0, at);
				buffer = buffer.slice(at + 1);
				let record: { type?: string; method?: string; message?: string; error?: string; extensionPath?: string; event?: string };
				try {
					record = JSON.parse(line);
				} catch {
					continue;
				}
				// A profile that cannot open, open in another pi among the reasons, fails its extension's session_start.
				if (record.type === "extension_error") {
					console.error(`hv explore: ${record.extensionPath} failed in ${record.event}: ${record.error}`);
					void end(true);
				}
				if (record.type === "extension_ui_request" && record.method === "notify" && record.message?.startsWith(NOTICE)) {
					console.log(record.message);
					if (record.message.startsWith(ENDED)) void end(record.message.startsWith(REFUSED));
				}
			}
		});
		pi.stdin!.write(`${JSON.stringify({ type: "prompt", message: `/explore ${args}` })}\n`);
	});
}

if (import.meta.main) {
	const argv = process.argv.slice(2);
	const split = argv.indexOf("--");
	const args = split < 0 ? argv : argv.slice(0, split);
	const command = split < 0 ? [] : argv.slice(split + 1);
	const store = process.env.HV_STORE;
	if (args[0] === "--help" || args[0] === "-h") {
		console.log(USAGE);
		process.exit(0);
	}
	if (!store) {
		console.error(`hv explore: HV_STORE is not set; run it as hv explore\n\n${USAGE}`);
		process.exit(2);
	}
	if (args[0] === "--found") {
		console.log(await found(store));
		process.exit(0);
	}
	const request = parse(args.join(" "));
	if (typeof request === "string") {
		console.error(`hv explore: ${request}\n\n${USAGE}`);
		process.exit(2);
	}
	if (tuiOpen()) {
		// Literal keys, then Enter on its own, so nothing in the direction reads as a key name.
		execFileSync("tmux", ["send-keys", "-t", SESSION, "-l", `/explore ${args.join(" ")}`]);
		execFileSync("tmux", ["send-keys", "-t", SESSION, "Enter"]);
		console.log("The hypervisor's TUI is open: typed /explore into its pane, where the run goes on (tmux attach -t hypervisor).");
		process.exit(0);
	}
	const profile = process.env.OPTCHAT_HOME && process.env.HV_PROFILE ? path.join(process.env.OPTCHAT_HOME, "profiles", process.env.HV_PROFILE) : undefined;
	if (!command.length || !profile) {
		console.error(`hv explore: no pi to run, or no profile (OPTCHAT_HOME, HV_PROFILE); run it as hv explore\n\n${USAGE}`);
		process.exit(2);
	}
	process.exit(await headless(args.join(" "), command, profile));
}
