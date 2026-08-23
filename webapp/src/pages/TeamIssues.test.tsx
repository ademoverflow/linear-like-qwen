import { screen } from "@testing-library/react";
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

vi.mock("@/api/issues", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/issues")>();
	return {
		...actual,
		listIssues: vi.fn(),
		createIssue: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeams } = await import("@/api/teams");
const { listIssues } = await import("@/api/issues");
const { renderAt } = await import("../test/test-router");
const { issueFixture, meFixture, teamFixture } = await import(
	"../test/fixtures"
);

describe("TeamIssues", () => {
	it("renders the Team's Issues as a card stack", async () => {
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		vi.mocked(listIssues).mockResolvedValue([issueFixture]);
		renderAt("/teams/ENG/issues");
		expect(await screen.findByText("ENG-1")).toBeTruthy();
		expect(screen.getByText("Set up the core loop")).toBeTruthy();
		expect(screen.getByText("Backlog")).toBeTruthy();
	});

	it("shows the sidebar New Team entry to Admins and hides it from members", async () => {
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		vi.mocked(listIssues).mockResolvedValue([issueFixture]);
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		expect(screen.getByRole("button", { name: "New Team" })).toBeTruthy();
	});

	it("hides the sidebar New Team entry from non-Admins", async () => {
		vi.mocked(getMe).mockResolvedValue({
			...meFixture,
			is_admin: false,
		});
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		vi.mocked(listIssues).mockResolvedValue([issueFixture]);
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		expect(screen.queryByRole("button", { name: "New Team" })).toBeNull();
	});

	it("shows the empty state when the Team has no Issues", async () => {
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		vi.mocked(listIssues).mockResolvedValue([]);
		renderAt("/teams/ENG/issues");
		expect(await screen.findByText("No Issues yet")).toBeTruthy();
	});
});
