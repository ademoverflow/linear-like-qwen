import { X } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE =
	'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface DialogProps {
	open: boolean;
	title: string;
	onClose: () => void;
	children: ReactNode;
}

/**
 * Modal dialog: rendered in a portal, traps focus while open, closes on Esc
 * or backdrop click and restores focus to the previously focused element.
 */
export function Dialog({ open, title, onClose, children }: DialogProps) {
	const containerRef = useRef<HTMLDivElement>(null);
	const previousFocus = useRef<HTMLElement | null>(null);

	useEffect(() => {
		if (!open) return;
		previousFocus.current = document.activeElement as HTMLElement | null;
		const container = containerRef.current;
		const firstFocusable = container?.querySelector<HTMLElement>(FOCUSABLE);
		(firstFocusable ?? container)?.focus();

		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === "Escape") {
				event.stopPropagation();
				onClose();
				return;
			}
			if (event.key !== "Tab" || !container) return;
			const focusables = Array.from(
				container.querySelectorAll<HTMLElement>(FOCUSABLE),
			);
			if (focusables.length === 0) {
				event.preventDefault();
				container.focus();
				return;
			}
			const first = focusables[0];
			const last = focusables[focusables.length - 1];
			const active = document.activeElement;
			if (event.shiftKey && (active === first || active === container)) {
				event.preventDefault();
				last.focus();
			} else if (!event.shiftKey && active === last) {
				event.preventDefault();
				first.focus();
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
		// biome-ignore lint/a11y/noStaticElementInteractions: backdrop click closes the dialog; Esc is the keyboard path
		<div
			className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[15vh]"
			onMouseDown={onBackdropClick}
		>
			<div
				ref={containerRef}
				role="dialog"
				aria-modal="true"
				aria-label={title}
				tabIndex={-1}
				className="w-full max-w-md rounded-lg border border-line bg-surface p-4 shadow-xl outline-none"
			>
				<div className="mb-3 flex items-center justify-between">
					<h2 className="text-sm font-semibold text-foreground">{title}</h2>
					<button
						type="button"
						onClick={onClose}
						aria-label="Close dialog"
						className="rounded p-1 text-faint hover:bg-surface-subtle hover:text-foreground"
					>
						<X size={16} />
					</button>
				</div>
				{children}
			</div>
		</div>,
		document.body,
	);
}
