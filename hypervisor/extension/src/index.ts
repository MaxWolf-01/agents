import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { NotImplemented } from "./not-implemented.ts";

export interface Config {
	/** The store's directory, the one place the extension and its tools write. */
	store: string;
	/** The home directory of the machine the explorer reads; a relative path the model sends starts here. */
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
