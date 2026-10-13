// The live hypervisor: this extension beside our pi-optchat fork, which holds the memory (`hv` starts pi with both). It
// registers the session tools, the inbox, wait and the explorer's read tools, and makes them, with OptChat's `zoom` and
// `date`, the whole active set: OptChat's own `spawn` and `tell` run pi subagents with pi's coding tools, which
// lifelong-hypervisor#P4 rules out. A message waits in the inbox, listed on OptChat's status line, until the hypervisor
// reads it; a ping reaches OptChat as a report and starts a turn, as does what wait and a background delegate post.
// Either way memory logs it as `work`, not as max's. Each message max types is saved as a numbered file and reaches
// the hypervisor with that file's path under it, so it passes a message on by path. `hv` loads this extension before
// OptChat, whose input handler journals the message as it will arrive, path line included.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { exploreTools } from "./explore.ts";
import { unreadLine, waiting } from "./inbox.ts";
import { fromEnvironment } from "./index.ts";
import { append } from "./journal.ts";
import type { SessionConfig } from "./sessions.ts";
import { background, waitTool } from "./pace.ts";
import { inputsDir, save } from "./inputs.ts";
import { inboxTool, sessionTools } from "./tools.ts";
import { watch } from "./watch.ts";

/** OptChat's memory tools, which stay active. */
export const MEMORY = ["zoom", "date"];
/** Where OptChat takes a report from another extension (pi-optchat's `REPORT_CHANNEL`). */
const REPORT_CHANNEL = "optchat:report";
/** Where OptChat asks other extensions for their status line (pi-optchat's `STATUS_CHANNEL`). */
const STATUS_CHANNEL = "optchat:status";
/** How often the spawned sessions and the inbox are looked at. */
const WATCH_MS = 3000;

/** Under `inputsDir(config.home)`: max's messages. Under `config.store`: `spawned.jsonl`, the windows start_session opened; `inbox/`, the messages that wait, and `inbox/read/` those read or delivered; `watch.jsonl`, a line for each look that failed. */
export function live(config: SessionConfig): (pi: ExtensionAPI) => void {
	return (pi) => {
		const work = background(config.store);
		const tools = [...sessionTools(config, work), inboxTool(config.store), waitTool(work), ...exploreTools(config)];
		for (const tool of tools) pi.registerTool(tool);
		pi.events.on(STATUS_CHANNEL, (data) => {
			const line = unreadLine(
				waiting(config.store).filter((m) => !m.ping),
				Date.now(),
			);
			if (line) (data as { lines: string[] }).lines.push(line);
		});
		pi.on("input", async (event) => {
			// What another extension sends, a ping or a report among them, is not max's.
			if (event.source === "extension" || !event.text.trim()) return { action: "continue" };
			return { action: "transform", text: await save(config.home, inputsDir(config.home), event.text) };
		});
		let watching: ReturnType<typeof watch> | undefined;
		pi.on("session_start", () => {
			pi.setActiveTools([...MEMORY, ...tools.map((tool) => tool.name)]);
			watching ??= watch(
				config,
				WATCH_MS,
				(told) => told.ping === true,
				(pings) => {
					// No profile open yet, or an import running: nothing takes the report, and the inbox keeps the pings for the next look.
					const report: { text: string; taken?: boolean } = { text: pings.join("\n") };
					pi.events.emit(REPORT_CHANNEL, report);
					return report.taken === true;
				},
				(error) => void append(config.store, "watch.jsonl", { at: new Date().toISOString(), error: String(error) }).catch(() => {}),
			);
		});
		pi.on("session_shutdown", async () => {
			watching?.stop();
			watching = undefined;
			// What still runs posts that it stopped, which the next session's watch delivers.
			await work.stop();
		});
	};
}

/** The extension as pi loads it (`pi -e`), configured as `hv` sets the environment. */
export default live(fromEnvironment());
