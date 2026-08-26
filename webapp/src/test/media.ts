import { vi } from "vitest";

interface FakeMql {
	matches: boolean;
	media: string;
	listeners: Set<(event: { matches: boolean }) => void>;
}

/**
 * Controllable window.matchMedia for jsdom tests (ticket 10). `desktop`
 * picks the 768px breakpoint, `systemDark` the OS setting, and
 * `systemDark.set` fires the "change" event for listeners (the
 * system-following theme path).
 */
export function stubMediaQueries(opts: {
	desktop: boolean;
	systemDark?: boolean;
}): { systemDark: { set: (dark: boolean) => void } } {
	const state = { desktop: opts.desktop, systemDark: opts.systemDark ?? false };
	const mqls = new Map<string, FakeMql>();

	const mqlFor = (media: string): FakeMql => {
		let mql = mqls.get(media);
		if (!mql) {
			mql = {
				matches:
					media === "(min-width: 768px)"
						? state.desktop
						: media === "(prefers-color-scheme: dark)"
							? state.systemDark
							: false,
				media,
				listeners: new Set(),
			};
			mqls.set(media, mql);
		}
		return mql;
	};

	vi.stubGlobal("matchMedia", (media: string) => {
		const mql = mqlFor(media);
		return {
			get matches() {
				return mql.matches;
			},
			media: mql.media,
			onchange: null,
			conditionText: "",
			ports: [],
			isPortal: false,
			addEventListener: (
				_type: string,
				listener: (event: { matches: boolean }) => void,
			) => {
				mql.listeners.add(listener);
			},
			removeEventListener: (
				_type: string,
				listener: (event: { matches: boolean }) => void,
			) => {
				mql.listeners.delete(listener);
			},
			dispatchEvent: () => true,
		} as unknown as MediaQueryList;
	});

	return {
		systemDark: {
			set: (dark: boolean) => {
				state.systemDark = dark;
				const mql = mqls.get("(prefers-color-scheme: dark)");
				if (mql) {
					mql.matches = dark;
					mql.listeners.forEach((listener) => {
						listener({ matches: dark });
					});
				}
			},
		},
	};
}
