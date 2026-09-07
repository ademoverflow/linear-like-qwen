import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubMediaQueries } from "../test/media";

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
		getIssue: vi.fn(),
		updateIssue: vi.fn(),
		transitionIssue: vi.fn(),
		listIssueActivity: vi.fn(),
		archiveIssue: vi.fn(),
		restoreIssue: vi.fn(),
		deleteIssue: vi.fn(),
	};
});

vi.mock("@/api/comments", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/comments")>();
	return {
		...actual,
		listIssueComments: vi.fn(),
		createComment: vi.fn(),
		updateComment: vi.fn(),
		deleteComment: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeamLabels, listTeamMembers, listTeamStates, listTeams } =
	await import("@/api/teams");
const {
	archiveIssue,
	deleteIssue,
	getIssue,
	listAllIssues,
	listIssueActivity,
	listIssues,
	transitionIssue,
	updateIssue,
} = await import("@/api/issues");
const { createComment, deleteComment, listIssueComments, updateComment } =
	await import("@/api/comments");
const { renderAt } = await import("../test/test-router");
const {
	activityFixture,
	commentFixture,
	doneStateId,
	issueDetailFixture,
	issueFixture,
	labelFixture,
	labelsFixture,
	memberFixture,
	meFixture,
	statesFixture,
	teamFixture,
} = await import("../test/fixtures");

function mockCommon() {
	vi.mocked(getMe).mockResolvedValue(meFixture);
	vi.mocked(listTeams).mockResolvedValue([teamFixture]);
	vi.mocked(listAllIssues).mockResolvedValue([issueFixture]);
	vi.mocked(listTeamMembers).mockResolvedValue([memberFixture]);
	vi.mocked(getIssue).mockResolvedValue(issueDetailFixture);
	vi.mocked(listIssues).mockResolvedValue({
		issues: [issueFixture],
		next_cursor: null,
	});
	vi.mocked(listIssueActivity).mockResolvedValue(activityFixture);
	vi.mocked(listIssueComments).mockResolvedValue([commentFixture]);
	vi.mocked(listTeamStates).mockResolvedValue(statesFixture);
	vi.mocked(listTeamLabels).mockResolvedValue([]);
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe("IssueDetail", () => {
	it("shows the identifier, title, sanitized Markdown and properties", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		expect(await screen.findByText("ENG-1")).toBeTruthy();
		// Desktop layout: the title appears in the panel and in the
		// left list column (the list data resolves a wave later).
		await waitFor(() =>
			expect(screen.getAllByText("Set up the core loop")).toHaveLength(2),
		);
		// Markdown rendered (not raw): the heading and the bold span.
		expect(screen.getByRole("heading", { name: "Plan" })).toBeTruthy();
		expect(screen.getByText("bold")).toBeTruthy();
		// Properties.
		expect(
			await within(screen.getByLabelText("Properties")).findByText("Backlog"),
		).toBeTruthy();
		expect(screen.getByText("No priority")).toBeTruthy();
		expect(screen.getByText("Unassigned")).toBeTruthy();
		// The Labels property is a picker; the fixture Issue has no labels.
		expect(screen.getByText("No labels")).toBeTruthy();
	});

	it("below 768px the list column is gone and the panel is the full page", async () => {
		stubMediaQueries({ desktop: false });
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		await screen.findByText("ENG-1");
		// No list column: its New Issue button is absent and the title
		// appears only in the panel.
		expect(screen.queryByRole("button", { name: "New Issue" })).toBeNull();
		expect(screen.getAllByText("Set up the core loop")).toHaveLength(1);
		// Back navigation is the panel header link.
		expect(screen.getByRole("link", { name: /ENG \/ Issues/ })).toBeTruthy();
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

	it("the comment composer textarea uses the theme foreground token", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		await screen.findByText("ENG-1");
		// The MarkdownEditor textarea (description, comments) must carry the
		// token: its ancestors set no text colour, so typed text would
		// otherwise fall back to browser black in dark mode.
		const textarea = await screen.findByLabelText("Write a comment");
		expect(textarea.className).toContain("text-foreground");
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
		// Typed text must follow the theme (token, not browser default).
		expect(input.className).toContain("text-foreground");
		fireEvent.change(input, { target: { value: "New title" } });
		fireEvent.keyDown(input, { key: "Enter" });
		await waitFor(() =>
			expect(updateIssue).toHaveBeenCalledWith(issueFixture.id, {
				updated_at: issueDetailFixture.updated_at,
				title: "New title",
			}),
		);
	});

	it("applies Labels through the picker with the last-seen updated_at", async () => {
		mockCommon();
		vi.mocked(listTeamLabels).mockResolvedValue(labelsFixture);
		vi.mocked(updateIssue).mockResolvedValue({
			...issueFixture,
			labels: [
				{
					id: labelFixture.id,
					name: labelFixture.name,
					color: labelFixture.color,
				},
			],
		});
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		const labelsButton = await screen.findByRole("button", {
			name: "Change labels",
		});
		fireEvent.click(labelsButton);
		await screen.findByRole("dialog", { name: "Labels" });
		fireEvent.click(screen.getByRole("checkbox", { name: "bug" }));
		fireEvent.click(screen.getByRole("button", { name: "Save" }));
		await waitFor(() =>
			expect(updateIssue).toHaveBeenCalledWith(issueFixture.id, {
				updated_at: issueDetailFixture.updated_at,
				label_ids: [labelFixture.id],
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
	it("shows the Comment card with its author and sanitised Markdown", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		const card = await screen.findByRole("article");
		// The body is rendered Markdown (not raw).
		expect(within(card).getByText("Sanitised")).toBeTruthy();
		expect(within(card).queryByText("**Sanitised** comment body")).toBeNull();
		// Author + timestamp header.
		expect(within(card).getByText("Admin")).toBeTruthy();
		// The composer is present.
		expect(screen.getByLabelText("Write a comment")).toBeTruthy();
	});

	it("posts a Comment from the composer", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		const textarea = await screen.findByLabelText("Write a comment");
		fireEvent.change(textarea, { target: { value: "First take" } });
		fireEvent.click(screen.getByRole("button", { name: "Comment" }));
		await waitFor(() =>
			expect(createComment).toHaveBeenCalledWith(issueFixture.id, {
				body: "First take",
			}),
		);
	});

	it("shows Edit only for own Comments (Delete for an Admin's too)", async () => {
		mockCommon();
		vi.mocked(listIssueComments).mockResolvedValue([
			commentFixture,
			{
				...commentFixture,
				id: "99999999-9999-4999-8999-999999999999",
				author_id: "33333333-3333-4333-8333-333333333333",
				author_display_name: "Other",
			},
		]);
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		const [mine, theirs] = await screen.findAllByRole("article");
		expect(
			within(mine).getByRole("button", { name: "Edit comment" }),
		).toBeTruthy();
		expect(
			within(theirs).queryByRole("button", { name: "Edit comment" }),
		).toBeNull();
		// The fixture user is an Admin: deletion is offered on both.
		expect(
			within(mine).getByRole("button", { name: "Delete comment" }),
		).toBeTruthy();
		expect(
			within(theirs).getByRole("button", { name: "Delete comment" }),
		).toBeTruthy();
	});

	it("edits own Comment inline and saves the new body", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		await screen.findByRole("article");
		fireEvent.click(screen.getByRole("button", { name: "Edit comment" }));
		const editor = screen.getByLabelText("Comment body");
		fireEvent.change(editor, { target: { value: "Revised" } });
		fireEvent.click(screen.getByRole("button", { name: "Save" }));
		await waitFor(() =>
			expect(updateComment).toHaveBeenCalledWith(
				issueFixture.id,
				commentFixture.id,
				{ body: "Revised" },
			),
		);
	});

	it("deletes a Comment with a two-step confirm", async () => {
		mockCommon();
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		const card = await screen.findByRole("article");
		const deleteButton = screen.getByRole("button", { name: "Delete comment" });
		fireEvent.click(deleteButton);
		// The two-step confirm shows "Confirm?" (the aria-label is stable).
		expect(within(card).getByText("Confirm?")).toBeTruthy();
		fireEvent.click(deleteButton);
		await waitFor(() =>
			expect(deleteComment).toHaveBeenCalledWith(
				issueFixture.id,
				commentFixture.id,
			),
		);
	});

	it("archives the Issue from the header and returns to the list", async () => {
		mockCommon();
		vi.mocked(archiveIssue).mockResolvedValue(issueFixture);
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		await screen.findByText("ENG-1");
		fireEvent.click(screen.getByRole("button", { name: "Archive" }));
		await waitFor(() =>
			expect(archiveIssue).toHaveBeenCalledWith(issueFixture.id),
		);
		// The detail 404s once archived, so the panel returns to the list.
		expect(await screen.findByText("New Issue")).toBeTruthy();
	});

	it("hides Archive and Delete from plain members", async () => {
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
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		await screen.findByText("ENG-1");
		expect(screen.queryByRole("button", { name: "Archive" })).toBeNull();
		expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
	});

	it("hard-deletes only after the exact identifier is typed (Admin)", async () => {
		mockCommon();
		vi.mocked(deleteIssue).mockResolvedValue(undefined);
		renderAt("/teams/ENG/issues/44444444-4444-4444-8444-444444444444");
		await screen.findByText("ENG-1");
		fireEvent.click(screen.getByRole("button", { name: "Delete" }));
		const dialog = await screen.findByRole("dialog", {
			name: "Delete this Issue?",
		});
		const confirm = within(dialog).getByRole("button", {
			name: "Delete ENG-1",
		});
		expect(confirm.hasAttribute("disabled")).toBe(true);
		const input = within(dialog).getByLabelText(/Type ENG-1 to confirm/);
		fireEvent.change(input, { target: { value: "ENG-999" } });
		expect(confirm.hasAttribute("disabled")).toBe(true);
		fireEvent.change(input, { target: { value: "ENG-1" } });
		expect(confirm.hasAttribute("disabled")).toBe(false);
		fireEvent.click(confirm);
		await waitFor(() =>
			expect(deleteIssue).toHaveBeenCalledWith(issueFixture.id, "ENG-1"),
		);
	});
});
