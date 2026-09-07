import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "@/api/auth";

vi.stubEnv("VITE_API_URL", "http://api.test");

vi.mock("@/api/auth", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/api/auth")>();
	return {
		...actual,
		updateMe: vi.fn(),
	};
});

vi.mock("@/components/ui/Toast", async (importOriginal) => {
	const actual = await importOriginal<typeof import("@/components/ui/Toast")>();
	return {
		...actual,
		toast: vi.fn(),
	};
});

const { updateMe } = await import("@/api/auth");
const { meFixture } = await import("../../test/fixtures");
const { toast } = await import("@/components/ui/Toast");
const { ThemeSwitcher } = await import("./ThemeSwitcher");

function renderSwitcher(
	preference: "system" | "light" | "dark",
	onChange: (preference: "system" | "light" | "dark") => void,
) {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	render(
		<QueryClientProvider client={queryClient}>
			<ThemeSwitcher preference={preference} onChange={onChange} />
		</QueryClientProvider>,
	);
	return { queryClient };
}

describe("ThemeSwitcher", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("shows the three states and marks the current one", () => {
		renderSwitcher("system", vi.fn());
		// No jest-dom matchers in this repo: assert via getAttribute.
		expect(
			screen
				.getByRole("button", { name: "Theme: System" })
				.getAttribute("aria-pressed"),
		).toBe("true");
		expect(
			screen
				.getByRole("button", { name: "Theme: Light" })
				.getAttribute("aria-pressed"),
		).toBe("false");
		expect(
			screen
				.getByRole("button", { name: "Theme: Dark" })
				.getAttribute("aria-pressed"),
		).toBe("false");
	});

	it("persists the choice via PATCH /auth/me and applies it from the response", async () => {
		vi.mocked(updateMe).mockResolvedValue({ ...meFixture, theme: "dark" });
		const onChange = vi.fn();
		const { queryClient } = renderSwitcher("system", onChange);

		fireEvent.click(screen.getByRole("button", { name: "Theme: Dark" }));

		await waitFor(() =>
			expect(vi.mocked(updateMe)).toHaveBeenCalledWith({ theme: "dark" }),
		);
		await waitFor(() => expect(onChange).toHaveBeenCalledWith("dark"));
		// The updated me is written into the profile cache (ADR 0004).
		expect(queryClient.getQueryData<Me>(["auth", "me"])?.theme).toBe("dark");
	});

	it("toasts when the preference cannot be saved", async () => {
		vi.mocked(updateMe).mockRejectedValue(new Error("boom"));
		renderSwitcher("light", vi.fn());

		fireEvent.click(screen.getByRole("button", { name: "Theme: Dark" }));

		await waitFor(() => expect(toast).toHaveBeenCalledWith("boom"));
	});
});
