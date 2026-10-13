import { take } from "./inbox.ts";
import { alive, registry, type Session, type Spawned, spawnedWindows } from "./sessions.ts";

/** What a look throws to leave everything for the next one, when `deliver` cannot take events now. */
const NOT_READY = new Error("not ready for events");

/** A watched session's state at one look: its status, and the window it is known by. */
export interface Seen {
	status: string;
	window: string;
}

/**
 * Looks at the spawned sessions and the inbox once at the start and every `ms` after, and hands `deliver` the events
 * since the last look, if any. The first look, which `started` resolves after, only learns the sessions' states. A
 * look that fails goes to `failed`, and the next one starts from the states the last good one saw; so does a look that
 * has events while `ready` says `deliver` cannot take them, or that `deliver` refuses by returning `false`, and it
 * leaves the inbox as it is. Reads files alone: the registry, and the store's own.
 */
export function watch(
	{ home, store }: { home: string; store: string },
	ms: number,
	deliver: (events: string[]) => boolean | void,
	failed: (error: unknown) => void,
	ready: () => boolean = () => true,
) {
	let seen: Map<number, Seen> | undefined;
	let looking = false;
	const look = async () => {
		if (looking) return;
		looking = true;
		try {
			const now = watched(await registry(home), await spawnedWindows(store));
			// A registry file caught mid-write reads as no session; only a process that is gone has ended.
			for (const [pid, was] of seen ?? []) if (!now.has(pid) && alive(pid)) now.set(pid, was);
			const changed = seen ? changes(seen, now) : [];
			await take(store, (told) => {
				const events = [...changed, ...told.map((t) => `[${t.from}] hv tell: ${t.text}`)];
				if (events.length && (!ready() || deliver(events) === false)) throw NOT_READY;
			});
			seen = now;
		} catch (error) {
			if (error !== NOT_READY) failed(error);
		} finally {
			looking = false;
		}
	};
	const timer = setInterval(() => void look(), ms);
	timer.unref();
	return { look, stop: () => clearInterval(timer), started: look() };
}

/**
 * What changed between two looks at the watched sessions, an event each: a session that was busy and is not any more
 * (its turn ended), and a session that is gone.
 */
export function changes(before: Map<number, Seen>, now: Map<number, Seen>): string[] {
	return [...before].flatMap(([pid, was]) => {
		const is = now.get(pid);
		if (!is) return [`[${was.window}] ${was.status} → ended`];
		return was.status === "busy" && is.status !== "busy" ? [`[${is.window}] busy → ${is.status}`] : [];
	});
}

/** The spawned sessions as the registry lists them, by pid: the claude processes spawn's windows were opened running. */
export function watched(live: Pick<Session, "pid" | "status">[], spawned: Spawned[]): Map<number, Seen> {
	return new Map(
		live.flatMap((s) => {
			const window = spawned.find((w) => w.pid === s.pid);
			return window ? [[s.pid, { status: s.status, window: window.window }] as const] : [];
		}),
	);
}
