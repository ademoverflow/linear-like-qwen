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

const { getMe, login } = await import("@/api/auth");
const { ApiError } = await import("@/api/client");
const { renderAt } = await import("../test/test-router");

const unauthenticated = () =>
	new ApiError(401, { code: "unauthenticated", message: "Not authenticated" });

describe("Login", () => {
	it("renders the login form", async () => {
		vi.mocked(getMe).mockRejectedValue(unauthenticated());
		renderAt("/login");
		expect(await screen.findByRole("heading", { name: "Log in" })).toBeTruthy();
		expect(screen.getByRole("textbox", { name: "Email" })).toBeTruthy();
		expect(screen.getByPlaceholderText("Your password")).toBeTruthy();
	});

	it("shows an alert when the credentials are rejected", async () => {
		vi.mocked(getMe).mockRejectedValue(unauthenticated());
		vi.mocked(login).mockRejectedValue(
			new ApiError(401, {
				code: "unauthenticated",
				message: "Invalid email or password",
			}),
		);
		renderAt("/login");
		fireEvent.change(await screen.findByRole("textbox", { name: "Email" }), {
			target: { value: "admin@example.com" },
		});
		fireEvent.change(screen.getByPlaceholderText("Your password"), {
			target: { value: "wrong-pass" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Log in" }));
		const alert = await screen.findByRole("alert");
		expect(alert.textContent).toBe("Invalid email or password");
	});
});
