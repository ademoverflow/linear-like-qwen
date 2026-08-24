import {
	QueryClient,
	QueryClientProvider,
	useQuery,
} from "@tanstack/react-query";
import {
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Issue } from "@/api/issues";

vi.stubEnv("VITE_API_URL", "http://api.test");

vi.mock("@/components/ui/Toast", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/components/ui/Toast")>();
	return {
		...actual,
		toast: vi.fn(),
	};
});

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
	};
});

vi.mock("@/api/issues", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/issues")>();
	return {
		...actual,
		listIssues: vi.fn(),
		listAllIssues: vi.fn(),
		createIssue: vi.fn(),
		getIssue: vi.fn(),
		transitionIssue: vi.fn(),
		listIssueActivity: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeamStates, listTeams } = await import("@/api/teams");
const { getIssue, listAllIssues, listIssueActivity, transitionIssue } =
	await import("@/api/issues");
const { renderAt } = await import("../test/test-router");
const {
	doneStateId,
	issueDetailFixture,
	issueFixture,
	meFixture,
	statesFixture,
	teamFixture,
	testIssueId,
	testStateId,
	testTeamId,
} = await import("../test/fixtures");
const { targetStateForDrop } = await import("../components/issues/Board");
const { useTransitionIssue } = await import("../hooks/use-transition-issue");
const { ApiError } = await import("../api/client");
const { queryKeys } = await import("../api/query-keys");
const { toast } = await import("../components/ui/Toast");

const doneIssueFixture: Issue = {
	...issueFixture,
	id: "44444444-4444-4444-8444-444444444442",
	number: 2,
	identifier: "ENG-2",
	title: "Second Issue",
	state_id: doneStateId,
	state_name: "Done",
	state_category: "completed",
	state_color: "#4cb371",
	completed_at: new Date("2026-08-22T12:00:00.000Z"),
};

function DetailObserver() {
	// Mirrors the mounted detail panel: the invalidation in the hook only
	// refetches while an observer is active.
	useQuery({
		queryKey: queryKeys.issues.detail(testIssueId),
		queryFn: () => getIssue(testIssueId),
	});
	return null;
}

function ListObserver() {
	useQuery({
		queryKey: queryKeys.issues.team(testTeamId),
		queryFn: () => listAllIssues(testTeamId),
	});
	return null;
}

function ActivityObserver() {
	useQuery({
		queryKey: queryKeys.issues.activity(testIssueId),
		queryFn: () => listIssueActivity(testIssueId),
	});
	return null;
}

function TransitionHarness() {
	const transition = useTransitionIssue(testTeamId);
	return (
		<div>
			<button
				type="button"
				onClick={() =>
					transition.mutate({
						issue_id: testIssueId,
						state_id: doneStateId,
						updated_at: issueDetailFixture.updated_at,
					})
				}
			>
				Move to Done
			</button>
			<DetailObserver />
			<ListObserver />
			<ActivityObserver />
		</div>
	);
}

function renderHarness() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	queryClient.setQueryData(
		queryKeys.issues.detail(testIssueId),
		issueDetailFixture,
	);
	queryClient.setQueryData(queryKeys.issues.team(testTeamId), [issueFixture]);
	queryClient.setQueryData(queryKeys.teams.states(testTeamId), statesFixture);
	render(
		<QueryClientProvider client={queryClient}>
			<TransitionHarness />
		</QueryClientProvider>,
	);
	return { queryClient };
}

describe("TeamBoard", () => {
	it("renders one column per Workflow State in position order, with Issues grouped by State", async () => {
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
		vi.mocked(listAllIssues).mockResolvedValue([
			issueFixture,
			doneIssueFixture,
		]);
		renderAt("/teams/ENG/board");
		await screen.findByText("Second Issue");

		const groups = screen.getAllByRole("region");
		expect(groups.map((group) => group.getAttribute("aria-label"))).toEqual([
			"Backlog",
			"Todo",
			"In Progress",
			"In Review",
			"Done",
			"Canceled",
		]);
		expect(
			within(screen.getByRole("region", { name: "Backlog" })).getByText(
				"ENG-1",
			),
		).toBeTruthy();
		expect(
			within(screen.getByRole("region", { name: "Done" })).getByText("ENG-2"),
		).toBeTruthy();
	});

	it("carries ARIA roles on columns, lists and cards, and a drag handle per card", async () => {
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
		vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
		renderAt("/teams/ENG/board");
		await screen.findByText("Set up the core loop");

		const backlog = screen.getByRole("region", { name: "Backlog" });
		expect(
			within(backlog).getByRole("list", { name: "Backlog Issues" }),
		).toBeTruthy();
		expect(within(backlog).getByRole("listitem")).toBeTruthy();
		expect(
			screen.getByRole("button", { name: "Drag ENG-1: Set up the core loop" }),
		).toBeTruthy();
	});

	it("links the sidebar Board entry to the Team's board", async () => {
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
		vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
		renderAt("/teams/ENG/board");
		await screen.findByText("Set up the core loop");
		expect(screen.getByRole("link", { name: "Board" })).toBeTruthy();
	});

	it("shows the empty state when the Team has no Issues", async () => {
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
		vi.mocked(listAllIssues).mockResolvedValue([]);
		renderAt("/teams/ENG/board");
		expect(await screen.findByText("No Issues yet")).toBeTruthy();
	});

	it("resolves the drop target: column ids map to their State, card ids to their State", () => {
		const issues = [issueFixture, doneIssueFixture];
		expect(targetStateForDrop(doneStateId, issues, statesFixture)).toBe(
			doneStateId,
		);
		expect(targetStateForDrop(issueFixture.id, issues, statesFixture)).toBe(
			testStateId,
		);
		expect(targetStateForDrop("not-an-id", issues, statesFixture)).toBeNull();
	});
});

describe("useTransitionIssue (board drop seam)", () => {
	// The vi.fn() mocks accumulate call counts across tests; reset them so
	// the per-test call-count assertions are exact.
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("moves the cached Issue optimistically and sends the raw last-seen updated_at", async () => {
		vi.mocked(transitionIssue).mockResolvedValue({
			...issueFixture,
			state_name: "Done",
			state_category: "completed",
			state_color: "#4cb371",
			completed_at: new Date("2026-08-24T10:00:00.000Z"),
			updated_at: "2026-08-24T10:00:00.000001+00:00",
		});
		vi.mocked(getIssue).mockResolvedValue(issueDetailFixture);
		vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
		vi.mocked(listIssueActivity).mockResolvedValue([]);
		const { queryClient } = renderHarness();
		fireEvent.click(screen.getByRole("button", { name: "Move to Done" }));

		await waitFor(() => {
			const cached = queryClient.getQueryData<Issue[]>(
				queryKeys.issues.team(testTeamId),
			);
			expect(cached?.[0].state_name).toBe("Done");
			expect(cached?.[0].state_category).toBe("completed");
			expect(cached?.[0].completed_at).toBeInstanceOf(Date);
			expect(cached?.[0].canceled_at).toBeNull();
		});
		await waitFor(() =>
			expect(transitionIssue).toHaveBeenCalledWith(testIssueId, {
				state_id: doneStateId,
				updated_at: issueDetailFixture.updated_at,
			}),
		);
	});

	it("writes the authoritative response into the caches and refetches Activity", async () => {
		vi.mocked(transitionIssue).mockResolvedValue({
			...issueFixture,
			state_name: "Done",
			state_category: "completed",
			state_color: "#4cb371",
			completed_at: new Date("2026-08-24T10:00:00.000Z"),
			updated_at: "2026-08-24T10:00:00.000001+00:00",
		});
		vi.mocked(getIssue).mockResolvedValue(issueDetailFixture);
		vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
		vi.mocked(listIssueActivity).mockResolvedValue([]);
		const { queryClient } = renderHarness();
		fireEvent.click(screen.getByRole("button", { name: "Move to Done" }));

		await waitFor(() => {
			const cached = queryClient.getQueryData<Issue[]>(
				queryKeys.issues.team(testTeamId),
			);
			expect(cached?.[0].updated_at).toBe("2026-08-24T10:00:00.000001+00:00");
		});
		await waitFor(() => expect(listIssueActivity).toHaveBeenCalledTimes(2));
	});

	it("rolls back and toasts when the transition fails", async () => {
		vi.mocked(transitionIssue).mockRejectedValue(
			new ApiError(500, { code: "server_error", message: "Boom" }),
		);
		const { queryClient } = renderHarness();
		fireEvent.click(screen.getByRole("button", { name: "Move to Done" }));

		await waitFor(() => expect(vi.mocked(toast)).toHaveBeenCalledWith("Boom"));
		await waitFor(() => {
			const cached = queryClient.getQueryData<Issue[]>(
				queryKeys.issues.team(testTeamId),
			);
			expect(cached?.[0].state_name).toBe("Backlog");
			expect(cached?.[0].completed_at).toBeNull();
		});
	});

	it("refetches and toasts on a stale (409) transition", async () => {
		vi.mocked(transitionIssue).mockRejectedValue(
			new ApiError(409, {
				code: "conflict",
				message: "The Issue was updated by someone else. Reload and try again.",
			}),
		);
		vi.mocked(getIssue).mockResolvedValue(issueDetailFixture);
		vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
		vi.mocked(listIssueActivity).mockResolvedValue([]);
		renderHarness();
		fireEvent.click(screen.getByRole("button", { name: "Move to Done" }));

		await waitFor(() =>
			expect(vi.mocked(toast)).toHaveBeenCalledWith(
				"This Issue was changed by someone else. Loaded the latest version.",
			),
		);
		// Each observed query was fetched on mount and refetched after the 409.
		await waitFor(() => expect(getIssue).toHaveBeenCalledTimes(2));
		await waitFor(() => expect(listAllIssues).toHaveBeenCalledTimes(2));
		await waitFor(() => expect(listIssueActivity).toHaveBeenCalledTimes(2));
	});
});
