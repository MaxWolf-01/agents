// The live hypervisor: this extension beside our pi-optchat fork, which holds the memory (`hv` starts pi with both). It
// registers the session tools, the inbox, tell_jarvis, wait and the explorer's read tools, and makes them, with
// OptChat's `zoom` and `date`, the whole active set: OptChat's own `spawn` and `tell` run pi subagents with pi's coding tools, which
// lifelong-hypervisor#P4 rules out. A message waits in the inbox, listed on OptChat's status line, until the hypervisor
// reads it; a ping reaches OptChat as a report and starts a turn, as does what wait and a background delegate post.
// Either way memory logs it as `work`, not as max's. Each message max types is saved as a numbered file and reaches
// the hypervisor with that file's path under it, so it passes a message on by path. `hv` loads this extension before
// OptChat, whose input handler journals the message as it will arrive, path line included. `/explore` runs explore steps
// on the same profile (`exploring.ts`).

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { exploreTools } from "./explore.ts";
import { exploring, usageLog } from "./exploring.ts";
import { inbox } from "./inbox.ts";
import { type JarvisConfig, jarvisFromEnvironment } from "./jarvis.ts";
import { append } from "./journal.ts";
import { fromEnvironment, type SessionConfig } from "./sessions.ts";
import { background, waitTool } from "./pace.ts";
import { save } from "./inputs.ts";
import { inboxTool, jarvisTool, sessionTools } from "./tools.ts";
import { watch } from "./watch.ts";

/** OptChat's memory tools, which stay active. */
export const MEMORY = ["zoom", "date"];
/** Where OptChat takes a report from another extension (pi-optchat's `REPORT_CHANNEL`). */
const REPORT_CHANNEL = "optchat:report";
/** Where OptChat asks other extensions for their status line (pi-optchat's `STATUS_CHANNEL`). */
const STATUS_CHANNEL = "optchat:status";
/** How often the watch takes the inbox's pings. */
const WATCH_MS = 3000;

/** Under `config.home`'s `.local/share/hypervisor-inputs/`: max's messages. Under `config.store`: `spawned.jsonl`, the windows start_session opened; `inbox/`, the messages that wait, and `inbox/read/` those read or delivered; `watch.jsonl`, a line for each take of the pings that failed; `explore.jsonl`, what explore runs found. `config.usage` is OptChat's usage log for the profile, which an explore run's token cap reads. `config.jarvis` is where tell_jarvis reaches Jarvis's mailbox, by default where the environment says. */
export function live(config: SessionConfig & { usage?: string; jarvis?: JarvisConfig }): (pi: ExtensionAPI) => void {
	return (pi) => {
		const messages = inbox(config.store);
		const work = background(messages);
		const tools = [...sessionTools(config, work), inboxTool(messages), jarvisTool(config.jarvis ?? jarvisFromEnvironment()), waitTool(work), ...exploreTools(config)];
		for (const tool of tools) pi.registerTool(tool);
		pi.events.on(STATUS_CHANNEL, (data) => {
			const line = messages.statusLine();
			if (line) (data as { lines: string[] }).lines.push(line);
		});
		pi.on("input", async (event) => {
			// What another extension sends, a ping or a report among them, is not max's.
			if (event.source === "extension" || !event.text.trim()) return { action: "continue" };
			return { action: "transform", text: await save(config.home, event.text) };
		});
		let watching: ReturnType<typeof watch> | undefined;
		pi.on("session_start", () => {
			pi.setActiveTools([...MEMORY, ...tools.map((tool) => tool.name)]);
			watching ??= watch(
				messages,
				WATCH_MS,
				(pings) => {
					// No profile open yet, or an import running: nothing takes the report, and the inbox keeps the pings for the next take.
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
		exploring(pi, { store: config.store, usage: config.usage });
	};
}

/** The extension as pi loads it (`pi -e`), configured as `hv` sets the environment. */
export default live({ ...fromEnvironment(), usage: usageLog() });
