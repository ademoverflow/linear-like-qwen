import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "./markdown";

describe("Markdown", () => {
	it("renders GFM tables", () => {
		render(<Markdown content={"| a | b |\n| --- | --- |\n| 1 | 2 |"} />);
		expect(screen.getByRole("table")).toBeTruthy();
		expect(screen.getByRole("cell", { name: "2" })).toBeTruthy();
	});

	it("renders task lists with checkboxes", () => {
		render(<Markdown content={"- [ ] open item\n- [x] done item"} />);
		expect(screen.getByRole("checkbox", { checked: true })).toBeTruthy();
		expect(screen.getByRole("checkbox", { checked: false })).toBeTruthy();
	});

	it("renders strikethrough and code", () => {
		render(<Markdown content={"~~old~~ and `code`"} />);
		expect(screen.getByText("old").tagName).toBe("DEL");
		expect(screen.getByText("code").tagName).toBe("CODE");
	});

	it("strips raw HTML and script tags", () => {
		render(<Markdown content={"hello <script>alert(1)</script> world"} />);
		expect(document.querySelector("script")).toBeNull();
		expect(screen.getByText(/hello/)).toBeTruthy();
	});

	it("removes javascript: URLs from links", () => {
		render(<Markdown content={"[click](javascript:alert(1))"} />);
		const link = document.querySelector("a");
		expect(link?.getAttribute("href") ?? "").not.toContain("javascript:");
	});

	it("keeps http links", () => {
		render(<Markdown content={"[site](https://example.com)"} />);
		expect(
			screen.getByRole("link", { name: "site" }).getAttribute("href"),
		).toBe("https://example.com");
	});
});
