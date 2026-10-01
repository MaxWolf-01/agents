import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { NotImplemented } from "./not-implemented.ts";

/**
 * The messages one model request carries: a message holding the rendered view, then the current turn as it stands.
 * The current turn starts at the last user message; everything before it is in the view, as entries.
 */
export function swapContext(_messages: AgentMessage[], _view: string): AgentMessage[] {
	throw new NotImplemented("hypervisor-view-swap");
}
