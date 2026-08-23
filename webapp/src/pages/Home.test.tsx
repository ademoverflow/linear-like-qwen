import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.stubEnv("VITE_API_URL", "http://api.test");

vi.mock("@/api/auth", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/auth")>();
	return {
		...actual,
		getMe: vi.fn(),
		getAuthStatus: vi.fn(),
		register: vi.fn(),
		login: vi.fn(),
		logout: vi.fn(),
	};
});

vi.mock("@/api/teams", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/teams")>();
	return {
		...actual,
		listTeams: vi.fn(),
		createTeam: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeams } = await import("@/api/teams");
const { renderAt } = await import("../test/test-router");
const { meFixture } = await import("../test/fixtures");

describe("Home", () => {
	it("offers to create the first Team to an Admin with no Teams", async () => {
		vi.mocked(getMe).mockResolvedValue({ ...meFixture, memberships: [] });
		vi.mocked(listTeams).mockResolvedValue([]);
		renderAt("/");
		expect(
			await screen.findByRole("heading", { name: "No Teams yet" }),
		).toBeTruthy();
		const main = document.querySelector("main");
		expect(main).toBeTruthy();
		expect(
			within(main as HTMLElement).getByRole("button", {
				name: "New Team",
			}),
		).toBeTruthy();
	});

	it("tells non-Admins to ask a workspace Admin when they have no Teams", async () => {
		vi.mocked(getMe).mockResolvedValue({
			...meFixture,
			is_admin: false,
			memberships: [],
		});
		vi.mocked(listTeams).mockResolvedValue([]);
		renderAt("/");
		expect(
			await screen.findByRole("heading", { name: "No Teams yet" }),
		).toBeTruthy();
		expect(screen.getByText(/ask a workspace admin/i)).toBeTruthy();
	});
});
