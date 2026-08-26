import { type ReactNode, useCallback, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

/**
 * Off-canvas sidebar for narrow screens (< 768px, ticket 10, brief §7.4):
 * a fixed overlay with backdrop; Esc or a backdrop click closes it; focus
 * moves in on open and returns to the trigger on close. The desktop
 * sidebar is the static, always-visible version.
 */
export function SidebarDrawer({
	open,
	onClose,
	children,
}: {
	open: boolean;
	onClose: () => void;
	children: ReactNode;
}) {
	const panelRef = useRef<HTMLDivElement>(null);
	const previousFocus = useRef<HTMLElement | null>(null);

	useEffect(() => {
		if (!open) return;
		previousFocus.current = document.activeElement as HTMLElement | null;
		panelRef.current?.focus();
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === "Escape") {
				event.stopPropagation();
				onClose();
			}
		};
		document.addEventListener("keydown", onKeyDown, true);
		return () => {
			document.removeEventListener("keydown", onKeyDown, true);
			previousFocus.current?.focus();
		};
	}, [open, onClose]);

	const onBackdropClick = useCallback(
		(event: React.MouseEvent<HTMLDivElement>) => {
			if (event.target === event.currentTarget) onClose();
		},
		[onClose],
	);

	if (!open) return null;

	return createPortal(
		// biome-ignore lint/a11y/noStaticElementInteractions: backdrop click closes the drawer; Esc is the keyboard path
		<div
			className="fixed inset-0 z-50 bg-black/40"
			onMouseDown={onBackdropClick}
		>
			<div
				ref={panelRef}
				role="dialog"
				aria-modal="true"
				aria-label="Navigation"
				tabIndex={-1}
				className="h-full w-64 max-w-full border-r border-line bg-surface shadow-xl outline-none"
			>
				{children}
			</div>
		</div>,
		document.body,
	);
}
