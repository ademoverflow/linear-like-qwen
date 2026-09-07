import { fireEvent, screen, within } from "@testing-library/react";
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

vi.mock("@/api/users", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/users")>();
	return {
		...actual,
		listUsers: vi.fn(),
		deactivateUser: vi.fn(),
		reactivateUser: vi.fn(),
		promoteUser: vi.fn(),
		demoteUser: vi.fn(),
	};
});

vi.mock("@/api/invitations", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/invitations")>();
	return {
		...actual,
		listInvitations: vi.fn(),
		createInvitation: vi.fn(),
	};
});

const { getMe } = await import("@/api/auth");
const { listTeams } = await import("@/api/teams");
const { listUsers } = await import("@/api/users");
const { createInvitation, listInvitations } = await import("@/api/invitations");
const { renderAt } = await import("../test/test-router");
const { meFixture } = await import("../test/fixtures");

const ISO = "2026-08-22T12:00:00.000Z";
const memberUser = {
	id: "55555555-5555-4555-8555-555555555555",
	email: "member@example.com",
	display_name: "Jane",
	avatar_url: null,
	is_admin: false,
	is_active: true,
	created_at: new Date(ISO),
};
const adminUser = { ...meFixture, display_name: "Root" };
const pendingInvitation = {
	id: "66666666-6666-4666-8666-666666666666",
	email: "invitee@example.com",
	invited_by: meFixture.id,
	expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
	accepted_at: null,
	created_at: new Date(ISO),
};

function setup() {
	vi.mocked(getMe).mockResolvedValue(meFixture);
	vi.mocked(listTeams).mockResolvedValue([]);
	vi.mocked(listUsers).mockResolvedValue([adminUser, memberUser]);
	vi.mocked(listInvitations).mockResolvedValue([pendingInvitation]);
}

describe("Admin", () => {
	it("lists Users with role and status for a workspace Admin", async () => {
		setup();
		renderAt("/admin");
		expect(await screen.findByRole("heading", { name: /admin/i })).toBeTruthy();
		const adminRow = await screen.findByRole("row", {
			name: /admin@example.com/,
		});
		const memberRow = screen.getByRole("row", { name: /member@example.com/ });
		expect(within(adminRow).getByText("Root")).toBeTruthy();
		expect(within(adminRow).getByText("Admin")).toBeTruthy();
		expect(within(adminRow).getByText("Active")).toBeTruthy();
		expect(within(memberRow).getByText("Jane")).toBeTruthy();
		expect(within(memberRow).getByText("Member")).toBeTruthy();
		expect(
			within(memberRow).getByRole("button", { name: "Promote" }),
		).toBeTruthy();
		expect(
			within(memberRow).getByRole("button", { name: "Deactivate" }),
		).toBeTruthy();
	});

	it("shows Invitations with statuses and reveals the token once on invite", async () => {
		setup();
		vi.mocked(createInvitation).mockResolvedValue({
			...pendingInvitation,
			token: "fresh-token-123",
		});
		renderAt("/admin");
		await screen.findByRole("heading", { name: /admin/i });

		await fireEvent.click(screen.getByRole("tab", { name: "Invitations" }));
		expect(await screen.findByText("invitee@example.com")).toBeTruthy();
		expect(screen.getByText("Pending")).toBeTruthy();

		const emailInput = screen.getByLabelText("Email");
		fireEvent.change(emailInput, { target: { value: "new@example.com" } });
		fireEvent.click(screen.getByRole("button", { name: /invite/i }));
		expect(await screen.findByText("fresh-token-123")).toBeTruthy();
		expect(createInvitation).toHaveBeenCalledWith("new@example.com");
	});

	function openInvitationsAndCreate() {
		renderAt("/admin");
		return screen;
	}

	async function inviteViaUi(screen: typeof screen) {
		await screen.findByRole("heading", { name: /admin/i });
		await fireEvent.click(screen.getByRole("tab", { name: "Invitations" }));
		const emailInput = screen.getByLabelText("Email");
		fireEvent.change(emailInput, { target: { value: "new@example.com" } });
		fireEvent.click(screen.getByRole("button", { name: /invite/i }));
		await screen.findByText("fresh-token-123");
	}

	it("copies the token when the clipboard API is available", async () => {
		setup();
		const writeText = vi.fn().mockResolvedValue(undefined);
		Object.defineProperty(navigator, "clipboard", {
			value: { writeText },
			configurable: true,
		});
		vi.mocked(createInvitation).mockResolvedValue({
			...pendingInvitation,
			token: "fresh-token-123",
		});
		await inviteViaUi(openInvitationsAndCreate());
		fireEvent.click(screen.getByRole("button", { name: "Copy" }));
		expect(await screen.findByText("Copied")).toBeTruthy();
		expect(writeText).toHaveBeenCalledWith("fresh-token-123");
	});

	it("falls back to execCommand when the clipboard API is unavailable", async () => {
		setup();
		Object.defineProperty(navigator, "clipboard", {
			value: undefined,
			configurable: true,
		});
		const execCommand = vi.fn().mockReturnValue(true);
		Object.defineProperty(document, "execCommand", {
			value: execCommand,
			configurable: true,
		});
		vi.mocked(createInvitation).mockResolvedValue({
			...pendingInvitation,
			token: "fresh-token-123",
		});
		await inviteViaUi(openInvitationsAndCreate());
		fireEvent.click(screen.getByRole("button", { name: "Copy" }));
		expect(await screen.findByText("Copied")).toBeTruthy();
		expect(execCommand).toHaveBeenCalledWith("copy");
	});

	it("shows a hint when copying fails entirely", async () => {
		setup();
		Object.defineProperty(navigator, "clipboard", {
			value: undefined,
			configurable: true,
		});
		Object.defineProperty(document, "execCommand", {
			value: vi.fn().mockReturnValue(false),
			configurable: true,
		});
		vi.mocked(createInvitation).mockResolvedValue({
			...pendingInvitation,
			token: "fresh-token-123",
		});
		await inviteViaUi(openInvitationsAndCreate());
		fireEvent.click(screen.getByRole("button", { name: "Copy" }));
		expect(await screen.findByText(/copy failed/i)).toBeTruthy();
	});

	it("redirects non-Admins away from the admin screen", async () => {
		vi.mocked(getMe).mockResolvedValue({ ...meFixture, is_admin: false });
		vi.mocked(listTeams).mockResolvedValue([]);
		vi.mocked(listUsers).mockResolvedValue([]);
		vi.mocked(listInvitations).mockResolvedValue([]);
		renderAt("/admin");
		expect(await screen.findByText("No Teams yet")).toBeTruthy();
		expect(screen.queryByRole("heading", { name: /admin/i })).toBeNull();
	});
});
