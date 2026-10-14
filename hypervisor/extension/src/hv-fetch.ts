// `hv fetch`: brings the messages Jarvis left the hypervisor into its inbox, where they wait like an orchestrator's
// reports. A systemd user timer runs it, since the VPS cannot reach the laptop.

import { inbox } from "./inbox.ts";
import { fetchFromJarvis, jarvisFromEnvironment } from "./jarvis.ts";

export const USAGE = `usage: hv fetch

Moves the messages Jarvis left the hypervisor in its outbox on the VPS into the hypervisor's inbox, from jarvis, and
deletes them there. It reaches the VPS as $HV_JARVIS_HOST (default jarvis) with the key $HV_JARVIS_KEY (default
~/.ssh/hypervisor-jarvis), and writes to the inbox of the store $HV_STORE, which hv sets.`;

if (import.meta.main) {
	const args = process.argv.slice(2);
	if (args.length) {
		console.log(USAGE);
		process.exit(args[0] === "--help" || args[0] === "-h" ? 0 : 2);
	}
	const store = process.env.HV_STORE;
	if (!store) {
		console.error(`hv fetch: HV_STORE is not set; run it as hv fetch\n\n${USAGE}`);
		process.exit(2);
	}
	try {
		const count = await fetchFromJarvis(jarvisFromEnvironment(), inbox(store));
		console.log(count ? `${count} from Jarvis left in the hypervisor's inbox.` : "Nothing from Jarvis.");
	} catch (error) {
		console.error(`hv fetch: ${(error as Error).message}`);
		process.exit(1);
	}
}
