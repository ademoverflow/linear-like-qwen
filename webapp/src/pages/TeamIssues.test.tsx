import { fireEvent, screen } from "@testing-library/react";
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
		listAllIssues: vi.fn(),
		createIssue: vi.fn(),
		bulkUpdateIssues: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeamLabels, listTeamMembers, listTeamStates, listTeams } =
	await import("@/api/teams");
const { bulkUpdateIssues, listIssues } = await import("@/api/issues");
const { renderAt } = await import("../test/test-router");
const {
	issueFixture,
	labelsFixture,
	memberFixture,
	meFixture,
	statesFixture,
	teamFixture,
	testIssueId,
	testStateId,
} = await import("../test/fixtures");

function mockCommon() {
	vi.mocked(getMe).mockResolvedValue(meFixture);
	vi.mocked(listTeams).mockResolvedValue([teamFixture]);
	vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
	vi.mocked(listTeamMembers).mockResolvedValue([memberFixture]);
	vi.mocked(listTeamLabels).mockResolvedValue(labelsFixture);
	vi.mocked(listIssues).mockResolvedValue({
		issues: [issueFixture],
		next_cursor: null,
	});
}

describe("TeamIssues", () => {
	it("renders the Team's Issues grouped by State", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		expect(await screen.findByText("ENG-1")).toBeTruthy();
		expect(screen.getByText("Set up the core loop")).toBeTruthy();
		// "Backlog" appears as the group header and on the card's State.
		expect(screen.getAllByText("Backlog")).toHaveLength(2);
	});

	it("shows the sidebar New Team entry to Admins and hides it from members", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		expect(screen.getByRole("button", { name: "New Team" })).toBeTruthy();
	});

	it("hides the sidebar New Team entry from non-Admins", async () => {
		mockCommon();
		vi.mocked(getMe).mockResolvedValue({ ...meFixture, is_admin: false });
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		expect(screen.queryByRole("button", { name: "New Team" })).toBeNull();
	});

	it("shows the empty state when the Team has no Issues", async () => {
		mockCommon();
		vi.mocked(listIssues).mockResolvedValue({ issues: [], next_cursor: null });
		renderAt("/teams/ENG/issues");
		expect(await screen.findByText("No Issues yet")).toBeTruthy();
	});

	it("offers the Labels manager only to the Team owner", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		expect(screen.getByRole("button", { name: "Labels" })).toBeTruthy();
	});

	it("hides the Labels manager from members", async () => {
		mockCommon();
		vi.mocked(getMe).mockResolvedValue({
			...meFixture,
			is_admin: false,
			memberships: [
				{
					team_id: teamFixture.id,
					team_key: "ENG",
					team_name: "Engineering",
					role: "member",
				},
			],
		});
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		expect(screen.queryByRole("button", { name: "Labels" })).toBeNull();
	});

	it("applies a State filter live from the filter dialog", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.click(screen.getByRole("button", { name: /Filter/ }));
		await screen.findByRole("dialog", { name: "Filter Issues" });
		fireEvent.click(screen.getByRole("checkbox", { name: "Backlog" }));
		await vi.waitFor(() =>
			expect(listIssues).toHaveBeenCalledWith(
				teamFixture.id,
				expect.objectContaining({ state_ids: [testStateId] }),
			),
		);
	});

	it("selects Issues and bulk-changes their State", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.click(screen.getByRole("button", { name: "Select" }));
		fireEvent.click(screen.getByRole("checkbox", { name: "Select ENG-1" }));
		expect(await screen.findByText("1 selected")).toBeTruthy();
		const todoState = statesFixture.find((state) => state.name === "Todo");
		fireEvent.change(screen.getByLabelText("Set state"), {
			target: { value: todoState?.id ?? "" },
		});
		await vi.waitFor(() =>
			expect(bulkUpdateIssues).toHaveBeenCalledWith({
				issue_ids: [testIssueId],
				state_id: todoState?.id,
			}),
		);
	});

	it("shows the filter count and an empty-match state", async () => {
		mockCommon();
		vi.mocked(listIssues).mockResolvedValue({ issues: [], next_cursor: null });
		renderAt("/teams/ENG/issues");
		await screen.findByRole("button", { name: /Filter/ });
		fireEvent.click(screen.getByRole("button", { name: /Filter/ }));
		await screen.findByRole("dialog", { name: "Filter Issues" });
		fireEvent.click(screen.getByRole("checkbox", { name: "Backlog" }));
		await vi.waitFor(() =>
			expect(screen.getByRole("button", { name: "Filter (1)" })).toBeTruthy(),
		);
		expect(await screen.findByText("No Issues match the filters")).toBeTruthy();
	});
});
