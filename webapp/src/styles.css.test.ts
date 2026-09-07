import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// CSS contract for the focus ring (ADR 0015): jsdom does not resolve
// :focus-visible from imported stylesheets, so the rule is asserted on
// the stylesheet text itself. Vitest runs from the webapp root
// (make test-webapp / pnpm --filter webapp run test).
const css = readFileSync(join(process.cwd(), "src", "styles.css"), "utf8")
	.replace(/\s+/g, " ")
	.trim();

describe("styles.css focus-ring contract (ADR 0015)", () => {
	it("keeps the global :focus-visible ring on the focus-ring token", () => {
		expect(css).toMatch(
			/:focus-visible { outline: 2px solid var\(--color-focus-ring\); /,
		);
	});

	it("exempts the text-entry family from the outline", () => {
		const match = css.match(/([^{}]+) { outline: none; }/);
		expect(match, "exemption block (outline: none) must exist").not.toBeNull();
		const selectors = match?.[1] ?? "";
		for (const selector of [
			"input:not([type]):focus-visible",
			'input[type="text"]:focus-visible',
			'input[type="password"]:focus-visible',
			"textarea:focus-visible",
		]) {
			expect(selectors, `${selector} must be exempted`).toContain(selector);
		}
	});

	it("keeps the ring on checkbox and radio", () => {
		const match = css.match(/([^{}]+) { outline: none; }/);
		expect(match?.[1]).not.toContain("checkbox");
		expect(match?.[1]).not.toContain("radio");
	});
});
