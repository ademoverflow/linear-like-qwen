import { useEffect } from "react";

function isTypingTarget(element: Element | null): boolean {
	if (!(element instanceof HTMLElement)) return false;
	return (
		element.tagName === "INPUT" ||
		element.tagName === "TEXTAREA" ||
		element.tagName === "SELECT" ||
		element.isContentEditable
	);
}

export interface ShortcutOptions {
	/**
	 * Require the platform modifier (Cmd on macOS, Ctrl elsewhere) to be
	 * held — used for `Cmd/Ctrl+K`. Without it, any modifier suppresses.
	 */
	modifier?: boolean;
}

/**
 * Global single-key shortcut (brief §7.3). Never fires while focus is in an
 * input, textarea, select or contenteditable. With `modifier: true` the key
 * fires only with Cmd/Ctrl held (and no other modifier).
 */
export function useShortcut(
	key: string,
	handler: () => void,
	options: ShortcutOptions = {},
) {
	useEffect(() => {
		const onKeyDown = (event: KeyboardEvent) => {
			if (options.modifier) {
				if (!event.metaKey && !event.ctrlKey) return;
				if (event.altKey || event.shiftKey) return;
			} else if (event.metaKey || event.ctrlKey || event.altKey) {
				return;
			}
			if (isTypingTarget(document.activeElement)) return;
			if (event.key.toLowerCase() === key.toLowerCase()) {
				event.preventDefault();
				handler();
			}
		};
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [key, handler, options.modifier]);
}
