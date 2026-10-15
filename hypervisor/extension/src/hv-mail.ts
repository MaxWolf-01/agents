// `hv mail`: what the hypervisor and Jarvis sent each other, as one timeline, for max to look into.

import { setTimeout as sleep } from "node:timers/promises";
import { type Filter, hypervisorInbox, identity, instant, jarvisInbox, type Mail, render, timeline } from "./mail.ts";

export const USAGE = `usage: hv mail [--all] [--since DATE] [--until DATE] [-n N] [-f] [--json]

Prints what the hypervisor and Jarvis sent each other, oldest first, read and unread alike: the hypervisor's inbox on
the laptop, in the store $HV_STORE, which hv sets, and Jarvis's inbox on the VPS, which it reads as $HV_JARVIS_HOST
(default jarvis) over your own ssh login, in the workspace $HV_JARVIS_WORKSPACE (default its Docker volume). A message
Jarvis has sent waits in its outbox until hv fetch brings it over, and shows from then on.

  --all          also what orchestrators sent the hypervisor and the other reports in Jarvis's inbox
  --since DATE   from DATE on; a bare date (2026-10-15) is that day's start, in local time
  --until DATE   before DATE; a bare date counts that whole day
  -n N           only the N newest
  -f             keep printing messages as they arrive, every 15 seconds
  --json         one JSON object per message and line: at, from, to, text, read`;

const POLL_MS = 15_000;

if (import.meta.main) {
	let options: ReturnType<typeof parse>;
	try {
		options = parse(process.argv.slice(2));
	} catch (error) {
		console.error(`hv mail: ${(error as Error).message}\n\n${USAGE}`);
		process.exit(2);
	}
	if (options.help) {
		console.log(USAGE);
		process.exit(0);
	}
	const store = process.env.HV_STORE;
	if (!store) {
		console.error(`hv mail: HV_STORE is not set; run it as hv mail\n\n${USAGE}`);
		process.exit(2);
	}
	const host = process.env.HV_JARVIS_HOST ?? "jarvis";
	const print = (m: Mail) => console.log(options.json ? JSON.stringify(m) : render(m));
	let warned = false;
	const gather = async () => {
		let remote: Mail[] = [];
		try {
			remote = await jarvisInbox(host, { all: options.filter.all, workspace: process.env.HV_JARVIS_WORKSPACE });
		} catch (error) {
			if (!warned) console.error(`hv mail: Jarvis's inbox left out, ${(error as Error).message}`);
			warned = true;
		}
		return [...hypervisorInbox(store), ...remote];
	};
	const seen = new Set<string>();
	for (const m of timeline(await gather(), options.filter)) {
		seen.add(identity(m));
		print(m);
	}
	while (options.follow) {
		await sleep(POLL_MS);
		const { last: _, ...filter } = options.filter;
		for (const m of timeline(await gather(), filter)) {
			if (seen.has(identity(m))) continue;
			seen.add(identity(m));
			print(m);
		}
	}
}

/** The command line's options. */
export function parse(args: string[]): { filter: Filter; follow: boolean; json: boolean; help: boolean } {
	const filter: Filter = {};
	let follow = false;
	let json = false;
	let help = false;
	for (let i = 0; i < args.length; i++) {
		const value = () => {
			const v = args[++i];
			if (v === undefined) throw new Error(`${args[i - 1]} needs a value`);
			return v;
		};
		switch (args[i]) {
			case "--all":
				filter.all = true;
				break;
			case "--since":
				filter.since = instant(value());
				break;
			case "--until":
				filter.until = instant(value(), true);
				break;
			case "-n": {
				const n = value();
				if (!/^\d+$/.test(n)) throw new Error(`-n takes a count, not ${n}`);
				filter.last = Number(n);
				break;
			}
			case "-f":
			case "--follow":
				follow = true;
				break;
			case "--json":
				json = true;
				break;
			case "-h":
			case "--help":
				help = true;
				break;
			default:
				throw new Error(`no option ${args[i]}`);
		}
	}
	return { filter, follow, json, help };
}
