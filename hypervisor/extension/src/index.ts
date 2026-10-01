import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { NotImplemented } from "./not-implemented.ts";

export interface Config {
	/** The store's directory, the one place the hypervisor's own tools write. */
	store: string;
	home: string;
}

/**
 * The hypervisor as a pi extension. It registers the hypervisor's tools and makes them the whole active set, so none
 * of pi's own tools (`bash`, `edit`, `write`, an unguarded `read`) stays active.
 */
export function hypervisor(_config: Config): (pi: ExtensionAPI) => void {
	return () => {
		throw new NotImplemented("hypervisor-view-swap");
	};
}
