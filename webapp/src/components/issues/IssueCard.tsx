import { Link } from "@tanstack/react-router";
import type { Issue } from "@/api/issues";
import { Avatar } from "@/components/ui/Avatar";
import { PriorityGlyph } from "@/lib/priorities";
import { LabelChip } from "./LabelChip";

/**
 * Issue card, prototype variant B (card stack): identifier + title + state
 * on row one, priority glyph + Label chips on row two, assignee on the
 * right. Links to the detail. In selection mode (bulk, ticket 05) a
 * checkbox is added and the card does not navigate on checkbox clicks.
 */
export function IssueCard({
	issue,
	teamKey,
	selectable = false,
	checked = false,
	onToggle,
}: {
	issue: Issue;
	teamKey: string;
	selectable?: boolean;
	checked?: boolean;
	onToggle?: (issueId: string) => void;
}) {
	return (
		<div className="flex items-start gap-2">
			{selectable && (
				<input
					type="checkbox"
					aria-label={`Select ${issue.identifier}`}
					checked={checked}
					onChange={() => onToggle?.(issue.id)}
					className="mt-3.5 h-4 w-4 shrink-0 accent-accent"
				/>
			)}
			<Link
				to="/teams/$teamKey/issues/$issueId"
				params={{ teamKey, issueId: issue.id }}
				className="block min-w-0 flex-1 rounded-lg border border-neutral-200 bg-white p-3 shadow-sm hover:shadow dark:border-neutral-800 dark:bg-neutral-900"
			>
				<div className="flex items-center gap-2">
					<span className="shrink-0 font-mono text-xs text-neutral-500">
						{issue.identifier}
					</span>
					<span className="min-w-0 flex-1 truncate text-sm font-medium">
						{issue.title}
					</span>
					<span
						className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
						style={{ backgroundColor: issue.state_color }}
						aria-hidden
					/>
					<span className="shrink-0 text-xs text-neutral-500">
						{issue.state_name}
					</span>
				</div>
				<div className="mt-2 flex flex-wrap items-center gap-2">
					<PriorityGlyph priority={issue.priority} />
					{issue.labels.map((label) => (
						<LabelChip key={label.id} label={label} />
					))}
					<span className="flex-1" />
					<Avatar
						user={
							issue.assignee_id
								? {
										displayName: issue.assignee_display_name ?? "Unknown",
										avatarUrl: issue.assignee_avatar_url,
									}
								: null
						}
					/>
				</div>
			</Link>
		</div>
	);
}
