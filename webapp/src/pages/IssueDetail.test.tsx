import { fireEvent, screen, waitFor, within } from "@testing-library/react";
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
		listTeamMembers: vi.fn(),
		listTeamStates: vi.fn(),
	};
});

vi.mock("@/api/issues", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/issues")>();
	return {
		...actual,
		listIssues: vi.fn(),
		createIssue: vi.fn(),
		getIssue: vi.fn(),
		updateIssue: vi.fn(),
		transitionIssue: vi.fn(),
		listIssueActivity: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeamMembers, listTeamStates, listTeams } = await import(
	"@/api/teams"
);
const {
	getIssue,
	listIssueActivity,
	listIssues,
	transitionIssue,
	updateIssue,
} = await import("@/api/issues");
const { renderAt } = await import("../test/test-router");
const {
	activityFixture,
	doneStateId,
	issueDetailFixture,
	issueFixture,
	memberFixture,
	meFixture,
	statesFixture,
	teamFixture,
} = await import("../test/fixtures");

function mockCommon() {
	vi.mocked(getMe).mockResolvedValue(meFixture);
	vi.mocked(listTeams).mockResolvedValue([teamFixture]);
	vi.mocked(listIssues).mockResolvedValue([issueFixture]);
	vi.mocked(listTeamMembers).mockResolvedValue([memberFixture]);
	vi.mocked(getIssue).mockResolvedValue(issueDetailFixture);
	vi.mocked(listIssueActivity).mockResolvedValue(activityFixture);
	vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
}

describe("IssueDetail", () => {
	it("shows the identifier, title, sanitized Markdown and properties", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		expect(await screen.findByText("ENG-1")).toBeTruthy();
		expect(screen.getByText("Set up the core loop")).toBeTruthy();
		// Markdown rendered (not raw): the heading and the bold span.
		expect(screen.getByRole("heading", { name: "Plan" })).toBeTruthy();
		expect(screen.getByText("bold")).toBeTruthy();
		// Properties.
		expect(
			await within(screen.getByLabelText("Properties")).findByText("Backlog"),
		).toBeTruthy();
		expect(screen.getByText("No priority")).toBeTruthy();
		expect(screen.getByText("Unassigned")).toBeTruthy();
		expect(screen.getByText("No labels yet")).toBeTruthy();
	});

	it("shows the Activity feed chronologically", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		await screen.findByText("ENG-1");
		expect(await screen.findByText("created this Issue")).toBeTruthy();
		expect(
			await screen.findByText(
				"changed Title from Old title to Set up the core loop",
			),
		).toBeTruthy();
	});

	it("saves an inline title edit with the last-seen updated_at", async () => {
		mockCommon();
		vi.mocked(updateIssue).mockResolvedValue({
			...issueFixture,
			title: "New title",
		});
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		const titleButton = await screen.findByRole("button", {
			name: "Edit title: Set up the core loop",
		});
		fireEvent.click(titleButton);
		const input = screen.getByLabelText("Edit title");
		fireEvent.change(input, { target: { value: "New title" } });
		fireEvent.keyDown(input, { key: "Enter" });
		await waitFor(() =>
			expect(updateIssue).toHaveBeenCalledWith(issueFixture.id, {
				updated_at: issueDetailFixture.updated_at,
				title: "New title",
			}),
		);
	});

	it("transitions the State through the same path with the last-seen updated_at", async () => {
		mockCommon();
		vi.mocked(transitionIssue).mockResolvedValue({
			...issueFixture,
			state_name: "Done",
			state_category: "completed",
			state_color: "#4cb371",
		});
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		const stateSelect = await screen.findByLabelText("State");
		await waitFor(() =>
			expect(stateSelect.querySelectorAll("option")).toHaveLength(6),
		);
		fireEvent.change(stateSelect, {
			target: { value: doneStateId },
		});
		await waitFor(() =>
			expect(transitionIssue).toHaveBeenCalledWith(issueFixture.id, {
				state_id: doneStateId,
				updated_at: issueDetailFixture.updated_at,
			}),
		);
	});

	it("rolls back and toasts on a stale (409) update", async () => {
		mockCommon();
		vi.mocked(updateIssue).mockRejectedValue(
			new (await import("@/api/client")).ApiError(409, {
				code: "conflict",
				message: "The Issue was updated by someone else. Reload and try again.",
			}),
		);
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		const titleButton = await screen.findByRole("button", {
			name: "Edit title: Set up the core loop",
		});
		fireEvent.click(titleButton);
		const input = screen.getByLabelText("Edit title");
		fireEvent.change(input, { target: { value: "Clobbered" } });
		fireEvent.keyDown(input, { key: "Enter" });
		expect(await screen.findByText(/changed by someone else/)).toBeTruthy();
		// The optimistic title is rolled back.
		expect(
			await screen.findByRole("button", {
				name: "Edit title: Set up the core loop",
			}),
		).toBeTruthy();
	});
});
