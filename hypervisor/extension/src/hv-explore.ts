// `hv explore`: explore steps on the hypervisor's own profile, as `/explore` runs them in its TUI (`exploring.ts`). The run
// lives in the TUI alone: with it open, the command is typed into its pane; with it closed, the command `hv` passes
// after `--` starts it, with the command as pi's first message, which pi runs once every extension has started. `hv explore --found` prints what the
// latest run found.

import { execFileSync } from "node:child_process";
import { parse, USAGE as COMMAND } from "./exploring.ts";
import { lines } from "./journal.ts";

export const USAGE = `usage: hv explore N [direction] [--tokens T] [--until-week P]
       hv explore --found

Runs up to N explore steps on the hypervisor's own memory, as /explore does in its TUI:
${COMMAND.split("\n").slice(1).join("\n")}
The command goes to the TUI, which hv starts when it does not run; the run goes on there (tmux attach -t hypervisor).
With --found, prints what the latest run found, from $HV_STORE/explore.jsonl.`;

/** The tmux session `hv` runs the TUI in, and its pane: a bare `=session` names no pane, so send-keys takes the colon. */
const SESSION = "=hypervisor";
const PANE = `${SESSION}:`;

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
	week?: number | "unread";
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
		if (line.ended) out.push(`\nEnded after ${line.steps} ${line.steps === 1 ? "step" : "steps"}, ${line.tokens} tokens: stopped by ${line.ended}.${line.week === undefined ? "" : line.week === "unread" ? " The week's quota was never read." : ` The week at ${line.week}%.`}`);
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

if (import.meta.main) {
	const argv = process.argv.slice(2);
	const split = argv.indexOf("--");
	const args = split < 0 ? argv : argv.slice(0, split);
	const start = split < 0 ? [] : argv.slice(split + 1);
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
	const command = `/explore ${args.join(" ")}`;
	if (tuiOpen()) {
		// Literal keys, then Enter on its own, so nothing in the direction reads as a key name.
		execFileSync("tmux", ["send-keys", "-t", PANE, "-l", command]);
		execFileSync("tmux", ["send-keys", "-t", PANE, "Enter"]);
		console.log("The hypervisor's TUI is open, so /explore was typed into its pane: see there that the run started (tmux attach -t hypervisor). A draft in its editor would have taken the text.");
		process.exit(0);
	}
	if (!start.length) {
		console.error(`hv explore: the TUI does not run, and nothing was given to start it; run it as hv explore\n\n${USAGE}`);
		process.exit(2);
	}
	execFileSync(start[0]!, [...start.slice(1), command], { stdio: "inherit" });
	console.log("The hypervisor's TUI started, with /explore as its first message: the run goes on there (tmux attach -t hypervisor).");
}
