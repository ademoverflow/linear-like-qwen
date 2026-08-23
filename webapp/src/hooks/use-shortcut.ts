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

/**
 * Global single-key shortcut (brief §7.3). Never fires while focus is in an
 * input, textarea, select or contenteditable.
 */
export function useShortcut(key: string, handler: () => void) {
	useEffect(() => {
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.metaKey || event.ctrlKey || event.altKey) return;
			if (isTypingTarget(document.activeElement)) return;
			if (event.key === key) {
				event.preventDefault();
				handler();
			}
		};
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [key, handler]);
}
