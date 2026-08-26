import { useEffect, useState } from "react";

function mediaQueryList(query: string): MediaQueryList | null {
	if (typeof window.matchMedia !== "function") return null;
	return window.matchMedia(query);
}

/**
 * Track a CSS media query (ticket 10: the 768px breakpoints). jsdom has no
 * window.matchMedia — without it the hook reports "no match"; tests stub it
 * via `stubMediaQueries` (test/media.ts).
 */
export function useMediaQuery(query: string): boolean {
	const [matches, setMatches] = useState(
		() => mediaQueryList(query)?.matches ?? false,
	);

	useEffect(() => {
		const mql = mediaQueryList(query);
		if (!mql) return;
		setMatches(mql.matches);
		const onChange = (event: MediaQueryListEvent) => setMatches(event.matches);
		mql.addEventListener("change", onChange);
		return () => mql.removeEventListener("change", onChange);
	}, [query]);

	return matches;
}
