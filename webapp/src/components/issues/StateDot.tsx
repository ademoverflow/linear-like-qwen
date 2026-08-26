import type { WorkflowState } from "@/api/teams";

type Category = WorkflowState["category"];

/** Fixed semantic colour per State category (brief §7.4, ticket 10). */
const CATEGORY_COLOR: Record<Category, string> = {
	backlog: "var(--color-cat-backlog)",
	unstarted: "var(--color-cat-unstarted)",
	started: "var(--color-cat-started)",
	completed: "var(--color-cat-completed)",
	canceled: "var(--color-cat-canceled)",
};

/**
 * The State dot — the only place a State's own colour may be drawn
 * (brief §7.4). Falls back to the fixed category colour when the State
 * colour is missing.
 */
export function StateDot({
	color,
	category,
	small = false,
}: {
	color: string | null | undefined;
	category: Category;
	small?: boolean;
}) {
	return (
		<span
			aria-hidden
			className={
				"inline-block shrink-0 rounded-full " +
				(small ? "h-2 w-2" : "h-2.5 w-2.5")
			}
			style={{ backgroundColor: color ?? CATEGORY_COLOR[category] }}
		/>
	);
}
