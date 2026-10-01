import { NotImplemented } from "../../src/not-implemented.ts";

/** Whether an error is a stub's, thrown directly or reported by fast-check as the cause of a failed run. */
export function isStub(error: unknown): boolean {
	return error instanceof NotImplemented || (error instanceof Error && error.cause instanceof NotImplemented);
}

/**
 * The options that make a check an expected failure until `slice` lands. Strict: node's runner fails a check that
 * passes while marked. It tolerates only the stub's error, so a wrong implementation, or a bug in the check, fails.
 */
export function liftedBy(slice: string) {
	return { expectFailure: { label: `lifted by ${slice}`, match: isStub } };
}
