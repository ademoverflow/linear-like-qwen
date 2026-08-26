import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Issue } from "@/api/issues";
import { stubMediaQueries } from "../../test/media";

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
	testUserId,
} = await import("../../test/fixtures");

const secondIssue: Issue = {
	...issueFixture,
	id: "66666666-6666-4666-8666-666666666666",
	number: 2,
	identifier: "ENG-2",
	title: "Second issue",
};

function mockCommon() {
	vi.mocked(getMe).mockResolvedValue(meFixture);
	vi.mocked(listTeams).mockResolvedValue([teamFixture]);
	vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
	vi.mocked(listTeamMembers).mockResolvedValue([
		{
			id: testUserId,
			display_name: "Admin",
			avatar_url: null,
			role: "owner",
		},
	]);
	vi.mocked(listTeamLabels).mockResolvedValue([]);
	vi.mocked(listIssues).mockResolvedValue({
		issues: [issueFixture, secondIssue],
		next_cursor: null,
	});
	vi.mocked(listAllIssues).mockResolvedValue([issueFixture, secondIssue]);
	vi.mocked(getIssue).mockResolvedValue(issueDetailFixture);
	vi.mocked(searchIssues).mockResolvedValue({ issues: [] });
}

afterEach(() => {
	vi.unstubAllGlobals();
	localStorage.clear();
	document.documentElement.classList.remove("dark");
});

describe("AppShell theming (ticket 10)", () => {
	it("system: follows the dark OS setting", async () => {
		stubMediaQueries({ desktop: true, systemDark: true });
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		await waitFor(() =>
			expect(document.documentElement.classList.contains("dark")).toBe(true),
		);
	});

	it("system: follows OS setting changes at runtime", async () => {
		const stub = stubMediaQueries({ desktop: true, systemDark: false });
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		expect(document.documentElement.classList.contains("dark")).toBe(false);
		stub.systemDark.set(true);
		await waitFor(() =>
			expect(document.documentElement.classList.contains("dark")).toBe(true),
		);
	});

	it("a manual light override wins over the dark OS setting", async () => {
		stubMediaQueries({ desktop: true, systemDark: true });
		mockCommon();
		vi.mocked(getMe).mockResolvedValue({ ...meFixture, theme: "light" });
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		await waitFor(() =>
			expect(document.documentElement.classList.contains("dark")).toBe(false),
		);
	});

	it("a manual dark preference applies the dark theme", async () => {
		stubMediaQueries({ desktop: true, systemDark: false });
		mockCommon();
		vi.mocked(getMe).mockResolvedValue({ ...meFixture, theme: "dark" });
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		await waitFor(() =>
			expect(document.documentElement.classList.contains("dark")).toBe(true),
		);
	});
});

describe("AppShell 768px layout (ticket 10)", () => {
	it("below 768px the sidebar becomes an off-canvas drawer", async () => {
		stubMediaQueries({ desktop: false });
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");

		// The static sidebar is gone; the narrow header offers the drawer.
		expect(screen.queryByRole("button", { name: "Log out" })).toBeNull();
		fireEvent.click(screen.getByRole("button", { name: "Open sidebar" }));
		const drawer = await screen.findByRole("dialog", { name: "Navigation" });
		expect(
			within(drawer).getByRole("link", { name: "My Issues" }),
		).toBeTruthy();
		// Esc closes the drawer. The drawer listens on the document capture
		// phase; in jsdom dispatching on window does not reach it.
		fireEvent.keyDown(document, { key: "Escape" });
		expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
	});

	it("keeps the static sidebar on desktop", async () => {
		stubMediaQueries({ desktop: true });
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		expect(screen.queryByRole("button", { name: "Open sidebar" })).toBeNull();
		expect(screen.getByRole("button", { name: "Log out" })).toBeTruthy();
	});
});

describe("AppShell shortcuts", () => {
	it("C opens the New Issue dialog", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.keyDown(window, { key: "c" });
		expect(
			await screen.findByRole("dialog", { name: "New Issue" }),
		).toBeTruthy();
	});

	it("? opens the cheat-sheet", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.keyDown(window, { key: "?" });
		expect(
			await screen.findByRole("dialog", { name: "Keyboard shortcuts" }),
		).toBeTruthy();
		expect(screen.getByText("This cheat-sheet")).toBeTruthy();
	});

	it("does not fire shortcuts while typing in an input", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.keyDown(window, { key: "/" });
		const input = screen.getByPlaceholderText(/Search Issues/);
		fireEvent.keyDown(input, { key: "c" });
		fireEvent.keyDown(input, { key: "?" });
		expect(screen.queryByRole("dialog", { name: "New Issue" })).toBeNull();
		expect(
			screen.queryByRole("dialog", { name: "Keyboard shortcuts" }),
		).toBeNull();
	});

	it("J/K and arrows move the keyboard cursor on the list", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");

		// The list shows both Issues (grouped by State).
		expect(screen.getByText("ENG-2")).toBeTruthy();

		fireEvent.keyDown(window, { key: "ArrowDown" });
		expect(
			document.querySelector(
				'[data-issue-id="44444444-4444-4444-8444-444444444444"] [aria-current="true"]',
			),
		).toBeTruthy();

		fireEvent.keyDown(window, { key: "j" });
		expect(
			document.querySelector(
				'[data-issue-id="66666666-6666-4666-8666-666666666666"] [aria-current="true"]',
			),
		).toBeTruthy();

		fireEvent.keyDown(window, { key: "k" });
		expect(
			document.querySelector(
				'[data-issue-id="44444444-4444-4444-8444-444444444444"] [aria-current="true"]',
			),
		).toBeTruthy();
	});

	it("Enter opens the Issue at the cursor", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.keyDown(window, { key: "ArrowDown" });
		fireEvent.keyDown(window, { key: "Enter" });
		// The detail page renders the Issue (panel + list).
		await waitFor(() =>
			expect(screen.getAllByText("Set up the core loop")).toHaveLength(2),
		);
	});

	it("S opens the State quick menu for the selected Issue", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.keyDown(window, { key: "s" });
		expect(await screen.findByText("Set State…")).toBeTruthy();
		// Esc closes the quick menu.
		fireEvent.keyDown(window, { key: "Escape" });
		expect(screen.queryByText("Set State…")).toBeNull();
	});

	it("A/P/L open their quick menus with nothing selected (selects first row)", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues");
		await screen.findByText("ENG-1");
		fireEvent.keyDown(window, { key: "a" });
		expect(await screen.findByText("Assign to…")).toBeTruthy();
		fireEvent.keyDown(window, { key: "Escape" });
		fireEvent.keyDown(window, { key: "p" });
		expect(await screen.findByText("Set Priority…")).toBeTruthy();
		fireEvent.keyDown(window, { key: "Escape" });
		fireEvent.keyDown(window, { key: "l" });
		expect(await screen.findByText(/No Labels in this Team yet/)).toBeTruthy();
	});
});
