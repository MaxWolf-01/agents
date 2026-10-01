import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ToolDefinition } from "@earendil-works/pi-coding-agent";
import type { Store } from "./store.ts";

/** A tool's answer: the text it printed, or `(nothing)`. */
export const answer = (text: string) => ({ content: [{ type: "text" as const, text: text.trimEnd() || "(nothing)" }], details: undefined });

/** The memory tools: each runs one store command and answers with what it printed. */
export function memoryTools(store: Store): ToolDefinition[] {
	return [
		defineTool({
			name: "zoom",
			label: "Zoom",
			description: "Show a block of your view one level finer: its two halves as view lines. Zoom again into a half to go deeper; a half of one entry is that entry.",
			parameters: Type.Object({ block: Type.String({ description: "The block as LO-HI, the numbers after # on its view line, e.g. 64-127." }) }),
			execute: async (_id, { block }) => answer(await store.zoom(block)),
		}),
		defineTool({
			name: "recall",
			label: "Recall",
			description: "Search your whole log, every entry ever logged, for a Python regex, ignoring case. Prints the matching entries, newest last.",
			parameters: Type.Object({ regex: Type.String({ description: "A Python regular expression." }) }),
			execute: async (_id, { regex }) => answer(await store.recall(regex)),
		}),
		defineTool({
			name: "raw",
			label: "Raw",
			description: "Print the whole text of one entry, for an entry whose line ends in [raw: N bytes].",
			parameters: Type.Object({ id: Type.Integer({ description: "The entry's number, after # on its line." }) }),
			execute: async (_id, { id }) => answer(await store.raw(id)),
		}),
	] as ToolDefinition[];
}
