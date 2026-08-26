import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Me } from "@/api/auth";
import type { Issue } from "@/api/issues";

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
		listTeamStates: vi.fn(),
		listTeamMembers: vi.fn(),
		listTeamLabels: vi.fn(),
	};
});

vi.mock("@/api/issues", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/issues")>();
	return {
		...actual,
		listIssues: vi.fn(),
		searchIssues: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeamLabels, listTeamMembers, listTeamStates, listTeams } =
	await import("@/api/teams");
const { listIssues } = await import("@/api/issues");
const { renderAt } = await import("../test/test-router");
const {
	issueFixture,
	meFixture,
	statesFixture,
	teamFixture,
	testStateId,
	testTeamId,
	testUserId,
} = await import("../test/fixtures");

const dsgnTeamId = "99999999-9999-4999-8999-999999999999";

const meTwoTeams: Me = {
	...meFixture,
	is_admin: false,
	memberships: [
		{
			team_id: testTeamId,
			team_key: "ENG",
			team_name: "Engineering",
			role: "owner",
		},
		{
			team_id: dsgnTeamId,
			team_key: "DSGN",
			team_name: "Design",
			role: "member",
		},
	],
};

const dsgnIssue: Issue = {
	...issueFixture,
	id: "55555555-5555-4555-8555-555555555555",
	team_id: dsgnTeamId,
	number: 3,
	identifier: "DSGN-3",
	title: "Design the onboarding",
	state_id: testStateId,
};

function mockCommon() {
	vi.mocked(getMe).mockResolvedValue(meTwoTeams);
	vi.mocked(listTeams).mockResolvedValue([teamFixture]);
	vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
	vi.mocked(listTeamMembers).mockResolvedValue([]);
	vi.mocked(listTeamLabels).mockResolvedValue([]);
}

describe("MyIssues", () => {
	it("groups the user's assigned Issues by Team", async () => {
		mockCommon();
		vi.mocked(listIssues).mockResolvedValue({
			issues: [issueFixture, dsgnIssue],
			next_cursor: null,
		});
		renderAt("/my-issues");
		expect(await screen.findByText("ENG-1")).toBeTruthy();
		expect(screen.getByText("DSGN-3")).toBeTruthy();
		// Group headers carry the Team name (the sidebar only shows the one
		// Team it knows, so "Engineering" appears in both).
		expect(screen.getAllByText("Engineering")).toHaveLength(2);
		expect(screen.getByText("Design")).toBeTruthy();
		// The page requests the cross-Team list scoped to the current User.
		expect(listIssues).toHaveBeenCalledWith(
			undefined,
			expect.objectContaining({ assignee_ids: [testUserId] }),
		);
	});

	it("shows the empty state when nothing is assigned", async () => {
		mockCommon();
		vi.mocked(listIssues).mockResolvedValue({ issues: [], next_cursor: null });
		renderAt("/my-issues");
		expect(await screen.findByText("No Issues assigned to you")).toBeTruthy();
	});

	it("keeps the My Issues sidebar link for users without Teams", async () => {
		mockCommon();
		vi.mocked(getMe).mockResolvedValue({
			...meFixture,
			is_admin: false,
			memberships: [],
		});
		vi.mocked(listTeams).mockResolvedValue([]);
		vi.mocked(listIssues).mockResolvedValue({ issues: [], next_cursor: null });
		renderAt("/my-issues");
		await screen.findByText("No Issues assigned to you");
		expect(screen.getByRole("link", { name: "My Issues" })).toBeTruthy();
	});
});
