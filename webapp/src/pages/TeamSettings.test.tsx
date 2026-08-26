import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "@/api/auth";
import type { TeamMember, WorkflowState } from "@/api/teams";

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
		listTeamMembers: vi.fn(),
		listTeamMemberCandidates: vi.fn(),
		addTeamMember: vi.fn(),
		updateTeamMemberRole: vi.fn(),
		removeTeamMember: vi.fn(),
		listTeamStates: vi.fn(),
		listTeamLabels: vi.fn(),
		createTeamLabel: vi.fn(),
		updateTeamLabel: vi.fn(),
		deleteTeamLabel: vi.fn(),
		updateTeam: vi.fn(),
		archiveTeam: vi.fn(),
		restoreTeam: vi.fn(),
		createTeamState: vi.fn(),
		updateTeamState: vi.fn(),
		reorderTeamStates: vi.fn(),
		deleteTeamState: vi.fn(),
	};
});

vi.mock("@/api/issues", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/issues")>();
	return {
		...actual,
		listIssues: vi.fn(),
		listAllIssues: vi.fn(),
		getIssue: vi.fn(),
		transitionIssue: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const {
	archiveTeam,
	addTeamMember,
	createTeamState,
	deleteTeamState,
	listTeamMemberCandidates,
	listTeamMembers,
	listTeamStates,
	listTeams,
	removeTeamMember,
	restoreTeam,
	updateTeam,
	updateTeamMemberRole,
	updateTeamState,
} = await import("@/api/teams");
const { listAllIssues } = await import("@/api/issues");
const { renderAt } = await import("../test/test-router");
const {
	issueFixture,
	meFixture,
	memberFixture,
	statesFixture,
	teamFixture,
	testStateId,
	testTeamId,
} = await import("../test/fixtures");
const { ApiError } = await import("../api/client");
const { toast } = await import("../components/ui/Toast");

const coldStateId = "33333333-3333-4333-8333-333333333399";

const coldState: WorkflowState = {
	id: coldStateId,
	name: "Cold",
	category: "backlog",
	color: "#336699",
	position: 6,
	version: 1,
};

const statesWithCold: WorkflowState[] = [...statesFixture, coldState];

const otherMember: TeamMember = {
	id: "99999999-9999-4999-8999-999999999999",
	display_name: "Member",
	avatar_url: null,
	role: "member",
};

const candidateUser = {
	id: "88888888-8888-4888-8888-888888888888",
	display_name: "New Person",
	email: "new@example.com",
	avatar_url: null,
};

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

function renderSettings() {
	vi.mocked(getMe).mockResolvedValue(meFixture);
	vi.mocked(listTeams).mockResolvedValue([teamFixture]);
	renderAt("/teams/ENG/settings");
}

describe("TeamSettings", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders the Team section and the three tabs for owners", async () => {
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });

		expect(screen.getByRole("heading", { name: "Team" })).toBeTruthy();
		expect(screen.getByRole("textbox", { name: "Name" })).toBeTruthy();
		expect(screen.getByRole("textbox", { name: "Description" })).toBeTruthy();
		expect(screen.getByRole("button", { name: "Members" })).toBeTruthy();
		expect(screen.getByRole("button", { name: "Labels" })).toBeTruthy();
		expect(
			screen.getByRole("button", { name: "Save" }).hasAttribute("disabled"),
		).toBe(true);
	});

	it("shows the owner-access message to a non-owner member", async () => {
		vi.mocked(getMe).mockResolvedValue(memberMe);
		vi.mocked(listTeams).mockResolvedValue([teamFixture]);
		renderAt("/teams/ENG/settings");
		expect(await screen.findByText("Owner access required")).toBeTruthy();
		expect(screen.queryByRole("button", { name: "Workflow" })).toBeNull();
	});

	it("shows the archived banner with an Admin Restore and no tabs", async () => {
		const archived = {
			...teamFixture,
			archived_at: new Date("2026-08-25T00:00:00Z"),
		};
		vi.mocked(getMe).mockResolvedValue(meFixture);
		vi.mocked(listTeams).mockResolvedValue([archived]);
		vi.mocked(restoreTeam).mockResolvedValue(teamFixture);
		renderAt("/teams/ENG/settings");
		expect(await screen.findByText("This Team is archived")).toBeTruthy();
		expect(screen.queryByRole("button", { name: "Workflow" })).toBeNull();

		fireEvent.click(screen.getByRole("button", { name: "Restore Team" }));
		fireEvent.click(screen.getByRole("button", { name: "Confirm restore?" }));
		await waitFor(() =>
			expect(vi.mocked(restoreTeam)).toHaveBeenCalledWith(testTeamId),
		);
	});

	it("saves the name and description through the Team edit endpoint", async () => {
		const updated = { ...teamFixture, name: "Platform" };
		vi.mocked(updateTeam).mockResolvedValue(updated);
		renderSettings();
		await screen.findByRole("button", { name: "Save" });

		fireEvent.change(screen.getByRole("textbox", { name: "Name" }), {
			target: { value: "Platform" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Save" }));

		await waitFor(() =>
			expect(vi.mocked(updateTeam)).toHaveBeenCalledWith(testTeamId, {
				name: "Platform",
				description: null,
			}),
		);
	});

	it("archives the Team with a two-step confirmation (Admin)", async () => {
		vi.mocked(archiveTeam).mockResolvedValue({
			...teamFixture,
			archived_at: new Date("2026-08-25T00:00:00Z"),
		});
		renderSettings();
		const archive = await screen.findByRole("button", { name: "Archive Team" });
		fireEvent.click(archive);
		expect(
			screen.getByRole("button", { name: "Confirm archive?" }),
		).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: "Confirm archive?" }));
		await waitFor(() =>
			expect(vi.mocked(archiveTeam)).toHaveBeenCalledWith(testTeamId),
		);
	});

	it("changes a member's role from the Members tab", async () => {
		vi.mocked(listTeamMembers).mockResolvedValue([otherMember, memberFixture]);
		vi.mocked(updateTeamMemberRole).mockResolvedValue({
			...otherMember,
			role: "owner",
		});
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });

		const roleSelect = await screen.findByRole("combobox", {
			name: "Role for Member",
		});
		fireEvent.change(roleSelect, { target: { value: "owner" } });

		await waitFor(() =>
			expect(vi.mocked(updateTeamMemberRole)).toHaveBeenCalledWith(
				testTeamId,
				otherMember.id,
				"owner",
			),
		);
	});

	it("adds a member from the candidate picker", async () => {
		vi.mocked(listTeamMembers).mockResolvedValue([otherMember]);
		vi.mocked(listTeamMemberCandidates).mockResolvedValue([candidateUser]);
		vi.mocked(addTeamMember).mockResolvedValue({
			...candidateUser,
			role: "member",
		});
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });

		fireEvent.click(screen.getByRole("button", { name: "Add member" }));
		const picker = await screen.findByRole("list", {
			name: "Member candidates",
		});
		fireEvent.click(
			await within(picker).findByRole("button", { name: /New Person/ }),
		);

		await waitFor(() =>
			expect(vi.mocked(addTeamMember)).toHaveBeenCalledWith(
				testTeamId,
				candidateUser.id,
			),
		);
	});

	it("removes a member with a two-step confirmation", async () => {
		vi.mocked(listTeamMembers).mockResolvedValue([otherMember]);
		vi.mocked(removeTeamMember).mockResolvedValue(undefined);
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });

		fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
		fireEvent.click(await screen.findByRole("button", { name: "Confirm?" }));

		await waitFor(() =>
			expect(vi.mocked(removeTeamMember)).toHaveBeenCalledWith(
				testTeamId,
				otherMember.id,
			),
		);
	});

	it("lists the Workflow States with their Issue counts", async () => {
		vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
		vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });
		fireEvent.click(screen.getByRole("button", { name: "Workflow" }));

		await screen.findByLabelText("Name for Backlog");
		expect(screen.getByLabelText("Name for Done")).toBeTruthy();
		// The one Issue sits in Backlog (testStateId).
		const list = screen.getByRole("list", { name: "Workflow States" });
		const rows = within(list).getAllByRole("listitem");
		expect(within(rows[0]).getByText("1")).toBeTruthy();
		expect(within(rows[4]).getByText("0")).toBeTruthy();
	});

	it("renames a State carrying the last-seen version", async () => {
		vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
		vi.mocked(listAllIssues).mockResolvedValue([]);
		vi.mocked(updateTeamState).mockResolvedValue({
			...statesFixture[0],
			name: "Baklog",
			version: 2,
		});
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });
		fireEvent.click(screen.getByRole("button", { name: "Workflow" }));

		const nameInput = await screen.findByLabelText("Name for Backlog");
		fireEvent.change(nameInput, { target: { value: "Baklog" } });
		fireEvent.blur(nameInput);

		await waitFor(() =>
			expect(vi.mocked(updateTeamState)).toHaveBeenCalledWith(
				testTeamId,
				testStateId,
				{ version: 1, name: "Baklog" },
			),
		);
	});

	it("toasts the server message and refetches States on a stale 409", async () => {
		vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
		vi.mocked(listAllIssues).mockResolvedValue([]);
		vi.mocked(updateTeamState).mockRejectedValue(
			new ApiError(409, {
				code: "conflict",
				message: "The State was changed by someone else. Reload and try again.",
			}),
		);
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });
		fireEvent.click(screen.getByRole("button", { name: "Workflow" }));

		const nameInput = await screen.findByLabelText("Name for Backlog");
		fireEvent.change(nameInput, { target: { value: "Stale" } });
		fireEvent.blur(nameInput);

		await waitFor(() =>
			expect(vi.mocked(toast)).toHaveBeenCalledWith(
				"The State was changed by someone else. Reload and try again.",
			),
		);
		// The 409 invalidated the observed States query: it refetched.
		await waitFor(() =>
			expect(vi.mocked(listTeamStates)).toHaveBeenCalledTimes(2),
		);
	});

	it("asks for a same-category migration target before deleting a State with Issues", async () => {
		vi.mocked(listTeamStates).mockResolvedValue(statesWithCold);
		vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
		vi.mocked(deleteTeamState).mockResolvedValue(undefined);
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });
		fireEvent.click(screen.getByRole("button", { name: "Workflow" }));

		await screen.findByLabelText("Name for Backlog");
		const list = screen.getByRole("list", { name: "Workflow States" });
		const rows = within(list).getAllByRole("listitem");
		fireEvent.click(within(rows[0]).getByRole("button", { name: "Delete" }));
		fireEvent.click(within(rows[0]).getByRole("button", { name: "Confirm?" }));

		const dialog = await screen.findByRole("dialog", {
			name: "Delete Backlog?",
		});
		// Only the other backlog State (Cold) is offered.
		const target = within(dialog).getByRole("combobox", {
			name: "Migrate Issues to",
		});
		expect(within(target).getByText("Cold")).toBeTruthy();
		expect(within(target).queryByText(statesFixture[1].name)).toBeNull();

		fireEvent.change(target, { target: { value: coldStateId } });
		fireEvent.click(
			within(dialog).getByRole("button", { name: "Migrate and delete" }),
		);

		await waitFor(() =>
			expect(vi.mocked(deleteTeamState)).toHaveBeenCalledWith(
				testTeamId,
				testStateId,
				{ version: 1, migrate_to_state_id: coldStateId },
			),
		);
	});

	it("deletes a State without Issues directly", async () => {
		vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
		vi.mocked(listAllIssues).mockResolvedValue([]);
		vi.mocked(deleteTeamState).mockResolvedValue(undefined);
		renderSettings();
		await screen.findByRole("button", { name: "Workflow" });
		fireEvent.click(screen.getByRole("button", { name: "Workflow" }));

		await screen.findByLabelText("Name for Backlog");
		const list = screen.getByRole("list", { name: "Workflow States" });
		const rows = within(list).getAllByRole("listitem");
		fireEvent.click(within(rows[0]).getByRole("button", { name: "Delete" }));
		fireEvent.click(within(rows[0]).getByRole("button", { name: "Confirm?" }));

		await waitFor(() =>
			expect(vi.mocked(deleteTeamState)).toHaveBeenCalledWith(
				testTeamId,
				testStateId,
				{
					version: 1,
				},
			),
		);
	});
});
it("adds a new State from the add-State dialog", async () => {
	vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
	vi.mocked(listAllIssues).mockResolvedValue([]);
	vi.mocked(createTeamState).mockResolvedValue({
		...coldState,
		name: "Testing",
		category: "unstarted",
	});
	renderSettings();
	await screen.findByRole("button", { name: "Workflow" });
	fireEvent.click(screen.getByRole("button", { name: "Workflow" }));

	fireEvent.click(await screen.findByRole("button", { name: "New State" }));
	const dialog = await screen.findByRole("dialog", { name: "New State" });
	fireEvent.change(within(dialog).getByRole("textbox", { name: "Name" }), {
		target: { value: "Testing" },
	});
	fireEvent.change(within(dialog).getByRole("combobox", { name: "Category" }), {
		target: { value: "unstarted" },
	});
	fireEvent.click(within(dialog).getByRole("button", { name: "Add" }));

	await waitFor(() =>
		expect(vi.mocked(createTeamState)).toHaveBeenCalledWith(testTeamId, {
			name: "Testing",
			category: "unstarted",
			color: "#f2c94c",
		}),
	);
});

it("offers the migrate dialog when the server says the State still has Issues", async () => {
	vi.mocked(listTeamStates).mockResolvedValue(statesWithCold);
	vi.mocked(listAllIssues).mockResolvedValue([]);
	// The UI sees no Issues (they are all archived), but the server
	// refuses the delete: the migration dialog must open.
	vi.mocked(deleteTeamState).mockRejectedValue(
		new ApiError(400, {
			code: "validation_error",
			message: "The State still has Issues; choose a State to migrate them to",
		}),
	);
	renderSettings();
	await screen.findByRole("button", { name: "Workflow" });
	fireEvent.click(screen.getByRole("button", { name: "Workflow" }));

	await screen.findByLabelText("Name for Backlog");
	const list = screen.getByRole("list", { name: "Workflow States" });
	const rows = within(list).getAllByRole("listitem");
	fireEvent.click(within(rows[0]).getByRole("button", { name: "Delete" }));
	fireEvent.click(within(rows[0]).getByRole("button", { name: "Confirm?" }));

	const dialog = await screen.findByRole("dialog", {
		name: "Delete Backlog?",
	});
	expect(
		within(dialog).getByRole("combobox", { name: "Migrate Issues to" }),
	).toBeTruthy();
});
