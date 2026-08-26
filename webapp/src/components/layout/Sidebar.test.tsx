import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "@/api/auth";

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
	};
});

const { getMe } = await import("@/api/auth");
const { listTeams } = await import("@/api/teams");
const { renderAt } = await import("../../test/test-router");
const { meFixture, teamFixture, testTeamId } = await import(
	"../../test/fixtures"
);

const memberMe: Me = {
	...meFixture,
	is_admin: false,
	memberships: [
		{
			team_id: testTeamId,
			team_key: "ENG",
			team_name: "Engineering",
			role: "member",
		},
	],
};

describe("Sidebar", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("shows the Settings link to owners and Admins only", async () => {
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		renderAt("/teams/ENG/issues");
		await screen.findByText("Engineering");
		expect(screen.getByRole("link", { name: "Settings" })).toBeTruthy();
	});

	it("hides the Settings link from plain members", async () => {
		vi.mocked(getMe).mockResolvedValue(memberMe);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		renderAt("/teams/ENG/issues");
		await screen.findByText("Engineering");
		expect(screen.queryByRole("link", { name: "Settings" })).toBeNull();
	});

	it("badges archived Teams (visible to Admins)", async () => {
		const archived = {
			...teamFixture,
			archived_at: new Date("2026-08-25T00:00:00Z"),
		};
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([archived]);
		renderAt("/teams/ENG/issues");
		await screen.findByText("Engineering");
		expect(screen.getByText("Archived")).toBeTruthy();
	});
});
