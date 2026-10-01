/** What a seam throws until the slice that builds it lands; the expected failures wait for exactly this. */
export class NotImplemented extends Error {
	constructor(slice: string) {
		super(`${slice} builds this`);
		this.name = "NotImplemented";
	}
}
