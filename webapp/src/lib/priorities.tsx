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
	none: { icon: Minus, className: "text-faint", label: "No priority" },
	urgent: { icon: AlertOctagon, className: "text-red-500", label: "Urgent" },
	high: {
		icon: ChevronsUp,
		className: "text-foreground",
		label: "High",
	},
	medium: {
		icon: ChevronUp,
		className: "text-muted",
		label: "Medium",
	},
	low: { icon: ChevronDown, className: "text-faint", label: "Low" },
};

/** Priority options for pickers and filters (single source of labels). */
export const PRIORITY_OPTIONS: { value: Priority; label: string }[] = (
	["none", "urgent", "high", "medium", "low"] as const
).map((value) => ({ value, label: PRIORITY_STYLE[value].label }));

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
