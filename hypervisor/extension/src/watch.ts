import { take } from "./inbox.ts";
import { registry, type Spawned, spawnedWindows } from "./sessions.ts";

/** A watched session's state at one look: its status, and the window it is known by. */
export interface Seen {
	status: string;
	window: string;
}

/** How long before its window was opened a session may have started and still count as the one spawned there. */
const SLACK_MS = 5000;

/**
 * What changed between two looks at the watched sessions, an event each: a session that was busy and is not any more
 * (its turn ended), and a session that is gone.
 */
export function changes(before: Map<number, Seen>, now: Map<number, Seen>): string[] {
	return [...before].flatMap(([pid, was]) => {
		const is = now.get(pid);
		if (!is) return [`${was.window}: ${was.status} → ended`];
		return was.status === "busy" && is.status !== "busy" ? [`${is.window}: busy → ${is.status}`] : [];
	});
}

/**
 * The spawned sessions as the registry lists them, by pid. A session counts as spawned when its pane is one spawn
 * opened, and it started no earlier than that window: tmux reuses a pane's number once its server restarts.
 */
export function watched(live: { pid: number; pane?: string; status: string; startedAt: number }[], spawned: Spawned[]): Map<number, Seen> {
	return new Map(
		live.flatMap((s) => {
			const window = spawned.findLast((w) => w.pane === s.pane && s.startedAt >= Date.parse(w.at) - SLACK_MS);
			return window ? [[s.pid, { status: s.status, window: window.window }] as const] : [];
		}),
	);
}

/**
 * Looks at the spawned sessions and the inbox every `ms`, and hands `deliver` the events since the last look, if any.
 * The first look only learns the sessions' states. Reads files alone: the registry, and the store's own.
 */
export function watch({ claude, store }: { claude: string; store: string }, ms: number, deliver: (events: string[]) => void) {
	let seen: Map<number, Seen> | undefined;
	let looking = false;
	const look = async () => {
		if (looking) return;
		looking = true;
		try {
			const now = watched(await registry(`${claude}/sessions`), await spawnedWindows(store));
			const events = [...(seen ? changes(seen, now) : []), ...(await take(store)).map((t) => `${t.from} (hv tell): ${t.text}`)];
			seen = now;
			if (events.length) deliver(events);
		} finally {
			looking = false;
		}
	};
	const timer = setInterval(() => void look().catch(() => {}), ms);
	timer.unref();
	return { look, stop: () => clearInterval(timer) };
}
