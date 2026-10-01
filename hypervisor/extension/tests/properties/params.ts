import fc from "fast-check";

type Schema = {
	type?: string;
	const?: unknown;
	enum?: unknown[];
	anyOf?: Schema[];
	oneOf?: Schema[];
	items?: Schema;
	properties?: Record<string, Schema>;
	required?: string[];
};

/**
 * Arguments a model could send to a tool, drawn from its parameter schema: every string from `strings`, and a
 * parameter the schema has and `fixed` names from the arbitrary given there, always present.
 */
export function paramsFor(
	schema: Schema,
	strings: fc.Arbitrary<string>,
	fixed: Record<string, fc.Arbitrary<unknown>> = {},
): fc.Arbitrary<Record<string, unknown>> {
	const properties = Object.entries(schema.properties ?? {}).map(([name, s]) => [name, fixed[name] ?? valueFor(s, strings)]);
	const always = Object.keys(fixed).filter((name) => schema.properties?.[name]);
	return fc.record(Object.fromEntries(properties), { requiredKeys: [...new Set([...(schema.required ?? []), ...always])] });
}

function valueFor(schema: Schema, strings: fc.Arbitrary<string>): fc.Arbitrary<unknown> {
	if (schema.const !== undefined) return fc.constant(schema.const);
	if (schema.enum) return fc.constantFrom(...schema.enum);
	const union = schema.anyOf ?? schema.oneOf;
	if (union) return fc.oneof(...union.map((s) => valueFor(s, strings)));
	switch (schema.type) {
		case "string":
			return strings;
		case "number":
		case "integer":
			return fc.integer({ min: -1, max: 2000 });
		case "boolean":
			return fc.boolean();
		case "array":
			return fc.array(valueFor(schema.items ?? {}, strings), { maxLength: 3 });
		case "object":
			return paramsFor(schema, strings);
		default:
			return fc.oneof(strings, fc.integer(), fc.boolean());
	}
}
