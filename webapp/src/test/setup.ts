import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest runs without `globals`, so Testing Library's automatic cleanup
// never registers — clean the DOM manually between tests.
afterEach(() => {
	cleanup();
});

// jsdom has no window.matchMedia (verified ticket 10). Default stub: the
// 768px desktop breakpoint matches (desktop layout unless a test stubs
// otherwise — see test/media.ts), the OS setting is light.
if (typeof window.matchMedia !== "function") {
	const desktopQuery = "(min-width: 768px)";
	window.matchMedia = (query: string) =>
		({
			matches: query === desktopQuery,
			media: query,
			onchange: null,
			conditionText: "",
			ports: [],
			isPortal: false,
			addEventListener: () => undefined,
			removeEventListener: () => undefined,
			dispatchEvent: () => false,
		}) as unknown as MediaQueryList;
}
