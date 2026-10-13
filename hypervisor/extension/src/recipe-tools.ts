// The explorer's read tools as a pi extension of their own, loaded beside pi-optchat in `recipe-run.ts`. max's home is read
// from the environment, and the hypervisor's store, which holds pi's credentials and the explorer's own memory, is denied.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { exploreTools } from "./explore.ts";
import { fromEnvironment } from "./sessions.ts";

export default function recipeTools(pi: ExtensionAPI) {
	for (const tool of exploreTools(fromEnvironment())) pi.registerTool(tool);
}
