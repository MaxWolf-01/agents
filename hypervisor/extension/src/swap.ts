import type { AgentMessage } from "@earendil-works/pi-agent-core";

/** The tag the view's message opens with; the provider hook finds the view by it. */
export const VIEW_OPEN = "<view>\n";
const VIEW_CLOSE = "\n</view>";

/**
 * The messages one model request carries: a message holding the rendered view, then the current turn as it stands.
 * The current turn starts at `start`, or else at the last user message; everything before it is in the view, as
 * entries. A run passes its first message as `start`, so a message max sends while it runs stays in the same turn.
 */
export function swapContext(messages: AgentMessage[], view: string, start = messages.findLastIndex((m) => m.role === "user")): AgentMessage[] {
	const turn = messages.slice(Math.max(0, start));
	return [viewMessage(view, turn[0]?.timestamp ?? 0), ...turn];
}

function viewMessage(view: string, timestamp: number): AgentMessage {
	return { role: "user", content: [{ type: "text", text: `${VIEW_OPEN}${view}${VIEW_CLOSE}` }], timestamp };
}
