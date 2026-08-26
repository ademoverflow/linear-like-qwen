import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { stubMediaQueries } from "../test/media";
import {
	applyThemePreference,
	readStoredThemePreference,
	resolveThemePreference,
	storeThemePreference,
	THEME_STORAGE_KEY,
	useThemePreference,
} from "./use-theme";

afterEach(() => {
	localStorage.clear();
	document.documentElement.classList.remove("dark");
});

describe("resolveThemePreference", () => {
	it("follows the system setting for 'system'", () => {
		stubMediaQueries({ desktop: true, systemDark: false });
		expect(resolveThemePreference("system")).toBe("light");
	});

	it("follows the system setting for 'system' when the OS is dark", () => {
		stubMediaQueries({ desktop: true, systemDark: true });
		expect(resolveThemePreference("system")).toBe("dark");
	});

	it("ignores the system setting for explicit 'light' and 'dark'", () => {
		stubMediaQueries({ desktop: true, systemDark: true });
		expect(resolveThemePreference("light")).toBe("light");
		expect(resolveThemePreference("dark")).toBe("dark");
	});
});

describe("applyThemePreference", () => {
	it("toggles the dark class on <html>", () => {
		stubMediaQueries({ desktop: true, systemDark: true });
		applyThemePreference("dark");
		expect(document.documentElement.classList.contains("dark")).toBe(true);
		applyThemePreference("light");
		expect(document.documentElement.classList.contains("dark")).toBe(false);
	});
});

describe("stored theme mirror", () => {
	it("round-trips each preference", () => {
		for (const preference of ["system", "light", "dark"] as const) {
			storeThemePreference(preference);
			expect(readStoredThemePreference()).toBe(preference);
		}
	});

	it("returns null for an unknown stored value", () => {
		localStorage.setItem(THEME_STORAGE_KEY, "blue");
		expect(readStoredThemePreference()).toBeNull();
	});
});

describe("useThemePreference", () => {
	beforeEach(() => {
		document.documentElement.classList.remove("dark");
	});

	it("applies the stored preference on mount", () => {
		stubMediaQueries({ desktop: true, systemDark: false });
		storeThemePreference("dark");
		const { unmount } = renderHook(() => useThemePreference());
		expect(document.documentElement.classList.contains("dark")).toBe(true);
		unmount();
	});

	it("follows OS setting changes while on 'system'", async () => {
		const stub = stubMediaQueries({ desktop: true, systemDark: false });
		const { unmount } = renderHook(() => useThemePreference());
		expect(document.documentElement.classList.contains("dark")).toBe(false);
		stub.systemDark.set(true);
		await waitFor(() =>
			expect(document.documentElement.classList.contains("dark")).toBe(true),
		);
		unmount();
	});

	it("stops following the OS once an explicit preference is set", async () => {
		const stub = stubMediaQueries({ desktop: true, systemDark: false });
		const { result, unmount } = renderHook(() => useThemePreference());
		// Wait for the state (and the effect that detaches the system
		// listener) to settle before flipping the OS setting.
		result.current.setPreference("light");
		await waitFor(() => expect(result.current.preference).toBe("light"));
		stub.systemDark.set(true);
		expect(document.documentElement.classList.contains("dark")).toBe(false);
		expect(result.current.preference).toBe("light");
		unmount();
	});
});
