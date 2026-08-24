import type { IssueLabel } from "@/api/issues";

/**
 * A Label chip: the Label's own colour as a dot plus its name (brief
 * §7.4). ``compact`` tightens the padding for the narrower Board cards.
 */
export function LabelChip({
	label,
	compact = false,
}: {
	label: IssueLabel;
	compact?: boolean;
}) {
	return (
		<span
			className={
				"inline-flex shrink-0 items-center gap-1.5 rounded-full border border-neutral-200 bg-neutral-50 text-neutral-600 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-300 " +
				(compact ? "px-1.5 py-0 text-[11px]" : "px-2 py-0.5 text-xs")
			}
		>
			<span
				className="inline-block h-2 w-2 shrink-0 rounded-full"
				style={{ backgroundColor: label.color }}
				aria-hidden
			/>
			{label.name}
		</span>
	);
}
