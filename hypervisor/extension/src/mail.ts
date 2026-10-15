// What the hypervisor and Jarvis sent each other, gathered from where each message ends up: the receiver's inbox, where
// it stays once read, moved to read/. The hypervisor's inbox is on the laptop; Jarvis's is in its workspace on the VPS,
// read over max's own ssh login, since the hypervisor's mailbox key may only tell, fetch and delete.

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { parsed } from "./inbox.ts";
import { JARVIS } from "./jarvis.ts";
import { run } from "./run.ts";

/** One message as the timeline shows it. */
export interface Mail {
	at: string;
	from: string;
	to: string;
	text: string;
	/** In the receiver's read/: the receiver has read it. */
	read: boolean;
}

/** The hypervisor's name in the timeline. */
export const HV = "hv";

/** Where Jarvis's workspace lies on the VPS host: its Docker volume, as jarvis-mailbox and the backup find it. */
const JARVIS_WORKSPACE = "/var/lib/docker/volumes/jarvis_jarvis-workspace/_data";

/** Every message in the hypervisor's inbox under `store`, read or not: Jarvis's, the orchestrators' and hv tell's. */
export function hypervisorInbox(store: string): Mail[] {
	const dir = path.join(store, "inbox");
	return [
		{ dir, read: false },
		{ dir: path.join(dir, "read"), read: true },
	].flatMap(({ dir, read }) =>
		names(dir, ".json").flatMap((name) => {
			const told = parsed(contents(path.join(dir, name)) ?? "");
			return told ? [{ at: told.at, from: told.from, to: HV, text: told.text, read }] : [];
		}),
	);
}

/**
 * The reports in Jarvis's inbox on `host`, read or not: the hypervisor's, and with `all` every other one too, each from
 * its file's name. A report still being written is a dotfile, so it is left out.
 */
export async function jarvisInbox(host: string, { all = false, workspace = JARVIS_WORKSPACE }: { all?: boolean; workspace?: string } = {}): Promise<Mail[]> {
	const glob = all ? "*" : "hypervisor-*";
	const script = `cd '${workspace}/inbox' 2>/dev/null || exit 0
for f in ${glob} read/${glob}; do [ -f "$f" ] && printf '%s %s %s\\n' "$f" "$(stat -c %Y "$f")" "$(base64 -w0 <"$f")"; done; true`;
	const out = await run("ssh", ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, script], { timeout: 30_000 });
	return out
		.split("\n")
		.filter(Boolean)
		.map((line) => {
			const [file = "", mtime, text] = line.split(" ");
			const name = path.basename(file);
			return {
				at: new Date(Number(mtime) * 1000).toISOString(),
				from: name.startsWith("hypervisor-") ? HV : name.replace(/\.[^.]*$/, ""),
				to: JARVIS,
				text: Buffer.from(text ?? "", "base64").toString("utf8").trim(),
				read: file.startsWith("read/"),
			};
		});
}

/** Which messages the timeline keeps; `since` and `until` are epoch milliseconds, `last` how many of the newest. */
export interface Filter {
	/** Also the orchestrators' messages to the hypervisor and the other reports in Jarvis's inbox. */
	all?: boolean;
	since?: number;
	until?: number;
	last?: number;
}

/** The messages `filter` keeps, oldest first. */
export function timeline(mails: Mail[], { all = false, since, until, last }: Filter = {}): Mail[] {
	const between = (m: Mail) => (m.from === JARVIS && m.to === HV) || (m.from === HV && m.to === JARVIS);
	const kept = mails
		.filter((m) => all || between(m))
		.filter((m) => (since === undefined || Date.parse(m.at) >= since) && (until === undefined || Date.parse(m.at) < until))
		.sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
	return last === undefined ? kept : kept.slice(Math.max(0, kept.length - last));
}

/** `when` as an instant: a bare date is that day's start in local time, or the next day's with `end`. */
export function instant(when: string, end = false): number {
	const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(when);
	const at = day ? new Date(Number(day[1]), Number(day[2]) - 1, Number(day[3]) + (end ? 1 : 0)).getTime() : Date.parse(when);
	if (Number.isNaN(at)) throw new Error(`${when} is no date; give 2026-10-15 or 2026-10-15T08:00`);
	return at;
}

/** A message as the timeline prints it: when, in local time, who to whom, unread or not, then its text indented. */
export function render(m: Mail): string {
	const d = new Date(m.at);
	const p = (n: number) => String(n).padStart(2, "0");
	const when = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
	const text = m.text.replace(/^/gm, "    ");
	return `${when}  ${m.from} → ${m.to}${m.read ? "" : "  (unread)"}\n${text}\n`;
}

/** What tells one message from another, the same before and after its receiver reads it. */
export function identity(m: Mail): string {
	return JSON.stringify([m.at, m.from, m.to, m.text]);
}

function names(dir: string, suffix: string): string[] {
	try {
		return readdirSync(dir).filter((name) => name.endsWith(suffix) && !name.startsWith("."));
	} catch {
		return [];
	}
}

/** A file's text, or nothing when it moved to read/ between the listing and the read. */
function contents(file: string): string | undefined {
	try {
		return readFileSync(file, "utf8");
	} catch {
		return undefined;
	}
}
