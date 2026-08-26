import { Dialog } from "@/components/ui/Dialog";

const SHORTCUTS: { keys: string; description: string }[] = [
	{ keys: "C", description: "New Issue" },
	{ keys: "/ or ⌘/Ctrl+K", description: "Search" },
	{ keys: "J / K or ↑ / ↓", description: "Move selection" },
	{ keys: "Enter", description: "Open Issue" },
	{ keys: "Esc", description: "Close menu / selection" },
	{ keys: "S", description: "Set State" },
	{ keys: "A", description: "Set Assignee" },
	{ keys: "P", description: "Set Priority" },
	{ keys: "L", description: "Toggle Labels" },
	{ keys: "?", description: "This cheat-sheet" },
];

/** The keyboard-shortcut cheat-sheet (brief §7.3, opened with `?`). */
export function ShortcutCheatsheet({
	open,
	onClose,
}: {
	open: boolean;
	onClose: () => void;
}) {
	return (
		<Dialog open={open} title="Keyboard shortcuts" onClose={onClose}>
			<ul className="flex flex-col gap-1.5">
				{SHORTCUTS.map((shortcut) => (
					<li
						key={shortcut.keys}
						className="flex items-center justify-between gap-4 text-sm"
					>
						<span className="text-neutral-600 dark:text-neutral-300">
							{shortcut.description}
						</span>
						<kbd className="shrink-0 rounded border border-neutral-300 px-1.5 py-0.5 font-mono text-xs dark:border-neutral-700">
							{shortcut.keys}
						</kbd>
					</li>
				))}
			</ul>
		</Dialog>
	);
}
