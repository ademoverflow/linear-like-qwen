import { useCallback, useEffect, useState } from "react";

/**
 * Theme preference (ticket 10, ADR 0014): "system" follows the OS setting
 * (matchMedia listener), "light"/"dark" are explicit. The authoritative
 * per-user value comes from GET /auth/me (me.theme); the localStorage
 * mirror lets the pre-paint script in index.html apply the theme before
 * React mounts (no flash of the wrong theme).
 */
export type ThemePreference = "system" | "light" | "dark";

export const THEME_STORAGE_KEY = "theme-preference";

function systemTheme(): "light" | "dark" {
	if (typeof window.matchMedia !== "function") return "light";
	return window.matchMedia("(prefers-color-scheme: dark)").matches
		? "dark"
		: "light";
}

export function resolveThemePreference(
	preference: ThemePreference,
): "light" | "dark" {
	return preference === "system" ? systemTheme() : preference;
}

export function applyThemePreference(preference: ThemePreference): void {
	document.documentElement.classList.toggle(
		"dark",
		resolveThemePreference(preference) === "dark",
	);
}

export function readStoredThemePreference(): ThemePreference | null {
	try {
		const value = localStorage.getItem(THEME_STORAGE_KEY);
		return value === "system" || value === "light" || value === "dark"
			? value
			: null;
	} catch {
		return null;
	}
}

export function storeThemePreference(preference: ThemePreference): void {
	try {
		localStorage.setItem(THEME_STORAGE_KEY, preference);
	} catch {
		// private mode etc. — the theme still applies for this tab
	}
}

/**
 * The theme preference for this tab: starts from the stored mirror, applies
 * the `.dark` class + writes the mirror on change, and follows OS setting
 * changes while on "system". AppShell syncs it from `me.theme` once the
 * profile loads.
 */
export function useThemePreference(): {
	preference: ThemePreference;
	setPreference: (preference: ThemePreference) => void;
} {
	const [preference, setPreferenceState] = useState<ThemePreference>(
		() => readStoredThemePreference() ?? "system",
	);

	useEffect(() => {
		applyThemePreference(preference);
		storeThemePreference(preference);
	}, [preference]);

	useEffect(() => {
		if (preference !== "system" || typeof window.matchMedia !== "function") {
			return;
		}
		const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
		const onChange = () => applyThemePreference("system");
		mediaQuery.addEventListener("change", onChange);
		return () => mediaQuery.removeEventListener("change", onChange);
	}, [preference]);

	const setPreference = useCallback(
		(next: ThemePreference) => setPreferenceState(next),
		[],
	);
	return { preference, setPreference };
}
