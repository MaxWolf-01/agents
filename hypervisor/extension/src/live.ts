// The live hypervisor: this extension beside our pi-optchat fork, which holds the memory (`hv` starts pi with both). It
// registers the session tools and the explorer's read tools, and makes them, with OptChat's `zoom` and `date`, the whole
// active set: OptChat's own `spawn` and `tell` run pi subagents with pi's coding tools, which lifelong-hypervisor#P4
// rules out. What the spawned orchestrators do reaches OptChat as reports, so memory logs it as `work`, not as max's.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { exploreTools } from "./explore.ts";
import { fromEnvironment } from "./index.ts";
import { append } from "./journal.ts";
import type { SessionConfig } from "./sessions.ts";
import { sessionTools } from "./tools.ts";
import { watch } from "./watch.ts";

/** OptChat's memory tools, which stay active. */
export const MEMORY = ["zoom", "date"];
/** Where OptChat takes a report from another extension (pi-optchat's `REPORT_CHANNEL`). */
const REPORT_CHANNEL = "optchat:report";
/** How often the spawned sessions and the inbox are looked at. */
const WATCH_MS = 3000;

/** Under `config.store`: `spawned.jsonl`, the windows start_session opened; `inbox/`, what `hv tell` left and the watch has not handed over; `watch.jsonl`, a line for each look that failed. */
export function live(config: SessionConfig): (pi: ExtensionAPI) => void {
	return (pi) => {
		const tools = [...sessionTools(config), ...exploreTools(config)];
		for (const tool of tools) pi.registerTool(tool);
		let watching: ReturnType<typeof watch> | undefined;
		pi.on("session_start", () => {
			pi.setActiveTools([...MEMORY, ...tools.map((tool) => tool.name)]);
			watching ??= watch(
				config,
				WATCH_MS,
				(events) => {
					// No profile open yet, or an import running: nothing takes the report, and the inbox keeps it for the next look.
					const report: { text: string; taken?: boolean } = { text: events.join("\n") };
					pi.events.emit(REPORT_CHANNEL, report);
					return report.taken === true;
				},
				(error) => void append(config.store, "watch.jsonl", { at: new Date().toISOString(), error: String(error) }).catch(() => {}),
			);
		});
		pi.on("session_shutdown", () => {
			watching?.stop();
			watching = undefined;
		});
	};
}

/** The extension as pi loads it (`pi -e`), configured as `hv` sets the environment. */
export default live(fromEnvironment());
