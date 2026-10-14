// The seam to Jarvis, max's life assistant on his VPS: the hypervisor leaves a message in Jarvis's inbox, and `hv fetch`
// brings Jarvis's messages to the hypervisor into its inbox. Both go over ssh with a key of the hypervisor's own, whose
// forced command on the VPS is `hypervisor/jarvis-mailbox`: the key can do what that script does and nothing else. The
// VPS cannot open a connection to the laptop, so the laptop pulls.

import { existsSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import type { Inbox } from "./inbox.ts";
import { run } from "./run.ts";

/** How the laptop reaches the mailbox: the ssh host and the key whose forced command it is. */
export interface JarvisConfig {
	host: string;
	key: string;
}

/** The sender `hv fetch` names Jarvis's messages by. */
export const JARVIS = "jarvis";
const SSH_TIMEOUT_MS = 30_000;

/** The configuration from the environment. */
export function jarvisFromEnvironment(): JarvisConfig {
	return { host: process.env.HV_JARVIS_HOST ?? "jarvis", key: process.env.HV_JARVIS_KEY ?? path.join(homedir(), ".ssh/hypervisor-jarvis") };
}

/** Leaves `message` in Jarvis's inbox, where it waits for Jarvis's next wake, and says under what name. */
export async function tellJarvis(config: JarvisConfig, message: string): Promise<string> {
	if (!message.trim()) throw new Error("the message is empty");
	const name = (await mailbox(config, ["tell"], `${message.trim()}\n`)).trim();
	return `Left in Jarvis's inbox as ${name}; Jarvis reads it at its next wake.`;
}

/**
 * Moves every message Jarvis left the hypervisor from its outbox into `inbox`, oldest first, each from `jarvis` and
 * sent when Jarvis wrote it, and only then deletes them on the VPS: a run that stops in between leaves them to arrive
 * again, never lost. Returns how many arrived.
 */
export async function fetchFromJarvis(config: JarvisConfig, inbox: Inbox): Promise<number> {
	const messages = (await mailbox(config, ["fetch"]))
		.split("\n")
		.filter(Boolean)
		.map((line) => {
			const [name, mtime, text] = line.split(" ");
			return { name, at: new Date(Number(mtime) * 1000).toISOString(), text: Buffer.from(text ?? "", "base64").toString("utf8").trim() };
		});
	for (const { at, text } of messages) if (text) await inbox.post({ at, from: JARVIS, text });
	if (messages.length) await mailbox(config, ["delete", ...messages.map((m) => m.name)]);
	return messages.length;
}

/** Runs one request of the mailbox's on the VPS, with only the mailbox key offered and no prompt to answer. */
async function mailbox({ host, key }: JarvisConfig, request: string[], input?: string): Promise<string> {
	if (!existsSync(key)) throw new Error(`no mailbox key at ${key}; hypervisor/jarvis-mailbox says how it is set up`);
	const ssh = ["-i", key, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, ...request];
	try {
		return await run("ssh", ssh, { input, timeout: SSH_TIMEOUT_MS });
	} catch (error) {
		throw new Error(`Jarvis's mailbox on ${host}, ${request[0]}: ${(error as Error).message.replace(/^ssh -i: /, "")}`);
	}
}
