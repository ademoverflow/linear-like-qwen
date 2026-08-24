import { Link } from "@tanstack/react-router";
import type { Issue } from "@/api/issues";
import { Avatar } from "@/components/ui/Avatar";
import { PriorityGlyph } from "@/lib/priorities";

/**
 * Issue card, prototype variant B (card stack): identifier + title + state
 * on row one, priority glyph + assignee on row two. Links to the detail.
 */
export function IssueCard({
	issue,
	teamKey,
}: {
	issue: Issue;
	teamKey: string;
}) {
	return (
		<Link
			to="/teams/$teamKey/issues/$issueId"
			params={{ teamKey, issueId: issue.id }}
			className="block rounded-lg border border-neutral-200 bg-white p-3 shadow-sm hover:shadow dark:border-neutral-800 dark:bg-neutral-900"
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
			<div className="mt-2 flex items-center gap-2">
				<PriorityGlyph priority={issue.priority} />
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
	);
}
