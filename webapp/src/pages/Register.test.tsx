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

const { getAuthStatus, getMe } = await import("@/api/auth");
const { ApiError } = await import("@/api/client");
const { renderAt } = await import("../test/test-router");

describe("Register", () => {
	it("offers bootstrap registration without a token while the user base is empty", async () => {
		vi.mocked(getMe).mockRejectedValue(
			new ApiError(401, {
				code: "unauthenticated",
				message: "Not authenticated",
			}),
		);
		vi.mocked(getAuthStatus).mockResolvedValue({ bootstrap_open: true });
		renderAt("/register");
		expect(
			await screen.findByRole("heading", { name: "Create your account" }),
		).toBeTruthy();
		expect(screen.queryByLabelText("Invitation token")).toBeNull();
	});

	it("requires an Invitation token once bootstrap is closed", async () => {
		vi.mocked(getMe).mockRejectedValue(
			new ApiError(401, {
				code: "unauthenticated",
				message: "Not authenticated",
			}),
		);
		vi.mocked(getAuthStatus).mockResolvedValue({ bootstrap_open: false });
		renderAt("/register");
		expect(
			await screen.findByRole("heading", { name: "Join with an invitation" }),
		).toBeTruthy();
		expect(
			await screen.findByRole("textbox", { name: "Invitation token" }),
		).toBeTruthy();
	});
});
