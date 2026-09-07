import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SearchIssue } from "@/api/issues";

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
		listAllIssues: vi.fn(),
		getIssue: vi.fn(),
		searchIssues: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeamLabels, listTeamMembers, listTeamStates, listTeams } =
	await import("@/api/teams");
const { getIssue, listAllIssues, listIssues, searchIssues } = await import(
	"@/api/issues"
);
const { renderAt } = await import("../../test/test-router");
const {
	issueDetailFixture,
	issueFixture,
	meFixture,
	statesFixture,
	teamFixture,
} = await import("../../test/fixtures");

const dsgnTeamId = "99999999-9999-4999-8999-999999999999";

const engIssue: SearchIssue = {
	...issueFixture,
	team_key: "ENG",
	team_name: "Engineering",
};

const dsgnIssue: SearchIssue = {
	...issueFixture,
	id: "55555555-5555-4555-8555-555555555555",
	team_id: dsgnTeamId,
	number: 3,
	identifier: "DSGN-3",
	title: "Design the onboarding",
	team_key: "DSGN",
	team_name: "Design",
};

function mockCommon() {
	vi.mocked(getMe).mockResolvedValue(meFixture);
	vi.mocked(listTeams).mockResolvedValue([teamFixture]);
	vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
	vi.mocked(listTeamMembers).mockResolvedValue([]);
	vi.mocked(listTeamLabels).mockResolvedValue([]);
	vi.mocked(listIssues).mockResolvedValue({ issues: [], next_cursor: null });
	vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
	vi.mocked(getIssue).mockResolvedValue(issueDetailFixture);
}

describe("SearchOverlay", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("opens on / and focuses the input", async () => {
		mockCommon();
		renderAt("/my-issues");
		await screen.findByText("No Issues assigned to you");
		fireEvent.keyDown(window, { key: "/" });
		const input = screen.getByPlaceholderText(/Search Issues/);
		expect(input).toBeTruthy();
		// Typed text must follow the theme (token, not browser default).
		expect(input.className).toContain("text-foreground");
		await waitFor(() => expect(document.activeElement).toBe(input));
	});

	it("opens on Cmd+K and on Ctrl+K", async () => {
		mockCommon();
		renderAt("/my-issues");
		await screen.findByText("No Issues assigned to you");
		fireEvent.keyDown(window, { key: "k", metaKey: true });
		expect(screen.getByRole("dialog", { name: "Search" })).toBeTruthy();
		fireEvent.keyDown(screen.getByPlaceholderText(/Search Issues/), {
			key: "Escape",
		});
		expect(screen.queryByRole("dialog", { name: "Search" })).toBeNull();

		fireEvent.keyDown(window, { key: "k", ctrlKey: true });
		expect(screen.getByRole("dialog", { name: "Search" })).toBeTruthy();
	});

	it("does not open on a plain k", async () => {
		mockCommon();
		renderAt("/my-issues");
		await screen.findByText("No Issues assigned to you");
		fireEvent.keyDown(window, { key: "k" });
		expect(screen.queryByRole("dialog", { name: "Search" })).toBeNull();
	});

	it("renders results grouped by Team and navigates on Enter", async () => {
		mockCommon();
		vi.mocked(searchIssues).mockResolvedValue({
			issues: [engIssue, dsgnIssue],
		});
		renderAt("/my-issues");
		await screen.findByText("No Issues assigned to you");

		fireEvent.keyDown(window, { key: "/" });
		const input = screen.getByPlaceholderText(/Search Issues/);
		fireEvent.change(input, { target: { value: "core" } });
		await waitFor(() =>
			expect(searchIssues).toHaveBeenCalledWith(
				"core",
				expect.any(AbortSignal),
			),
		);

		const dialog = screen.getByRole("dialog", { name: "Search" });
		expect(await within(dialog).findByText("Engineering")).toBeTruthy();
		expect(within(dialog).getByText("Design")).toBeTruthy();
		expect(within(dialog).getByText("ENG-1")).toBeTruthy();
		expect(within(dialog).getByText("DSGN-3")).toBeTruthy();

		// Arrow keys move the selection (wrapping), Enter opens the Issue.
		fireEvent.keyDown(input, { key: "ArrowDown" });
		expect(
			within(dialog).getByRole("button", { current: true }).textContent,
		).toContain("DSGN-3");
		fireEvent.keyDown(input, { key: "ArrowDown" });
		expect(
			within(dialog).getByRole("button", { current: true }).textContent,
		).toContain("ENG-1");

		fireEvent.keyDown(input, { key: "Enter" });
		expect(screen.queryByRole("dialog", { name: "Search" })).toBeNull();
		// The selected Issue (ENG-1) detail page is rendered.
		expect(
			await screen.findByRole("button", {
				name: "Edit title: Set up the core loop",
			}),
		).toBeTruthy();
	});

	it("shows the no-results state and closes on Esc", async () => {
		mockCommon();
		vi.mocked(searchIssues).mockResolvedValue({ issues: [] });
		renderAt("/my-issues");
		await screen.findByText("No Issues assigned to you");

		fireEvent.keyDown(window, { key: "/" });
		const input = screen.getByPlaceholderText(/Search Issues/);
		fireEvent.change(input, { target: { value: "nothing" } });
		expect(await screen.findByText("No Issues match “nothing”.")).toBeTruthy();

		fireEvent.keyDown(input, { key: "Escape" });
		expect(screen.queryByRole("dialog", { name: "Search" })).toBeNull();
	});

	it("does not fetch while the query is empty", async () => {
		mockCommon();
		renderAt("/my-issues");
		await screen.findByText("No Issues assigned to you");
		fireEvent.keyDown(window, { key: "/" });
		await new Promise((resolve) => setTimeout(resolve, 200));
		expect(searchIssues).not.toHaveBeenCalled();
	});

	it("keeps shortcuts suppressed while typing in the search input", async () => {
		mockCommon();
		vi.mocked(searchIssues).mockResolvedValue({ issues: [] });
		vi.mocked(listIssues).mockResolvedValue({
			issues: [issueFixture],
			next_cursor: null,
		});
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.keyDown(window, { key: "/" });
		const input = screen.getByPlaceholderText(/Search Issues/);
		fireEvent.keyDown(input, { key: "c" });
		expect(screen.queryByRole("dialog", { name: "New Issue" })).toBeNull();
	});
});
