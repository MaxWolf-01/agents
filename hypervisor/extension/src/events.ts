const OPEN = "<event>\n";
const CLOSE = "\n</event>";

/**
 * The message that hands the hypervisor what happened while nobody asked: one `<event>` block per event. An event's
 * own `</event>` is broken up, so it cannot end its block early.
 */
export function eventMessage(events: string[]): string {
	return events.map((event) => `${OPEN}${event.replaceAll("</event>", "</ event>")}${CLOSE}`).join("\n");
}

/** The events a message holds, when it is nothing but `<event>` blocks; otherwise `undefined`. */
export function eventsIn(text: string): string[] | undefined {
	if (!text.startsWith(OPEN) || !text.endsWith(CLOSE) || text.length < OPEN.length + CLOSE.length) return undefined;
	return text.slice(OPEN.length, -CLOSE.length).split(`${CLOSE}\n${OPEN}`);
}
