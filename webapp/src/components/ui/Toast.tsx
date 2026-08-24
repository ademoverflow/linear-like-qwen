import { useSyncExternalStore } from "react";

interface ToastItem {
	id: number;
	message: string;
}

let toasts: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit() {
	for (const listener of listeners) listener();
}

/** Show a toast (brief §7.4: toast on optimistic-update error). */
export function toast(message: string) {
	const item: ToastItem = { id: nextId, message };
	nextId += 1;
	toasts = [...toasts, item].slice(-3);
	emit();
	window.setTimeout(() => dismissToast(item.id), 4000);
}

export function dismissToast(id: number) {
	if (!toasts.some((t) => t.id === id)) return;
	toasts = toasts.filter((t) => t.id !== id);
	emit();
}

function subscribe(listener: () => void) {
	listeners.add(listener);
	return () => {
		listeners.delete(listener);
	};
}

function getSnapshot() {
	return toasts;
}

/** Fixed bottom-right stack of toasts; dismiss on click. */
export function Toaster() {
	const items = useSyncExternalStore(subscribe, getSnapshot);
	if (items.length === 0) return null;
	return (
		<output
			aria-live="polite"
			className="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col gap-2"
		>
			{items.map((item) => (
				<button
					key={item.id}
					type="button"
					onClick={() => dismissToast(item.id)}
					className="pointer-events-auto rounded-md bg-neutral-900 px-3 py-2 text-sm text-white shadow-lg dark:bg-neutral-700"
				>
					{item.message}
				</button>
			))}
		</output>
	);
}
