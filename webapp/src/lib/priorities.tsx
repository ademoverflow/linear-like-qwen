import {
	AlertOctagon,
	ChevronDown,
	ChevronsUp,
	ChevronUp,
	Minus,
} from "lucide-react";

export type Priority = "none" | "urgent" | "high" | "medium" | "low";

const PRIORITY_STYLE: Record<
	Priority,
	{ icon: typeof Minus; className: string; label: string }
> = {
	none: { icon: Minus, className: "text-neutral-400", label: "No priority" },
	urgent: { icon: AlertOctagon, className: "text-red-500", label: "Urgent" },
	high: {
		icon: ChevronsUp,
		className: "text-neutral-600 dark:text-neutral-300",
		label: "High",
	},
	medium: {
		icon: ChevronUp,
		className: "text-neutral-500 dark:text-neutral-400",
		label: "Medium",
	},
	low: { icon: ChevronDown, className: "text-neutral-400", label: "Low" },
};

/** Linear-style priority glyph, consistent across list, board and detail. */
export function PriorityGlyph({
	priority,
	size = 14,
}: {
	priority: Priority;
	size?: number;
}) {
	const { icon: Icon, className, label } = PRIORITY_STYLE[priority];
	return (
		<span
			className="inline-flex shrink-0"
			role="img"
			title={label}
			aria-label={label}
		>
			<Icon size={size} className={className} />
		</span>
	);
}
